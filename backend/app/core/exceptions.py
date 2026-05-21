import traceback
import uuid
from typing import Any, Optional

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = structlog.get_logger(__name__)


class GSTSenseException(Exception):
    """Base class for all GSTSense application exceptions."""

    http_status: int = 500
    code: str = "INT_002"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str,
        code: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, message={self.message!r}, "
            f"details={self.details!r})"
        )


# ---------------------------------------------------------------------------
# 400 – Validation
# ---------------------------------------------------------------------------

class ValidationError(GSTSenseException):
    """HTTP 400 – request data failed business-level validation."""

    http_status = 400

    # VAL_001 invalid_email
    # VAL_002 invalid_gstin
    # VAL_003 invalid_file_type
    # VAL_004 file_too_large
    # VAL_005 missing_required_field

    @classmethod
    def invalid_email(cls, email: str) -> "ValidationError":
        return cls(
            message=f"'{email}' is not a valid email address",
            code="VAL_001",
            details={"email": email},
        )

    @classmethod
    def invalid_gstin(cls, gstin: str) -> "ValidationError":
        return cls(
            message=f"'{gstin}' is not a valid 15-digit GSTIN",
            code="VAL_002",
            details={"gstin": gstin},
        )

    @classmethod
    def invalid_file_type(cls, filename: str, allowed: list[str]) -> "ValidationError":
        return cls(
            message=(
                f"File '{filename}' has an unsupported type. "
                f"Allowed types: {', '.join(allowed)}"
            ),
            code="VAL_003",
            details={"filename": filename, "allowed_types": allowed},
        )

    @classmethod
    def file_too_large(cls, size_mb: float, max_mb: int) -> "ValidationError":
        return cls(
            message=(
                f"File size {size_mb:.1f} MB exceeds the "
                f"{max_mb} MB limit"
            ),
            code="VAL_004",
            details={"size_mb": size_mb, "max_mb": max_mb},
        )

    @classmethod
    def missing_required_field(cls, field: str) -> "ValidationError":
        return cls(
            message=f"Required field '{field}' is missing",
            code="VAL_005",
            details={"field": field},
        )


# ---------------------------------------------------------------------------
# 401 – Authentication
# ---------------------------------------------------------------------------

class AuthenticationError(GSTSenseException):
    """HTTP 401 – caller is not authenticated or credentials are invalid."""

    http_status = 401

    # AUTH_001 invalid_credentials
    # AUTH_002 token_expired
    # AUTH_003 token_invalid
    # AUTH_004 account_locked
    # AUTH_005 account_not_verified

    @classmethod
    def invalid_credentials(cls) -> "AuthenticationError":
        return cls(
            message="Invalid email or password",
            code="AUTH_001",
        )

    @classmethod
    def token_expired(cls) -> "AuthenticationError":
        return cls(
            message="Your session has expired. Please log in again",
            code="AUTH_002",
        )

    @classmethod
    def token_invalid(cls) -> "AuthenticationError":
        return cls(
            message="Authentication token is invalid or malformed",
            code="AUTH_003",
        )

    @classmethod
    def account_locked(cls, until: Optional[str] = None) -> "AuthenticationError":
        details: dict[str, Any] = {}
        msg = "Your account has been temporarily locked due to too many failed login attempts"
        if until:
            msg += f". Try again after {until}"
            details["locked_until"] = until
        return cls(message=msg, code="AUTH_004", details=details)

    @classmethod
    def account_not_verified(cls) -> "AuthenticationError":
        return cls(
            message="Please verify your email address before logging in",
            code="AUTH_005",
        )


# ---------------------------------------------------------------------------
# 403 – Authorization
# ---------------------------------------------------------------------------

