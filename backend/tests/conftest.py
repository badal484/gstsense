"""Pytest fixtures shared across all test modules.

Uses a real PostgreSQL test database (gstsense_test) that is created,
migrated, and torn down for the test session. Each test function runs
inside a TRUNCATE-based cleanup so it starts with a clean slate.

Architecture notes:
- Schema is created once before all tests using asyncio.run() (outside any
  pytest-asyncio managed event loop) so there are no session/function loop
  mismatch issues.
- Each test gets a fresh NullPool engine so asyncpg connections are never
  shared across tasks or reused across test functions.
- Starlette's BaseHTTPMiddleware task-group runs request handlers in subtasks;
  using NullPool + per-request sessions avoids "another operation in progress".
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.models.base import Base

TEST_DB_URL = (
    "postgresql+asyncpg://postgres:Mac%404834@localhost:5433/gstsense_test"
)

# Tables to truncate between tests (dependency order — children first)
_TRUNCATE_TABLES = [
    "audit_logs",
    "user_preferences",
    "compliance_scores",
    "mismatches",
    "referral_commissions",
    "ca_client_relationships",
    "ca_firms",
    "payments",
    "scans",
    "subscriptions",
    "notices",
    "organizations",
    "users",
]

_TRUNCATE_SQL = (
    f"TRUNCATE TABLE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE"
)


# ---------------------------------------------------------------------------
# Session setup — create schema once using asyncio.run (no fixture loop)
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run a coroutine in a fresh, self-contained event loop."""
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="session", autouse=True)
def create_test_schema():
    """Drop and recreate all tables once before the test session starts."""

    async def setup() -> None:
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def teardown() -> None:
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    _run(setup())
    yield
    _run(teardown())


# ---------------------------------------------------------------------------
# Per-test HTTP client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to the FastAPI app with a fresh NullPool engine per test.

    Each request gets its own session so Starlette's BaseHTTPMiddleware
    task-group can run subtasks without sharing a single asyncpg connection.
    After the test, all tables are truncated for a clean slate.
    """
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

    # Truncate after each test
    async with engine.begin() as conn:
        await conn.execute(text(_TRUNCATE_SQL))

    await engine.dispose()


# ---------------------------------------------------------------------------
# Convenience data fixtures
# ---------------------------------------------------------------------------

VALID_REGISTER_PAYLOAD = {
    "full_name": "Arjun Sharma",
    "email": "arjun@example.com",
    "password": "StrongPass1",
    "gstin": "29ABCDE1234F1Z5",
}


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user and return the full API response data."""
    resp = await client.post("/api/v1/auth/register", json=VALID_REGISTER_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest_asyncio.fixture
async def auth_headers(registered_user: dict) -> dict:
    """Return Authorization headers for the registered user's access token."""
    token = registered_user["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
