import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    InternalError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_secure_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.models.audit_log import AuditLog
from app.models.organization import Organization, Plan
from app.models.refresh_token import RefreshToken
from app.models.user import AccountType, User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.email_service import send_password_reset_email

logger = get_logger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
RESET_TOKEN_EXPIRY_HOURS = 1


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        request: RegisterRequest,
        ip_address: Optional[str] = None,
    ) -> tuple[User, Organization]:
        """Create a new user account and their first organization atomically.

        All DB writes participate in the caller's transaction (via get_db).
        If anything fails the entire transaction rolls back.
        """
        # 1. Email uniqueness
        existing = await self.db.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError.email_already_registered(request.email)

        # 2. GSTIN uniqueness (case-insensitive)
        existing_org = await self.db.execute(
            select(Organization).where(
                func.upper(Organization.gstin) == request.gstin.upper()
            )
        )
        if existing_org.scalar_one_or_none() is not None:
            raise ConflictError.gstin_already_registered(request.gstin)

        # 3. Create User
        user = User(
            email=request.email,
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            account_type=AccountType.smb,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()  # populate user.id before creating the org

        # 4. Create Organization (state_code = first 2 chars of GSTIN)
        org = Organization(
            owner_user_id=user.id,
            business_name=request.full_name,
            gstin=request.gstin,
            state_code=request.gstin[:2],
            plan=Plan.free,
            invoice_limit=settings.MAX_INVOICES_FREE,
            invoices_used_this_month=0,
        )
        self.db.add(org)
        await self.db.flush()  # populate org.id before the audit log

        # 5. Audit log
        await self._create_audit_log(
            action="user_registered",
            user_id=user.id,
            organization_id=org.id,
            ip_address=ip_address,
        )

        # Refresh to pick up server-default timestamps (created_at, updated_at)
        await self.db.refresh(user)
        await self.db.refresh(org)

        logger.info(
            "user_registered",
            user_id=str(user.id),
            email=user.email,
            gstin=org.gstin,
        )
        return user, org

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(
        self,
        request: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[User, Organization]:
        """Authenticate credentials with brute-force protection.

        Security-critical writes (failed attempts, lockout, audit log) are
        committed immediately before raising any exception so they persist
        even though the request ultimately returns an error response.
        """
        # 1. Look up by email — use a generic error to avoid enumeration
        result = await self.db.execute(
            select(User).where(User.email == request.email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError.invalid_credentials()

        now = datetime.now(tz=timezone.utc)

        # 2. Lockout check
        if user.locked_until and user.locked_until > now:
            remaining_minutes = int(
                (user.locked_until - now).total_seconds() / 60
            )
            raise AuthenticationError.account_locked(
                until=f"{remaining_minutes} minutes"
            )

        # 3. Active check
        if not user.is_active:
            raise AuthenticationError.invalid_credentials()

        # 4. Password verification
        if not verify_password(request.password, user.hashed_password):
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                user.failed_login_attempts = 0
                await self._create_audit_log(
                    action="account_locked",
                    user_id=user.id,
                    ip_address=ip_address,
                    metadata={"reason": "max_failed_attempts"},
                )

            await self._create_audit_log(
                action="user_login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            # Commit security writes before raising so they survive the rollback
            # that get_db performs when an exception propagates.
            await self.db.commit()
            raise AuthenticationError.invalid_credentials()

        # 5. Success — reset counters and record login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now

        await self._create_audit_log(
            action="user_logged_in",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 6. Fetch primary organisation (created at registration)
        org_result = await self.db.execute(
            select(Organization).where(Organization.owner_user_id == user.id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            raise NotFoundError.organization(str(user.id))

        logger.info("user_logged_in", user_id=str(user.id), email=user.email)
        return user, org

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    async def store_refresh_token(self, user_id: uuid.UUID, token: str) -> None:
        """Decode a refresh token and persist its jti for revocation tracking."""
        payload = verify_refresh_token(token)
        record = RefreshToken(
            jti=payload.jti,
            user_id=user_id,
            expires_at=payload.exp,
        )
        self.db.add(record)

    async def refresh_tokens(
        self,
        refresh_token: str,
    ) -> tuple[str, str]:
        """Validate a refresh token and issue a new token pair (rotation)."""
        payload = verify_refresh_token(refresh_token)

        # Check revocation in DB
        rt_result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.jti == payload.jti)
        )
        rt_record = rt_result.scalar_one_or_none()
        if rt_record is not None and rt_record.revoked_at is not None:
            raise AuthenticationError.token_invalid()

        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(payload.sub))
        )
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise AuthenticationError.token_invalid()

        # Revoke old token
        if rt_record is not None:
            rt_record.revoked_at = datetime.now(tz=timezone.utc)

        # Fetch org to embed org_id in the new access token
        org_result = await self.db.execute(
            select(Organization).where(Organization.owner_user_id == user.id)
        )
        org = org_result.scalar_one_or_none()
        org_id = str(org.id) if org else ""

        new_access = create_access_token(
            user_id=str(user.id),
            org_id=org_id,
            role=user.account_type.value,
        )
        new_refresh = create_refresh_token(user_id=str(user.id))

        # Store new refresh token record
        new_payload = verify_refresh_token(new_refresh)
        self.db.add(RefreshToken(
            jti=new_payload.jti,
            user_id=user.id,
            expires_at=new_payload.exp,
        ))

        # Purge expired tokens older than 60 days
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=60)
        await self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < cutoff)
        )

        logger.info("tokens_refreshed", user_id=str(user.id))
        return new_access, new_refresh

    # ------------------------------------------------------------------
    # Get user + org
    # ------------------------------------------------------------------

    async def get_user_with_org(
        self,
        user_id: uuid.UUID,
    ) -> tuple[User, Organization]:
        """Fetch user and their primary organisation. Raises 404 if either missing."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError.user(str(user_id))

        org_result = await self.db.execute(
            select(Organization).where(Organization.owner_user_id == user_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            raise NotFoundError.organization(str(user_id))

        return user, org

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    async def request_password_reset(self, email: str) -> None:
        """Initiate the password-reset flow.

        Always returns silently — never reveals whether the email is registered.
        The plain token is emailed; only its SHA-256 hash is stored.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            # Silent return — prevent email enumeration
            return

        plain_token = generate_secure_token(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()
        expiry = datetime.now(tz=timezone.utc) + timedelta(
            hours=RESET_TOKEN_EXPIRY_HOURS
        )

        user.password_reset_token = hashed_token
        user.password_reset_expires_at = expiry

        await self._create_audit_log(
            action="password_reset_requested",
            user_id=user.id,
        )

        try:
            await send_password_reset_email(email=email, reset_token=plain_token)
        except Exception as exc:
            logger.error(
                "password_reset_email_failed",
                email=email,
                error=str(exc),
            )
            # Do not raise — the token is stored; user can retry

        logger.info("password_reset_requested", user_id=str(user.id), email=email)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Complete the password-reset flow.

        Finds the user by the SHA-256 hash of the submitted token,
        validates expiry, then updates the password.
        """
        hashed_token = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(User).where(User.password_reset_token == hashed_token)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise ValidationError(
                message="Password reset token is invalid",
                code="VAL_005",
            )

        now = datetime.now(tz=timezone.utc)
        if user.password_reset_expires_at is None or user.password_reset_expires_at < now:
            raise ValidationError(
                message="Password reset token has expired. Please request a new one",
                code="VAL_005",
            )

        user.hashed_password = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires_at = None

        await self._create_audit_log(
            action="password_reset_completed",
            user_id=user.id,
        )

        logger.info("password_reset_completed", user_id=str(user.id))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_audit_log(
        self,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Append an immutable audit record to the current transaction."""
        entry = AuditLog(
            action=action,
            user_id=user_id,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata,
        )
        self.db.add(entry)
