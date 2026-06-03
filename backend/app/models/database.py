"""
Database models for GlassNote backend.

Tables:
    users               — Registered users with plan info, device binding, email verification
    sessions            — Metered interview sessions
    api_calls           — Individual LLM/STT API call records
    usage_quotas        — Monthly usage counters per user
    email_otps          — OTP codes for email verification during signup
    system_notifications — Broadcast messages pushed to all desktop clients
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, Index, JSON, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all GlassNote models."""
    pass


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    """
    A registered GlassNote user.

    Attributes:
        id:                  Unique user ID (UUID).
        email:               User's email address (unique).
        hashed_password:     bcrypt-hashed password.
        plan:                Current subscription plan ID (from pricing_config).
        plan_expires_at:     When the current paid plan expires (null = free/lifetime/no expiry).
        byok_enabled:        Whether BYOK (Bring Your Own Keys) feature is enabled.
        stripe_customer_id:  Stripe customer ID for billing.
        is_active:           Whether the account is active (False on payment failure).
        is_verified:         Whether the email has been OTP-verified.
        bound_device_id:     Hardware fingerprint of the locked device (null = no lock).
        device_unlink_count: How many times the device has been unlinked this month.
        device_unlink_reset_at: When to reset the unlink counter.
        created_at:          Account creation timestamp.
    """
    __tablename__ = "users"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email                   = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password         = Column(String(255), nullable=False)
    first_name              = Column(String(100), nullable=True, default="")
    last_name               = Column(String(100), nullable=True, default="")
    auth_provider           = Column(String(20), nullable=False, default="email")  # email | google
    google_id               = Column(String(255), nullable=True, unique=True, index=True)
    plan                    = Column(String(30), nullable=False, default="free")
    plan_expires_at         = Column(DateTime(timezone=True), nullable=True)   # None = free / no expiry
    stripe_customer_id      = Column(String(255), nullable=True)
    byok_enabled            = Column(Boolean, default=False, nullable=False)    # BYOK toggle (any plan)
    is_active               = Column(Boolean, default=True)
    is_verified             = Column(Boolean, default=False)
    bound_device_id         = Column(String(128), nullable=True)
    device_unlink_count     = Column(Integer, default=0)
    device_unlink_reset_at  = Column(DateTime(timezone=True), nullable=True)
    created_at              = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    sessions     = relationship("Session",      back_populates="user", lazy="dynamic")
    usage_quotas = relationship("UsageQuota",   back_populates="user", lazy="dynamic")
    email_otps   = relationship("EmailOTP",     back_populates="user", lazy="dynamic",
                                cascade="all, delete-orphan")


# ── Sessions ──────────────────────────────────────────────────────────────────

class Session(Base):
    """
    A metered interview session.

    Each session represents one continuous use of GlassNote (one interview).
    Sessions have a maximum duration (enforced by plan tier) and track
    all API calls made within them.

    Attributes:
        id:                  Unique session ID (UUID).
        user_id:             Owner user ID.
        started_at:          Session start timestamp.
        ended_at:            Session end timestamp (null if active).
        duration_seconds:    Total session duration.
        status:              Session lifecycle state (active | completed | expired).
        company:             Target company (for analytics).
        model_used:          Primary LLM model used.
        total_llm_calls:     Count of LLM API calls.
        total_input_tokens:  Sum of input tokens across all calls.
        total_output_tokens: Sum of output tokens across all calls.
        total_stt_seconds:   Total STT audio duration.
        total_cost_usd:      Our cost for this session.
    """
    __tablename__ = "sessions"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    started_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at            = Column(DateTime(timezone=True), nullable=True)
    duration_seconds    = Column(Integer, default=0)
    status              = Column(String(20), default="active")  # active | completed | expired
    company             = Column(String(255), nullable=True)
    model_used          = Column(String(50), nullable=True)
    total_llm_calls     = Column(Integer, default=0)
    total_input_tokens  = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_stt_seconds   = Column(Float, default=0.0)
    total_cost_usd      = Column(Float, default=0.0)
    session_summary     = Column(Text, nullable=True)
    conversation_json   = Column(JSON, nullable=True)

    # Relationships
    user      = relationship("User",    back_populates="sessions")
    api_calls = relationship("ApiCall", back_populates="session", lazy="dynamic")

    __table_args__ = (
        Index("idx_sessions_user_status", "user_id", "status"),
    )


# ── API Calls ─────────────────────────────────────────────────────────────────

