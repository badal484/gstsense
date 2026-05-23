import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import ssl as _ssl

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SSL context (used for RDS / managed Postgres that require SSL)
# Only active when DATABASE_SSL=true in the environment.
# ---------------------------------------------------------------------------

def _build_connect_args() -> dict:
    if not settings.DATABASE_SSL:
        return {}
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return {"ssl": ctx}

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args=_build_connect_args(),
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    # Don't expire ORM objects when the session is committed so that we can
    # still read attributes after the transaction closes without issuing
    # extra SELECT queries.
    expire_on_commit=False,
)


# Base is defined in app.models.base and re-exported here for convenience.
# Import it from there rather than from this module to avoid circular imports.

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` for use as a FastAPI dependency.

    - Commits on a clean exit.
    - Rolls back and re-raises on any exception.
    - Always closes the session in a ``finally`` block.
    - Logs a warning when the session exceeds 1 second of total wall time.
    """
    start = time.perf_counter()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            elapsed = time.perf_counter() - start
            if elapsed > 1.0:
                logger.warning(
                    "slow_db_session",
                    duration_ms=round(elapsed * 1000),
                )


# ---------------------------------------------------------------------------
# Celery-safe session (NullPool — no asyncpg connection reuse across event loops)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def celery_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh AsyncSession with NullPool for use inside Celery tasks.

    Each Celery task runs its own event loop via asyncio.new_event_loop().
    Using the module-level pooled engine across event loops causes asyncpg
    errors because connections are loop-bound. NullPool creates a fresh
    connection per session and discards it on close.
    """
    _engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, connect_args=_build_connect_args())
    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await _engine.dispose()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def check_database_health() -> bool:
    """Execute ``SELECT 1`` to verify the database connection is live.

    Returns ``True`` if healthy, ``False`` on any error.
    A 5-second connect timeout is enforced via the engine's pool.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(
            "database_health_check_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return False


# ---------------------------------------------------------------------------
# Row-level security context
# ---------------------------------------------------------------------------

async def set_rls_context(
    session: AsyncSession,
    user_id: str,
    org_id: str,
) -> None:
    """Set PostgreSQL session-local variables used by RLS policies.

    These variables are visible to all row-level security policies within
    the current transaction via ``current_setting('app.current_user_id')``.
    ``SET LOCAL`` scopes them to the transaction so they are automatically
    cleared when the transaction ends.

    Call this at the start of every authenticated database operation.
    """
    # SET LOCAL does not support $1 placeholders — embed the validated UUID strings directly.
    # Values come from verified JWT claims (server-signed), not user input.
    await session.execute(text(f"SET LOCAL app.current_user_id = '{user_id}'"))
    await session.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))
