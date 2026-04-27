"""
Database connection manager — async PostgreSQL via SQLAlchemy.

Provides:
    - Async engine (asyncpg) with connection pooling
    - AsyncSession factory for route handlers
    - FastAPI dependency: ``get_db``
    - Table creation/teardown via lifespan hooks
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import get_settings
from app.models.database import Base


# ── Engine & session factory (created lazily on first import) ─────────────────

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.debug,
    pool_size=20,          # baseline connections
    max_overflow=10,       # burst headroom (total 30 connections max)
    pool_timeout=30,       # wait for a connection (seconds)
    pool_recycle=1800,     # recycle connections every 30 min
    pool_pre_ping=True,    # verify connections before checkout (health check)
    connect_args={
        "ssl": False,      # ssl false for local development; set True in prod
        "command_timeout": 60,  # Query timeout
        "server_settings": {
            "application_name": "glassnote-api",
            "jit": "off",  # Disable JIT for predictable query performance
        },
    },
    # Connection pool monitoring
    pool_use_lifo=True,    # Reuse recent connections (better for keepalive)
)


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.

    Yields an AsyncSession and commits on success / rolls back on error.
    Each request gets its own session (no cross-request state).

    Usage::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User).where(...))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Lifecycle helpers ─────────────────────────────────────────────────────────

async def create_tables():
    """
    Create all tables defined in ``models/database.py``.

    Called once during application startup. In production, use Alembic
    migrations instead. This is a convenience for development.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[db] ✓ Tables created / verified")


async def close_engine():
    """
    Dispose the connection pool.

    Called during application shutdown to cleanly close all connections.
    """
    await engine.dispose()
    print("[db] ✓ Connection pool disposed")


async def get_pool_status() -> dict:
    """
    Get connection pool status for monitoring.

    Returns:
        dict: Pool statistics
    """
    pool = engine.pool

    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow(),
    }


async def health_check() -> bool:
    """
    Database health check.

    Returns:
        bool: True if database is reachable
    """
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"[db] Health check failed: {e}")
        return False
