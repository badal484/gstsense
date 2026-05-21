"""Rate limiting middleware and limiter instance."""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=settings.REDIS_URL,
)

AUTH_LIMIT = "5/minute"
UPLOAD_LIMIT = "10/hour"
API_LIMIT = "100/minute"
STRICT_LIMIT = "3/minute"


def get_rate_limit_handler() -> object:
    """Return custom rate-limit-exceeded handler with consistent JSON error format."""

    async def handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        logger.warning(
            "rate_limit_exceeded",
            path=request.url.path,
            client_ip=get_remote_address(request),
            limit=str(exc.detail),
        )
        return JSONResponse(
            status_code=429,
            content={
                "status": "error",
                "error": {
                    "code": "RATE_001",
                    "message": "Too many requests. Please slow down.",
                    "details": {"retry_after": "60 seconds"},
                },
            },
        )

    return handler
