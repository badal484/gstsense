import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import cast

import bcrypt
import redis.asyncio as aioredis
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger

logger = get_logger(__name__)

_BCRYPT_ROUNDS = 12


# ---------------------------------------------------------------------------
# Token payload model
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """Validated representation of a decoded JWT payload."""

    sub: str           # user_id (UUID string)
    org_id: str        # organization_id (UUID string)
    role: str          # smb | growth | ca_firm | admin
    jti: str           # JWT ID – used for token revocation
    exp: datetime
    iat: datetime
    type: str          # "access" | "refresh"


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def _prehash(password: str) -> bytes:
    """SHA-256 prehash so bcrypt never sees >72 bytes."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """Hash *password* using bcrypt (12 rounds) with SHA-256 prehashing."""
    if not password:
        raise ValueError("Password must not be empty")
    hashed = bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` when *plain_password* matches *hashed_password*."""
    try:
        return bcrypt.checkpw(_prehash(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, org_id: str, role: str) -> str:
    """Create and return a signed JWT access token.

    The token expires in ``JWT_ACCESS_TOKEN_EXPIRE_MINUTES`` minutes.
    A unique ``jti`` is embedded so individual tokens can be revoked via
    a Redis blocklist without invalidating the whole session.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, object] = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return cast(str, jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM))


def create_refresh_token(user_id: str) -> str:
    """Create and return a signed JWT refresh token.

    Refresh tokens are long-lived (``JWT_REFRESH_TOKEN_EXPIRE_DAYS`` days)
    and carry only the ``sub`` claim so that a compromised refresh token
    cannot be used directly to impersonate a user without going through the
    token-exchange endpoint.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, object] = {
        "sub": user_id,
        "org_id": "",
        "role": "",
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return cast(str, jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM))


# ---------------------------------------------------------------------------
# JWT token verification
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict[str, object]:
    """Decode a JWT and return its raw payload dict.

    Raises the appropriate ``AuthenticationError`` on expiry or invalidity
    so callers do not need to handle ``JWTError`` directly.
    """
    try:
        return cast(
            dict[str, object],
            jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]),
        )
    except ExpiredSignatureError:
        raise AuthenticationError.token_expired()
    except JWTError:
        raise AuthenticationError.token_invalid()


def verify_access_token(token: str) -> TokenPayload:
    """Decode, validate, and return the payload of an access token.

    Raises:
        AuthenticationError (AUTH_002): token has expired.
        AuthenticationError (AUTH_003): token is invalid or malformed.
    """
    payload = _decode_token(token)

    if payload.get("type") != "access":
        logger.warning("token_type_mismatch", expected="access", got=payload.get("type"))
        raise AuthenticationError.token_invalid()

    return TokenPayload(
        sub=str(payload["sub"]),
        org_id=str(payload.get("org_id", "")),
        role=str(payload.get("role", "")),
        jti=str(payload["jti"]),
        exp=_to_datetime(payload["exp"]),
        iat=_to_datetime(payload["iat"]),
        type=str(payload["type"]),
    )


def verify_refresh_token(token: str) -> TokenPayload:
    """Decode, validate, and return the payload of a refresh token.

    Raises:
        AuthenticationError (AUTH_002): token has expired.
        AuthenticationError (AUTH_003): token is invalid or malformed.
    """
    payload = _decode_token(token)

    if payload.get("type") != "refresh":
        logger.warning("token_type_mismatch", expected="refresh", got=payload.get("type"))
        raise AuthenticationError.token_invalid()

    return TokenPayload(
        sub=str(payload["sub"]),
        org_id=str(payload.get("org_id", "")),
        role=str(payload.get("role", "")),
        jti=str(payload["jti"]),
        exp=_to_datetime(payload["exp"]),
        iat=_to_datetime(payload["iat"]),
        type=str(payload["type"]),
    )


def _to_datetime(value: object) -> datetime:
    """Convert a JWT numeric date (int/float) or a datetime to a UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(float(str(value)), tz=timezone.utc)


# ---------------------------------------------------------------------------
# Razorpay signature verification
# ---------------------------------------------------------------------------

def verify_razorpay_webhook_signature(
    payload_body: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """Verify the HMAC-SHA256 signature on a Razorpay webhook request.

    Args:
        payload_body: The raw ``bytes`` body of the incoming HTTP request.
        signature: The value of the ``X-Razorpay-Signature`` header.
        webhook_secret: The webhook secret configured in the Razorpay dashboard.

    Returns:
        ``True`` if the signature is authentic, ``False`` otherwise.
    """
    try:
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        valid = hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.warning("razorpay_webhook_signature_error", error=str(exc))
        return False

    if not valid:
        logger.warning(
            "razorpay_webhook_signature_mismatch",
            received_signature=signature[:16] + "…",
        )
    return valid


def verify_razorpay_payment_signature(
    order_id: str,
    payment_id: str,
    signature: str,
) -> bool:
    """Verify the Razorpay payment signature after checkout.

    The message is ``"{order_id}|{payment_id}"`` signed with
    ``RAZORPAY_KEY_SECRET`` using HMAC-SHA256, as per Razorpay docs.

    Returns:
        ``True`` if authentic, ``False`` otherwise.
    """
    try:
        message = f"{order_id}|{payment_id}".encode("utf-8")
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        valid = hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.warning("razorpay_payment_signature_error", error=str(exc))
        return False

    if not valid:
        logger.warning(
            "razorpay_payment_signature_mismatch",
            order_id=order_id,
            payment_id=payment_id,
        )
    return valid


# ---------------------------------------------------------------------------
# User blocklist (Redis) — for immediate token invalidation on account delete
# ---------------------------------------------------------------------------


async def add_user_to_blocklist(user_id: str) -> None:
    """Block all tokens for user_id. TTL = access token lifetime."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.setex(
            f"blocked_user:{user_id}",
            settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "1",
        )
    finally:
        await r.aclose()


async def is_user_blocked(user_id: str) -> bool:
    """Return True if the user is in the blocklist."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        result = await r.get(f"blocked_user:{user_id}")
        return result is not None
    except Exception:
        return False
    finally:
        await r.aclose()


# ---------------------------------------------------------------------------
# Secure token generation
# ---------------------------------------------------------------------------

def generate_secure_token(length: int = 32) -> str:
    """Return a URL-safe, cryptographically secure random token.

    Used for password-reset links, email verification tokens, and
    one-time invitation codes.

    Args:
        length: Number of random bytes before URL-safe base64 encoding.
                The resulting string will be longer than *length*.
    """
    return secrets.token_urlsafe(length)
