"""
Tests for database connection pooling and health checks.
"""

import pytest
from app.services.database import get_pool_status, health_check


@pytest.mark.asyncio
async def test_health_check():
    """Test database health check."""
    is_healthy = await health_check()
    assert isinstance(is_healthy, bool)


@pytest.mark.asyncio
async def test_pool_status():
    """Test pool status retrieval."""
    status = await get_pool_status()

    assert "size" in status
    assert "checked_in" in status
    assert "checked_out" in status
    assert "overflow" in status
    assert "total" in status

    # Sanity checks
    assert status["size"] >= 0
    assert status["total"] >= 0
