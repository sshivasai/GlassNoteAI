"""
tests/conftest.py

Shared pytest fixtures for all GlassNote backend tests.

Strategy: Manual Add/Delete cleanup
─────────────────────────────────────────────────
Every test uses the real database. We use an `autouse` fixture to
delete test records after each test runs so the database stays clean.

Requirements:
  - PostgreSQL must be running and DATABASE_URL must be set in .env
  - Tables must already exist (the app auto-creates them on startup,
    or: python -c "import asyncio; from app.services.database import
    create_tables; asyncio.run(create_tables())")

Environment:
  - Set ADMIN_SECRET=test-admin-secret in .env (or the test env)
    before running tests, or it will be injected automatically below.

Run all tests:
    pytest tests/ -v
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import Header

# ── Inject test admin secret before any app imports resolve settings ──────────
ADMIN_SECRET = "test-admin-secret-glassnote"
os.environ.setdefault("ADMIN_SECRET", ADMIN_SECRET)

# Now import app (settings are resolved here)
from app.main import app
from app.services.database import async_session_factory, get_db
import app.routers.notifications as notifications_router


# ── Shared test constants ─────────────────────────────────────────────────────

TEST_EMAIL    = "pytest_user@glassnote-test.internal"
TEST_PASSWORD = "TestPass1234!"
TEST_DEVICE   = "pytest_device_fingerprint_001"


# ── Override admin guard for tests ────────────────────────────────────────────

async def _test_require_admin(x_admin_secret: str = Header(default="")) -> None:
    """Test replacement for _require_admin — validates against the test constant."""
    from fastapi import Header, HTTPException, status
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

# Inject the override into the app's dependency registry
app.dependency_overrides[notifications_router._require_admin] = _test_require_admin


# ── Core: DB session and cleanup ──────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_db():
    """Delete test records after each test."""
    yield
    async with async_session_factory() as session:
        # Delete test user and related records
        await session.execute(text(f"DELETE FROM usage_quotas WHERE user_id IN (SELECT id FROM users WHERE email = '{TEST_EMAIL}')"))
        await session.execute(text(f"DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email = '{TEST_EMAIL}')"))
        await session.execute(text(f"DELETE FROM email_otps WHERE user_id IN (SELECT id FROM users WHERE email = '{TEST_EMAIL}')"))
        await session.execute(text(f"DELETE FROM users WHERE email = '{TEST_EMAIL}'"))
        
        # Delete test notifications
        await session.execute(text("DELETE FROM system_notifications WHERE created_by = 'pytest'"))
        await session.commit()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Provide a normal AsyncSession for the test to use for assertions."""
    session = async_session_factory()
    yield session
    await session.close()


@pytest_asyncio.fixture(scope="function")
async def client():
    """
    Provide an HTTPX AsyncClient pointed at the FastAPI app.
    
    The app uses its normal get_db dependency (which commits properly),
    so API calls behave exactly like production.
    """
    transport = ASGITransport(app=app)
    ac = AsyncClient(transport=transport, base_url="http://test")
    yield ac
    await ac.aclose()