class AuthorizationError(GSTSenseException):
    """HTTP 403 – caller is authenticated but lacks permission."""

    http_status = 403

    # AUTHZ_001 insufficient_permissions
    # AUTHZ_002 plan_upgrade_required
    # AUTHZ_003 resource_not_owned
    # AUTHZ_004 scan_not_paid

    @classmethod
    def insufficient_permissions(cls, required: str) -> "AuthorizationError":
        return cls(
            message=f"You do not have the '{required}' permission required for this action",
            code="AUTHZ_001",
            details={"required_permission": required},
        )

    @classmethod
    def plan_upgrade_required(cls, required_plan: str, current_plan: str) -> "AuthorizationError":
        return cls(
            message=(
                f"This feature requires the '{required_plan}' plan. "
                f"You are currently on '{current_plan}'"
            ),
            code="AUTHZ_002",
            details={"required_plan": required_plan, "current_plan": current_plan},
        )

    @classmethod
    def resource_not_owned(cls, resource: str) -> "AuthorizationError":
        return cls(
            message=f"You do not have access to this {resource}",
            code="AUTHZ_003",
            details={"resource": resource},
        )

    @classmethod
    def scan_not_paid(cls, scan_id: str) -> "AuthorizationError":
        return cls(
            message="Payment is required to access this scan report",
            code="AUTHZ_004",
            details={"scan_id": scan_id},
        )


# ---------------------------------------------------------------------------
# 404 – Not Found
# ---------------------------------------------------------------------------

class NotFoundError(GSTSenseException):
    """HTTP 404 – requested resource does not exist."""

    http_status = 404

    # NF_001 scan_not_found
    # NF_002 user_not_found
    # NF_003 organization_not_found

    @classmethod
    def scan(cls, scan_id: str) -> "NotFoundError":
        return cls(
            message=f"Scan '{scan_id}' was not found",
            code="NF_001",
            details={"scan_id": scan_id},
        )

    @classmethod
    def user(cls, user_id: str) -> "NotFoundError":
        return cls(
            message=f"User '{user_id}' was not found",
            code="NF_002",
            details={"user_id": user_id},
        )

    @classmethod
    def organization(cls, org_id: str) -> "NotFoundError":
        return cls(
            message=f"Organization '{org_id}' was not found",
            code="NF_003",
            details={"org_id": org_id},
        )


# ---------------------------------------------------------------------------
# 409 – Conflict
# ---------------------------------------------------------------------------

class ConflictError(GSTSenseException):
    """HTTP 409 – request conflicts with current resource state."""

    http_status = 409

    # CONF_001 email_already_registered
    # CONF_002 gstin_already_registered
    # CONF_003 payment_already_processed

    @classmethod
    def email_already_registered(cls, email: str) -> "ConflictError":
        return cls(
            message=f"An account with email '{email}' already exists",
            code="CONF_001",
            details={"email": email},
        )

    @classmethod
    def gstin_already_registered(cls, gstin: str) -> "ConflictError":
        return cls(
            message=f"GSTIN '{gstin}' is already linked to another organization",
            code="CONF_002",
            details={"gstin": gstin},
        )

    @classmethod
    def payment_already_processed(cls, payment_id: str) -> "ConflictError":
        return cls(
            message=f"Payment '{payment_id}' has already been processed",
            code="CONF_003",
            details={"payment_id": payment_id},
        )


# ---------------------------------------------------------------------------
# 429 – Rate Limit
# ---------------------------------------------------------------------------

class RateLimitError(GSTSenseException):
    """HTTP 429 – caller has exceeded an allowed request rate."""

    http_status = 429

    # RATE_001 too_many_requests
    # RATE_002 too_many_login_attempts
    # RATE_003 upload_limit_exceeded

    @classmethod
    def too_many_requests(cls, retry_after: int) -> "RateLimitError":
        return cls(
            message=f"Too many requests. Please wait {retry_after} seconds before retrying",
            code="RATE_001",
            details={"retry_after_seconds": retry_after},
        )

    @classmethod
    def too_many_login_attempts(cls, retry_after: int) -> "RateLimitError":
        return cls(
            message=(
                f"Too many failed login attempts. "
                f"Please wait {retry_after} seconds before trying again"
            ),
            code="RATE_002",
            details={"retry_after_seconds": retry_after},
        )

    @classmethod
    def upload_limit_exceeded(cls, limit_per_hour: int) -> "RateLimitError":
        return cls(
            message=(
                f"You have reached the upload limit of {limit_per_hour} "
                f"files per hour"
            ),
            code="RATE_003",
            details={"limit_per_hour": limit_per_hour},
        )


