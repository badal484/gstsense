import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import check_database_health
import redis.asyncio as aioredis
from app.core.exceptions import GSTSenseException, generic_exception_handler, gstsense_exception_handler
from app.core.logging import RequestLoggingMiddleware, get_logger, setup_logging
from app.middleware.security_headers import SecurityHeadersMiddleware as EnhancedSecurityHeaders

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ---- Startup ----
    os.environ.setdefault("TZ", "Asia/Kolkata")
    time.tzset()
    setup_logging()

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )

    db_healthy = await check_database_health()
    if db_healthy:
        logger.info("database_healthy")
    else:
        logger.error("database_unhealthy_on_startup")

    logger.info(
        "application_started",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    yield

    # ---- Shutdown ----
    logger.info("application_shutting_down")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="GST Compliance SaaS for Indian SMBs and CA firms",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware stack
# Note: add_middleware stacks in reverse — last added runs outermost on request.
# Desired order: CORS → RequestLogging → SecurityHeaders → app
# ---------------------------------------------------------------------------

app.add_middleware(EnhancedSecurityHeaders)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

app.add_exception_handler(GSTSenseException, gstsense_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, generic_exception_handler)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Infrastructure"])
async def health_check() -> JSONResponse:
    """Return application health status.

    HTTP 200 when all checks pass, HTTP 503 when any check fails.
    """
    db_ok = await check_database_health()

    redis_ok = False
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    checks = {
        "database": db_ok,
        "redis": redis_ok,
    }
    all_healthy = all(checks.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )


# ---------------------------------------------------------------------------
# API router
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
