"""
tests/test_notifications.py

Integration tests for the notifications router against the real PostgreSQL database.

Isolation strategy: SAVEPOINT rollback (see conftest.py)
Every test runs inside a SAVEPOINT that is always rolled back.
No notification records persist after any test.

Tests cover:
    - GET /api/notifications/active (empty, with data)
    - Plan-targeted filtering
    - Expired notification exclusion
    - POST /api/notifications/create (admin auth required)
    - POST /api/notifications/deactivate/{id} (admin auth required)
    - GET /api/notifications/list (admin auth required)

Run:
    pytest tests/test_notifications.py -v
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from unittest.mock import patch

from app.models.database import SystemNotification
from tests.conftest import ADMIN_SECRET


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_notification_in_db(db_session, **kwargs) -> SystemNotification:
    """Insert a notification directly via the test DB session."""
    defaults = dict(
        title="Test Alert",
        message="This is a test message",
        type="info",
        is_active=True,
        created_by="pytest",
    )
    defaults.update(kwargs)
    n = SystemNotification(**defaults)
    db_session.add(n)
    await db_session.flush()
    await db_session.commit()
    return n


async def _create_via_api(client, **overrides) -> dict:
    """Create a notification via the admin API endpoint."""
    payload = dict(
        title="API Alert",
        message="Created via API",
        type="info",
        created_by="pytest",
    )
    payload.update(overrides)
    r = await client.post(
        "/api/notifications/create",
        json=payload,
        headers={"X-Admin-Secret": ADMIN_SECRET},
    )
    assert r.status_code == 201, f"Create failed: {r.text}"
    return r.json()


# ── GET /active ───────────────────────────────────────────────────────────────

class TestGetActiveNotifications:
    async def test_returns_empty_when_no_notifications(self, client):
        r = await client.get("/api/notifications/active")
        assert r.status_code == 200
        assert r.json() == []

    async def test_returns_active_notification(self, client, db_session):
        await _create_notification_in_db(db_session, title="Welcome!")
        r = await client.get("/api/notifications/active")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        titles = [n["title"] for n in data]
        assert "Welcome!" in titles

    async def test_excludes_inactive_notification(self, client, db_session):
        await _create_notification_in_db(
            db_session, title="Hidden", is_active=False
        )
        r = await client.get("/api/notifications/active")
        assert r.status_code == 200
        titles = [n["title"] for n in r.json()]
        assert "Hidden" not in titles

    async def test_excludes_expired_notification(self, client, db_session):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await _create_notification_in_db(
            db_session, title="Expired Alert", expires_at=past
        )
        r = await client.get("/api/notifications/active")
        assert r.status_code == 200
        titles = [n["title"] for n in r.json()]
        assert "Expired Alert" not in titles

    async def test_includes_notification_before_expiry(self, client, db_session):
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        await _create_notification_in_db(
            db_session, title="Future Alert", expires_at=future
        )
        r = await client.get("/api/notifications/active")
        titles = [n["title"] for n in r.json()]
        assert "Future Alert" in titles

    async def test_plan_targeted_hidden_from_other_plan(self, client, db_session):
        await _create_notification_in_db(
            db_session,
            title="Unlimited Only",
            target_plan="unlimited",
        )
        r = await client.get(
            "/api/notifications/active",
            params={"plan": "free"},
        )
        titles = [n["title"] for n in r.json()]
        assert "Unlimited Only" not in titles

    async def test_plan_targeted_shown_to_matching_plan(self, client, db_session):
        await _create_notification_in_db(
            db_session,
            title="Unlimited Only",
            target_plan="unlimited",
        )
        r = await client.get(
            "/api/notifications/active",
            params={"plan": "unlimited"},
        )
        titles = [n["title"] for n in r.json()]
        assert "Unlimited Only" in titles

    async def test_all_target_plan_shown_to_everyone(self, client, db_session):
        await _create_notification_in_db(
            db_session,
            title="Global Alert",
            target_plan="all",
        )
        for plan in ("free", "base", "unlimited", "byok"):
            r = await client.get(
                "/api/notifications/active",
                params={"plan": plan},
            )
            titles = [n["title"] for n in r.json()]
            assert "Global Alert" in titles, \
                f"Global alert should appear for plan '{plan}'"

    async def test_no_plan_param_shows_all_active(self, client, db_session):
        """Without a plan query param, all active notifications are returned."""
        await _create_notification_in_db(db_session, title="All Plans Alert")
        r = await client.get("/api/notifications/active")
        titles = [n["title"] for n in r.json()]
        assert "All Plans Alert" in titles

    async def test_response_has_required_fields(self, client, db_session):
        await _create_notification_in_db(db_session)
        r = await client.get("/api/notifications/active")
        assert r.status_code == 200
        n = r.json()[0]
        for field in ("id", "title", "message", "type", "created_at"):
            assert field in n, f"Missing field '{field}' in notification response"


# ── POST /create ──────────────────────────────────────────────────────────────

class TestCreateNotification:
    async def test_create_without_admin_secret_returns_403(self, client):
        r = await client.post("/api/notifications/create", json={
            "title": "Alert", "message": "Hello",
        })
        assert r.status_code == 403

    async def test_create_with_wrong_secret_returns_403(self, client):
        r = await client.post(
            "/api/notifications/create",
            json={"title": "Alert", "message": "Hello"},
            headers={"X-Admin-Secret": "wrong-secret"},
        )
        assert r.status_code == 403

    async def test_create_success_returns_201_with_id(self, client):
        r = await client.post(
            "/api/notifications/create",
            json={"title": "New Feature", "message": "We shipped X", "type": "info"},
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "created"
        assert "id" in data
        assert data["title"] == "New Feature"

    async def test_create_immediately_appears_in_active(self, client):
        await _create_via_api(client, title="Freshly Created")
        r = await client.get("/api/notifications/active")
        titles = [n["title"] for n in r.json()]
        assert "Freshly Created" in titles

    async def test_create_invalid_type_returns_400(self, client):
        r = await client.post(
            "/api/notifications/create",
            json={"title": "Bad", "message": "Test", "type": "invalid_type"},
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        assert r.status_code == 400

    async def test_create_warning_type_accepted(self, client):
        d = await _create_via_api(client, title="Warning Alert", type="warning")
        assert d["status"] == "created"

    async def test_create_critical_type_accepted(self, client):
        d = await _create_via_api(client, title="Critical Alert", type="critical")
        assert d["status"] == "created"

    async def test_create_with_plan_target(self, client):
        d = await _create_via_api(
            client, title="Base Users Alert", target_plan="base"
        )
        assert d["status"] == "created"

    async def test_create_persists_to_db(self, client, db_session):
        d = await _create_via_api(client, title="DB Persist Test")
        nid = d["id"]
        result = await db_session.execute(
            select(SystemNotification).where(
                SystemNotification.id == nid,
            )
        )
        n = result.scalar_one_or_none()
        assert n is not None
        assert n.title == "DB Persist Test"
        assert n.is_active is True


# ── POST /deactivate/{id} ─────────────────────────────────────────────────────

class TestDeactivateNotification:
    async def test_deactivate_success(self, client):
        d = await _create_via_api(client, title="To Deactivate")
        nid = d["id"]
        r = await client.post(
            f"/api/notifications/deactivate/{nid}",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "deactivated"

    async def test_deactivated_notification_excluded_from_active(self, client):
        d = await _create_via_api(client, title="Will Be Deactivated")
        nid = d["id"]
        await client.post(
            f"/api/notifications/deactivate/{nid}",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        r = await client.get("/api/notifications/active")
        ids = [n["id"] for n in r.json()]
        assert nid not in ids

    async def test_deactivate_without_auth_returns_403(self, client):
        d = await _create_via_api(client, title="No Auth Deactivate")
        nid = d["id"]
        r = await client.post(f"/api/notifications/deactivate/{nid}")
        assert r.status_code == 403

    async def test_deactivate_nonexistent_returns_404(self, client):
        fake_id = str(uuid4())
        r = await client.post(
            f"/api/notifications/deactivate/{fake_id}",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        assert r.status_code == 404

    async def test_deactivate_sets_is_active_false_in_db(self, client, db_session):
        d = await _create_via_api(client, title="DB Deactivate Check")
        nid = d["id"]
        await client.post(
            f"/api/notifications/deactivate/{nid}",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        await db_session.expire_all()  # refresh from DB
        result = await db_session.execute(
            select(SystemNotification).where(SystemNotification.id == nid)
        )
        n = result.scalar_one_or_none()
        assert n is not None
        assert n.is_active is False


# ── GET /list ─────────────────────────────────────────────────────────────────

class TestListNotifications:
    async def test_list_without_auth_returns_403(self, client):
        r = await client.get("/api/notifications/list")
        assert r.status_code == 403

    async def test_list_returns_all_including_inactive(self, client, db_session):
        # Create one active and one inactive directly in DB
        await _create_notification_in_db(db_session, title="Active", is_active=True)
        await _create_notification_in_db(db_session, title="Inactive", is_active=False)

        r = await client.get(
            "/api/notifications/list",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        assert r.status_code == 200
        titles = [n["title"] for n in r.json()]
        assert "Active" in titles
        assert "Inactive" in titles

    async def test_list_response_has_is_active_field(self, client, db_session):
        await _create_notification_in_db(db_session)
        r = await client.get(
            "/api/notifications/list",
            headers={"X-Admin-Secret": ADMIN_SECRET},
        )
        n = r.json()[0]
        assert "is_active" in n
        assert "created_by" in n