# ---------------------------------------------------------------------------
# 502 – External Service
# ---------------------------------------------------------------------------

class ExternalServiceError(GSTSenseException):
    """HTTP 502 – a downstream service failed or is unavailable."""

    http_status = 502

    # EXT_001 ai_service_unavailable
    # EXT_002 payment_service_error
    # EXT_003 storage_service_error

    @classmethod
    def ai_service_unavailable(cls) -> "ExternalServiceError":
        return cls(
            message="The AI explanation service is temporarily unavailable. Please try again shortly",
            code="EXT_001",
        )

    @classmethod
    def payment_service_error(cls, detail: str = "") -> "ExternalServiceError":
        return cls(
            message="The payment service encountered an error. Please try again",
            code="EXT_002",
            details={"detail": detail} if detail else {},
        )

    @classmethod
    def storage_service_error(cls) -> "ExternalServiceError":
        return cls(
            message="File storage service is temporarily unavailable. Please try again shortly",
            code="EXT_003",
        )


# ---------------------------------------------------------------------------
# 500 – Internal
# ---------------------------------------------------------------------------

class InternalError(GSTSenseException):
    """HTTP 500 – unrecoverable server-side error."""

    http_status = 500

    # INT_001 database_error
    # INT_002 unexpected_error
    # INT_003 file_processing_error

    @classmethod
    def database_error(cls, detail: str = "") -> "InternalError":
        return cls(
            message="A database error occurred. Our team has been notified",
            code="INT_001",
            details={"detail": detail} if detail else {},
        )

    @classmethod
    def unexpected_error(cls) -> "InternalError":
        return cls(
            message="An unexpected error occurred. Our team has been notified",
            code="INT_002",
        )

    @classmethod
    def file_processing_error(cls, filename: str) -> "InternalError":
        return cls(
            message=f"Failed to process file '{filename}'. Please try uploading again",
            code="INT_003",
            details={"filename": filename},
        )


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

async def gstsense_exception_handler(
    request: Request,
    exc: GSTSenseException,
) -> JSONResponse:
    """Handles all GSTSenseException subclasses with a consistent response envelope."""
    request_id: str = getattr(request.state, "request_id", str(uuid.uuid4()))

    log = logger.bind(
        request_id=request_id,
        exception_type=type(exc).__name__,
        error_code=exc.code,
        http_status=exc.http_status,
        path=request.url.path,
        method=request.method,
    )

    if exc.http_status >= 500:
        log.error("application_error", message=exc.message, details=exc.details)
    else:
        log.warning("client_error", message=exc.message, details=exc.details)

    body: dict[str, Any] = {
        "status": "error",
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
        "request_id": request_id,
    }

    if settings.is_development:
        body["error"]["exception_type"] = type(exc).__name__

    return JSONResponse(status_code=exc.http_status, content=body)


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catches all unhandled exceptions, logs the full traceback, and returns a safe 500."""
    request_id: str = getattr(request.state, "request_id", str(uuid.uuid4()))

    tb = traceback.format_exc()

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
        traceback=tb,
    )

    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass

    body: dict[str, Any] = {
        "status": "error",
        "error": {
            "code": "INT_002",
            "message": "An unexpected error occurred. Our team has been notified",
            "details": {},
        },
        "request_id": request_id,
    }

    if settings.is_development:
        body["error"]["exception_type"] = type(exc).__name__
        body["error"]["traceback"] = tb

    return JSONResponse(status_code=500, content=body)