class ApiCall(Base):
    """
    A single API call made through the proxy.

    Records every LLM and STT call for usage tracking and billing.
    Created asynchronously after the response stream completes
    to avoid adding latency to the proxy response.

    Attributes:
        id:               Unique call ID (UUID).
        session_id:       Parent session ID.
        call_type:        Type of call ('llm' or 'stt').
        provider:         API provider ('anthropic', 'openai', 'deepgram').
        model:            Specific model used.
        input_tokens:     Input token count (LLM only).
        output_tokens:    Output token count (LLM only).
        duration_seconds: Audio duration (STT only).
        latency_ms:       Response latency in milliseconds.
        cost_usd:         Estimated cost of this call.
        cached:           Whether response was served from cache.
        created_at:       Call timestamp.
    """
    __tablename__ = "api_calls"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id       = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    call_type        = Column(String(10), nullable=False)   # llm | stt
    provider         = Column(String(20), nullable=False)   # anthropic | openai | deepgram
    model            = Column(String(50), nullable=False)
    input_tokens     = Column(Integer, default=0)
    output_tokens    = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    latency_ms       = Column(Integer, default=0)
    cost_usd         = Column(Float, default=0.0)
    cached           = Column(Boolean, default=False)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("Session", back_populates="api_calls")

    __table_args__ = (
        Index("idx_api_calls_session_type", "session_id", "call_type"),
    )


# ── Usage Quotas ──────────────────────────────────────────────────────────────

class UsageQuota(Base):
    """
    Monthly usage quota for a user.

    Tracks sessions used vs. plan limit for the current billing period.
    A new row is created for each month. For lifetime plans (e.g., Free, BYOK),
    the period is "lifetime" so it never resets.

    Attributes:
        id:                  Unique quota ID (UUID).
        user_id:             Owner user ID.
        period:              Billing period in YYYY-MM format (or "lifetime").
        sessions_used:       Number of sessions started this period.
        sessions_limit:      Maximum sessions allowed by plan.
        total_input_tokens:  Sum of all input tokens this period.
        total_output_tokens: Sum of all output tokens this period.
        total_stt_seconds:   Sum of all STT audio seconds this period.
        total_cost_usd:      Our total cost this period.
    """
    __tablename__ = "usage_quotas"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    period              = Column(String(10), nullable=False)  # "2026-04" or "lifetime"
    sessions_used       = Column(Integer, default=0)
    sessions_limit      = Column(Integer, default=5)
    total_input_tokens  = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_stt_seconds   = Column(Float, default=0.0)
    total_cost_usd      = Column(Float, default=0.0)

    # Relationships
    user = relationship("User", back_populates="usage_quotas")

    __table_args__ = (
        Index("idx_usage_quotas_user_period", "user_id", "period", unique=True),
    )


# ── Email OTPs ────────────────────────────────────────────────────────────────

class EmailOTP(Base):
    """
    One-time password for email verification during signup.

    A new OTP is created at registration and must be verified before
    the user receives a JWT token. Expired and used OTPs are cleaned up.

    Attributes:
        id:         Unique OTP ID (UUID).
        user_id:    User the OTP belongs to.
        code:       6-digit OTP code.
        expires_at: Timestamp after which the OTP is invalid (10 min TTL).
        used:       Whether this OTP has been successfully used.
        attempts:   Number of failed verification attempts (max 5).
        created_at: OTP creation timestamp.
    """
    __tablename__ = "email_otps"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    code       = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used       = Column(Boolean, default=False)
    attempts   = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="email_otps")

    __table_args__ = (
        Index("idx_email_otps_user", "user_id"),
    )


# ── System Notifications ──────────────────────────────────────────────────────

class SystemNotification(Base):
    """
    Broadcast notification pushed to all desktop GUI clients.

    Admins create notifications via the backend admin endpoint.
    Desktop clients poll GET /api/notifications/active on startup
    and every hour. Dismissed notification IDs are stored locally.

    Attributes:
        id:          Unique notification ID (UUID).
        title:       Short notification title.
        message:     Full notification body.
        type:        Severity level ('info', 'warning', 'critical').
        is_active:   Whether the notification is currently being pushed.
        target_plan: If set, only shown to users on this plan ('all' = everyone).
        created_at:  Creation timestamp.
        expires_at:  Optional — notification stops showing after this time.
        created_by:  Admin email who created this notification.
    """
    __tablename__ = "system_notifications"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title        = Column(String(255), nullable=False)
    message      = Column(Text, nullable=False)
    type         = Column(String(20), nullable=False, default="info")  # info | warning | critical
    is_active    = Column(Boolean, default=True)
    target_plan  = Column(String(30), nullable=True)  # None/'all' = everyone, else specific plan ID
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at   = Column(DateTime(timezone=True), nullable=True)
    created_by   = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_system_notifications_active", "is_active"),
    )
