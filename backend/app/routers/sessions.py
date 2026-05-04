"""
Sessions Router — session lifecycle management.

Each "session" represents one continuous use of GlassNote (one interview).
Sessions are metered — starting a session decrements the user's quota.

Endpoints:
    POST /api/sessions/start        — begin a new metered session
    POST /api/sessions/end          — close a session
    GET  /api/sessions/current      — get active session info
    GET  /api/sessions/history      — past sessions list
    GET  /api/sessions/preflight    — check quota without consuming it (BACKEND-1)

All endpoints use PostgreSQL via async SQLAlchemy sessions.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Session, UsageQuota
from app.services.auth import get_current_user
from app.services.database import get_db
from app.config import get_settings
from app.pricing_config import (
    get_plan_limits, get_session_duration, get_quota_period, PLANS,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ── Models ────────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    """Request to start a new metered session."""
    company: str = ""
    model: str = "claude-haiku-4-5-20251001"

class SessionInfo(BaseModel):
    """Session information response."""
    session_id: str
    status: str                     # active | completed | expired
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    company: str = ""
    model: str = ""
    llm_calls: int = 0
    total_tokens: int = 0


class PreflightResponse(BaseModel):
    """Quota preflight check — does NOT consume a session. (BACKEND-1)"""
    allowed: bool
    sessions_used: int
    sessions_limit: int
    sessions_remaining: int         # -1 = unlimited
    plan: str
    period: str
    reason: Optional[str] = None    # human-readable block reason if allowed=False

class SessionListResponse(BaseModel):
    """List of sessions response."""
    sessions: list[SessionInfo]
    total: int


# ── Max session duration by plan (seconds) ────────────────────────────────────

_MAX_DURATION = {
    "free":      30 * 60,      # 30 minutes
    "starter":   2 * 3600,     # 2 hours
    "pro":       4 * 3600,     # 4 hours
    "unlimited": 6 * 3600,     # 6 hours
    "payg":      2 * 3600,     # 2 hours
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_to_info(s: Session) -> SessionInfo:
    """Convert a Session ORM object to a SessionInfo response model."""
    return SessionInfo(
        session_id=str(s.id),
        status=s.status,
        started_at=s.started_at.isoformat() if s.started_at else "",
        ended_at=s.ended_at.isoformat() if s.ended_at else None,
        duration_seconds=s.duration_seconds or 0,
        company=s.company or "",
        model=s.model_used or "",
        llm_calls=s.total_llm_calls or 0,
        total_tokens=(s.total_input_tokens or 0) + (s.total_output_tokens or 0),
    )


async def _get_or_create_quota(
    db: AsyncSession, user_id: str, plan_id: str
) -> UsageQuota:
    """Get or create the current-period usage quota for a user."""
    period = get_quota_period(plan_id)   # 'lifetime' or 'YYYY-MM'

    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user_id,
            UsageQuota.period == period,
        )
    )
    quota = result.scalar_one_or_none()

    if not quota:
        quota = UsageQuota(
            user_id=user_id,
            period=period,
            sessions_limit=get_plan_limits(plan_id),
        )
        db.add(quota)
        await db.flush()

    return quota


# ── Endpoints ─────────────────────────────────────────────────────────────────

# ── Preflight endpoint (BACKEND-1) ───────────────────────────────────────────

@router.get("/preflight", response_model=PreflightResponse)
async def session_preflight(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check whether the user can start a new session WITHOUT consuming quota.

    Use this before showing the session setup UI to display remaining sessions
    and pre-validate before the actual /start call.

    Returns:
        PreflightResponse: Quota status with allowed flag and remaining count.
    """
    plan       = user.get("plan", "free")
    plan_limit = get_plan_limits(plan)
    user_id    = user["sub"]
    period     = get_quota_period(plan)

    quota = await _get_or_create_quota(db, user_id, plan)
    used  = quota.sessions_used

    # -1 = unlimited (e.g. unlimited/byok plans with sessions_per_month=9999)
    is_unlimited = (plan_limit >= 9999)
    remaining    = -1 if is_unlimited else max(0, plan_limit - used)
    allowed      = is_unlimited or (used < plan_limit)

    return PreflightResponse(
        allowed=allowed,
        sessions_used=used,
        sessions_limit=plan_limit,
        sessions_remaining=remaining,
        plan=plan,
        period=period,
        reason=(
            None if allowed else
            f"Session limit reached ({used}/{plan_limit} on '{plan}' plan). "
            "Please upgrade your plan to continue."
        ),
    )


