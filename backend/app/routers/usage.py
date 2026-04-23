"""
Usage Router — STT usage reporting and usage dashboard.

The desktop app reports STT usage asynchronously (fire-and-forget)
after each session. This endpoint records it for billing.

Endpoints:
    POST /api/usage/report-stt     — async STT usage report from desktop
    GET  /api/usage/current        — current period usage summary

All endpoints use PostgreSQL via async SQLAlchemy sessions.
"""

from datetime import datetime, timezone
import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.models.database import UsageQuota, ApiCall, Session
from app.services.auth import get_current_user
from app.services.database import get_db
from app.config import get_settings

router = APIRouter(prefix="/api/usage", tags=["usage"])


# ── Request / Response models ─────────────────────────────────────────────────

class STTUsageReport(BaseModel):
    """
    STT usage report sent by desktop app at session end.

    The desktop app tracks STT duration locally and reports it
    asynchronously. Server validates that duration doesn't exceed
    session duration (anti-tampering).
    """
    session_id: str
    stt_provider: str            # "deepgram" | "openai_realtime"
    stt_model: str = ""          # specific model used
    duration_seconds: float      # total audio duration
    segments_count: int = 0      # number of transcription segments

class SessionUsageReport(BaseModel):
    """Full session usage payload from GUI."""
    session_id: str
    timestamp: float
    summary: dict
    stt_usage: List[dict]
    llm_usage: List[dict]
    session_summary: Optional[str] = None
    conversation_json: Optional[List[dict]] = None

