"""
Notifications Router — system-wide broadcast notifications.

Admins publish alerts via POST /api/notifications/create (requires admin secret).
Desktop clients poll GET /api/notifications/active on startup and every hour.

Endpoints:
    GET  /api/notifications/active   — fetch active notifications (public, JWT optional)
    POST /api/notifications/create   — publish a new notification (admin only)
    POST /api/notifications/deactivate/{id} — deactivate a notification (admin only)
    GET  /api/notifications/list     — list all notifications (admin only)
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import SystemNotification
from app.services.database import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── Auth guard for admin endpoints ────────────────────────────────────────────

async def _require_admin(x_admin_secret: str = Header(default="")):
    """
    Simple admin authentication via a shared secret header.

    In production, replace with a full role-based access control system.
    Set ADMIN_SECRET env var on the backend; never commit it.
    """
    settings = get_settings()
    admin_secret = getattr(settings, "admin_secret", "")
    if not admin_secret or x_admin_secret != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )


# ── Request / Response models ─────────────────────────────────────────────────

class NotificationCreate(BaseModel):
    """Payload to create a new system notification."""
    title:       str
    message:     str
    type:        str = "info"          # info | warning | critical
    target_plan: Optional[str] = None  # None or 'all' = everyone; else plan ID
    expires_at:  Optional[datetime] = None
    created_by:  Optional[str] = None


class NotificationOut(BaseModel):
    """Notification response model."""
    id:          str
    title:       str
    message:     str
    type:        str
    target_plan: Optional[str]
    created_at:  str
    expires_at:  Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_active(n: SystemNotification) -> bool:
    """Check whether a notification is still relevant (not expired)."""
    if not n.is_active:
        return False
    if n.expires_at:
        now = datetime.now(timezone.utc)
        expires = n.expires_at.replace(tzinfo=timezone.utc)
        if now > expires:
            return False
    return True


def _to_out(n: SystemNotification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        title=n.title,
        message=n.message,
        type=n.type,
        target_plan=n.target_plan,
        created_at=n.created_at.isoformat(),
        expires_at=n.expires_at.isoformat() if n.expires_at else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/active", response_model=list[NotificationOut])
async def get_active_notifications(
    plan: Optional[str] = None,  # query param: filter by user's plan
    db:   AsyncSession = Depends(get_db),
):
    """
    Fetch active system notifications.

    Called by the desktop GUI on startup and every hour (polling).
    Optionally filtered by the user's plan so plan-targeted alerts work.

    Query params:
        plan: The user's current plan ID (optional). Used to filter
              plan-targeted notifications.

    Returns:
        List of active NotificationOut objects.
    """
    result = await db.execute(
        select(SystemNotification)
        .where(SystemNotification.is_active == True)
        .order_by(SystemNotification.created_at.desc())
    )
    all_notifications = result.scalars().all()

    # Filter: only return notifications targeted at this user's plan (or 'all')
    active = []
    for n in all_notifications:
        if not _is_active(n):
            continue
        # target_plan == None or 'all' → shown to everyone
        if n.target_plan and n.target_plan != "all" and plan:
            if n.target_plan != plan:
                continue
        active.append(_to_out(n))

    return active


@router.post("/create", status_code=201)
async def create_notification(
    req:   NotificationCreate,
    db:    AsyncSession = Depends(get_db),
    _:     None = Depends(_require_admin),
):
    """
    Publish a new system notification (admin only).

    Requires the X-Admin-Secret header to match the ADMIN_SECRET env var.

    Returns:
        The created notification's ID.
    """
    if req.type not in ("info", "warning", "critical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="type must be one of: info, warning, critical",
        )

    notification = SystemNotification(
        title=req.title,
        message=req.message,
        type=req.type,
        is_active=True,
        target_plan=req.target_plan or None,
        expires_at=req.expires_at,
        created_by=req.created_by,
    )
    db.add(notification)
    await db.flush()

    nid = str(notification.id)
    print(f"[notifications] Created notification {nid}: '{req.title}' "
          f"(type={req.type}, target={req.target_plan or 'all'})")

    return {
        "status": "created",
        "id": nid,
        "title": req.title,
    }


@router.post("/deactivate/{notification_id}")
async def deactivate_notification(
    notification_id: UUID,
    db:  AsyncSession = Depends(get_db),
    _:   None = Depends(_require_admin),
):
    """
    Deactivate (hide) a notification (admin only).

    The notification is not deleted from the database for audit purposes.
    """
    result = await db.execute(
        select(SystemNotification).where(SystemNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notification.is_active = False
    print(f"[notifications] Deactivated notification {notification_id}")

    return {"status": "deactivated", "id": str(notification_id)}


@router.get("/list")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    _:  None = Depends(_require_admin),
):
    """
    List all notifications (active and inactive) for admin management.
    """
    result = await db.execute(
        select(SystemNotification).order_by(SystemNotification.created_at.desc())
    )
    all_n = result.scalars().all()
    return [
        {
            "id":          str(n.id),
            "title":       n.title,
            "message":     n.message,
            "type":        n.type,
            "is_active":   n.is_active,
            "target_plan": n.target_plan,
            "created_at":  n.created_at.isoformat(),
            "expires_at":  n.expires_at.isoformat() if n.expires_at else None,
            "created_by":  n.created_by,
        }
        for n in all_n
    ]