@router.post("/start", response_model=SessionInfo)
async def start_session(
    req: StartSessionRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new metered interview session.

    Validates the user's quota before allowing the session. If the user
    has exceeded their plan's session limit, returns 402 Payment Required
    with a structured JSON body for client-side routing (BACKEND-3).

    Each user can only have one active session at a time — starting a
    new session auto-closes any existing active session.

    Returns:
        SessionInfo: The newly created session.

    Raises:
        HTTPException: 402 if session quota exceeded (structured body).
    """
    settings = get_settings()
    plan = user.get("plan", "free")
    plan_limit = get_plan_limits(plan)
    is_lifetime = PLANS.get(plan, {}).get("sessions_lifetime", False)
    user_id = user["sub"]

    # Get or create quota (uses correct period key: 'lifetime' or YYYY-MM)
    quota = await _get_or_create_quota(db, user_id, plan)

    # Lifetime plans accumulate across all time; monthly plans reset each month
    used = quota.sessions_used

    if used >= plan_limit:
        # BACKEND-3: Structured 402 body for client-side routing
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error_code":         "quota_exceeded",
                "sessions_used":      used,
                "sessions_limit":     plan_limit,
                "sessions_remaining": 0,
                "plan":               plan,
                "message": (
                    f"Session limit reached ({used}/{plan_limit} sessions on '{plan}' plan). "
                    "Please upgrade your plan to continue."
                ),
                "upgrade_url": "https://glassnote.ai/dashboard/billing",
            },
        )

    # Increment session count
    quota.sessions_used += 1

    # Close any existing active session
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.status == "active",
        )
    )
    active = result.scalar_one_or_none()
    if active:
        now = datetime.now(timezone.utc)
        active.status = "completed"
        active.ended_at = now
        active.duration_seconds = int((now - active.started_at).total_seconds())

    # Create new session
    session = Session(
        user_id=user_id,
        status="active",
        company=req.company,
        model_used=req.model,
    )
    db.add(session)
    await db.flush()

    print(
        f"[session] Started — id={str(session.id)[:8]}  "
        f"user={user_id[:8]}  plan={plan}  "
        f"quota={quota.sessions_used}/{plan_limit}"
    )

    return _session_to_info(session)


@router.post("/end", response_model=SessionInfo)
async def end_session(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    End the current active session.

    Calculates final duration and marks the session as completed.

    Returns:
        SessionInfo: The completed session details.

    Raises:
        HTTPException: 404 if no active session exists.
    """
    result = await db.execute(
        select(Session).where(
            Session.user_id == user["sub"],
            Session.status == "active",
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session",
        )

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.ended_at = now
    session.duration_seconds = int((now - session.started_at).total_seconds())

    print(
        f"[session] Ended — id={str(session.id)[:8]}  "
        f"duration={session.duration_seconds}s  "
        f"calls={session.total_llm_calls}"
    )

    return _session_to_info(session)


@router.get("/current", response_model=Optional[SessionInfo])
async def get_current_session(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the user's current active session, if any.

    Returns None if no session is active.
    """
    result = await db.execute(
        select(Session).where(
            Session.user_id == user["sub"],
            Session.status == "active",
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return None

    # Calculate live duration
    duration = int((datetime.now(timezone.utc) - session.started_at).total_seconds())
    session.duration_seconds = duration

    # Check if session exceeded max duration (0 = unlimited)
    plan = user.get("plan", "free")
    max_minutes = get_session_duration(plan)  # from pricing_config — NOT hardcoded
    if max_minutes > 0:
        max_seconds = max_minutes * 60
        if duration > max_seconds:
            session.status = "expired"
            session.ended_at = datetime.now(timezone.utc)

    return _session_to_info(session)


@router.get("/history", response_model=SessionListResponse)
async def get_session_history(
    limit: int = 20,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the user's past sessions.

    Args:
        limit: Maximum number of sessions to return.

    Returns:
        SessionListResponse: List of past sessions.
    """
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user["sub"])
        .order_by(Session.started_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    items = [_session_to_info(s) for s in sessions]

    return SessionListResponse(sessions=items, total=len(items))


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session_detail(
    session_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific session by ID.

    Used by the dashboard usage page to show session detail when a row is clicked.

    Returns:
        SessionInfo: The session details.

    Raises:
        HTTPException: 404 if session not found or belongs to another user.
    """
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user["sub"],
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return _session_to_info(session)
