import logging
import sys
import time
import uuid
from typing import Any, Callable, cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings


def setup_logging() -> None:
    """Configure structlog for the current environment.

    Call exactly once at application startup in main.py before
    any logger is acquired.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_service_context,
    ]

    if settings.is_development:
        # Human-readable, coloured output for local development.
        processors: list[Any] = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        stdlib_formatter = logging.Formatter("%(message)s")
    else:
        # Machine-readable JSON for production log aggregation (Datadog, CloudWatch).
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        stdlib_formatter = logging.Formatter("%(message)s")

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Mirror stdlib logging (uvicorn, SQLAlchemy, etc.) through structlog.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(stdlib_formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Quieten noisy third-party loggers.
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _add_service_context(
    logger: Any,  # noqa: ANN001
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor: stamps every log entry with service metadata."""
    event_dict["service"] = settings.APP_NAME
    event_dict["environment"] = settings.ENVIRONMENT
    event_dict["version"] = settings.APP_VERSION
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger bound to *name*.

    Usage::

        logger = get_logger(__name__)
        logger.info("scan_started", scan_id=scan_id, user_id=user_id)
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that logs every HTTP request/response pair.

    Per-request:
    - Generates a unique ``request_id`` (UUID4) and stores it in
      ``request.state.request_id``.
    - Adds ``X-Request-ID`` to the response headers so callers can
      correlate logs with their own traces.
    - Logs method, path, status code, and wall-clock duration in
      milliseconds.
    - If the request is authenticated the ``user_id`` is included.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = get_logger("http.access")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = _elapsed_ms(start)
            self._logger.exception(
                "request_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            raise

        duration_ms = _elapsed_ms(start)
        response.headers["X-Request-ID"] = request_id

        user_id: str | None = getattr(request.state, "user_id", None)

        log_kwargs: dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
        }
        if user_id:
            log_kwargs["user_id"] = user_id

        level: Callable[..., None] = (
            self._logger.warning
            if response.status_code >= 400
            else self._logger.info
        )
        level("http_request", **log_kwargs)

        return response


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