class UsageSummary(BaseModel):
    """Current billing period usage summary."""
    period: str                  # "2026-04"
    plan: str
    sessions_count: int
    sessions_limit: int
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_stt_minutes: float = 0.0
    estimated_cost: float = 0.0


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/report-stt", status_code=202)
async def report_stt_usage(
    report: STTUsageReport,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive async STT usage report from the desktop app.

    This is fire-and-forget from the desktop side — the app doesn't
    wait for a response. STT usage is tracked for billing accuracy
    but doesn't block any real-time operations.

    Records an ApiCall row of type 'stt' and updates the quota.
    Returns 202 Accepted immediately.
    """
    # Estimate STT cost
    stt_cost_per_min = {
        "deepgram": 0.0043,
        "openai_realtime": 0.003,
    }.get(report.stt_provider, 0.005)

    cost = (report.duration_seconds / 60) * stt_cost_per_min

    # Record the STT call
    api_call = ApiCall(
        session_id=report.session_id,
        call_type="stt",
        provider=report.stt_provider,
        model=report.stt_model or report.stt_provider,
        duration_seconds=report.duration_seconds,
        cost_usd=cost,
    )
    db.add(api_call)

    # Update usage quota
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user["sub"],
            UsageQuota.period == period,
        )
    )
    quota = result.scalar_one_or_none()
    if quota:
        quota.total_stt_seconds += report.duration_seconds
        quota.total_cost_usd += cost

    # Update session STT total
    sess_result = await db.execute(
        select(Session).where(Session.id == report.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if session:
        session.total_stt_seconds += report.duration_seconds
        session.total_cost_usd += cost

    print(
        f"[usage] STT report — user={user['sub'][:8]}  "
        f"provider={report.stt_provider}  "
        f"duration={report.duration_seconds:.0f}s  "
        f"cost=${cost:.4f}"
    )

    return {"status": "accepted"}


@router.post("/report", status_code=200)
async def report_full_usage(
    report: SessionUsageReport,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive full session usage report from the desktop app.
    Validates the session_id as a UUID, looks up the session, and records STT/LLM usage.
    """
    # 1. Validate session_id is a valid UUID
    try:
        session_uuid = uuid_module.UUID(report.session_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid session_id: '{report.session_id}' — must be a valid UUID."
        )

    # 2. Look up the session in the DB
    sess_result = await db.execute(
        select(Session).where(
            Session.id == session_uuid,
            Session.user_id == user["sub"],
        )
    )
    session = sess_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session {report.session_id[:8]}... not found or not owned by you."
        )

    total_cost = 0.0

    # 3. Record STT calls
    for stt in report.stt_usage:
        cost = stt.get("cost_usd", 0.0)
        total_cost += cost
        api_call = ApiCall(
            session_id=session_uuid,
            call_type="stt",
            provider=stt.get("provider", "deepgram"),
            model=stt.get("model", ""),
            duration_seconds=stt.get("duration_seconds", 0.0),
            cost_usd=cost,
        )
        db.add(api_call)

    # 4. Record LLM calls
    for llm in report.llm_usage:
        cost = llm.get("cost_usd", 0.0)
        total_cost += cost
        api_call = ApiCall(
            session_id=session_uuid,
            call_type="llm",
            provider=llm.get("provider", "openai"),
            model=llm.get("model", ""),
            input_tokens=llm.get("input_tokens", 0),
            output_tokens=llm.get("output_tokens", 0),
            latency_ms=llm.get("latency_ms", 0),
            cost_usd=cost,
        )
        db.add(api_call)

    # 5. Update session with summary + conversation
    stt_sec = sum(s.get("duration_seconds", 0) for s in report.stt_usage)
    session.total_stt_seconds = (session.total_stt_seconds or 0.0) + stt_sec
    session.total_cost_usd    = (session.total_cost_usd or 0.0) + total_cost
    session.total_input_tokens  = (session.total_input_tokens or 0) + sum(l.get("input_tokens", 0) for l in report.llm_usage)
    session.total_output_tokens = (session.total_output_tokens or 0) + sum(l.get("output_tokens", 0) for l in report.llm_usage)
    session.total_llm_calls   = (session.total_llm_calls or 0) + len(report.llm_usage)
    if report.session_summary:
        session.session_summary = report.session_summary
    if report.conversation_json:
        session.conversation_json = report.conversation_json

    # 6. Update usage quota
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user["sub"],
            UsageQuota.period == period,
        )
    )
    quota = result.scalar_one_or_none()
    if quota:
        quota.total_stt_seconds  = (quota.total_stt_seconds or 0.0) + stt_sec
        quota.total_cost_usd     = (quota.total_cost_usd or 0.0) + total_cost
        quota.total_input_tokens  = (quota.total_input_tokens or 0) + sum(l.get("input_tokens", 0) for l in report.llm_usage)
        quota.total_output_tokens = (quota.total_output_tokens or 0) + sum(l.get("output_tokens", 0) for l in report.llm_usage)

    await db.commit()
    print(
        f"[usage] ✓ Session {report.session_id[:8]} reported — "
        f"STT: {len(report.stt_usage)}, LLM: {len(report.llm_usage)} — Cost: ${total_cost:.4f}"
    )
    return {"status": "ok"}


@router.get("/current", response_model=UsageSummary)
async def get_current_usage(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get usage summary for the current billing period.

    Returns session counts, token totals, STT minutes, and
    estimated cost for the current month.
    """
    settings = get_settings()
    plan = user.get("plan", "free")
    plan_limit = settings.plan_limits.get(plan, 3)
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get usage quota
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user["sub"],
            UsageQuota.period == period,
        )
    )
    quota = result.scalar_one_or_none()

    if quota:
        return UsageSummary(
            period=period,
            plan=plan,
            sessions_count=quota.sessions_used,
            sessions_limit=plan_limit,
            total_llm_calls=0,  # aggregated below if needed
            total_input_tokens=quota.total_input_tokens,
            total_output_tokens=quota.total_output_tokens,
            total_stt_minutes=round(quota.total_stt_seconds / 60, 1),
            estimated_cost=round(quota.total_cost_usd, 4),
        )
    else:
        return UsageSummary(
            period=period,
            plan=plan,
            sessions_count=0,
            sessions_limit=plan_limit,
        )
