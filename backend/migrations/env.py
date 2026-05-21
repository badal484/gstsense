import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic / logging setup
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import all models so their tables are registered on Base.metadata.
# The wildcard import is intentional: adding a new model to __init__.py is
# all that is needed for Alembic to pick it up automatically.
# ---------------------------------------------------------------------------

from app.core.config import settings  # noqa: E402
from app.models import (  # noqa: E402, F401
    AuditLog,
    Mismatch,
    Notice,
    Organization,
    Payment,
    Scan,
    Subscription,
    User,
)
from app.models.base import Base  # noqa: E402

# NOTE: We do NOT call config.set_main_option("sqlalchemy.url", ...) here
# because ConfigParser treats '%' as an interpolation character and will
# reject URLs whose passwords contain percent-encoded characters (e.g. %40).
# Instead, we build the engine directly from settings in run_async_migrations.

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode (generates SQL without a live connection)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (runs against a live database via asyncpg)
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
