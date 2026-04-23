"""
GlassNote Backend — Server Configuration.

All secrets and deployment config are read from environment variables
via pydantic-settings. A .env file can be used for local development.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Server configuration loaded from environment variables.

    Attributes:
        app_name: Display name used in logs and API responses.
        debug: Enable debug mode (verbose logging, auto-reload).
        database_url: PostgreSQL connection string (asyncpg).
        jwt_secret: Secret key for signing JWT tokens. MUST be changed in production.
        jwt_algorithm: Algorithm used for JWT encoding.
        jwt_expire_minutes: Token expiry time in minutes.
        anthropic_api_key: Master Anthropic API key for proxying LLM calls.
        openai_api_key: Master OpenAI API key for proxying LLM calls.
        deepgram_api_key: Master Deepgram API key (for future STT proxy).
        stripe_secret_key: Stripe secret key for billing.
        stripe_webhook_secret: Stripe webhook signing secret.
        cors_origins: Comma-separated allowed CORS origins.
        rate_limit_per_minute: Max API calls per user per minute.
    """

    # ── App ────────────────────────────────────────────────────
    app_name: str = "GlassNote API"
    debug: bool = False

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://glassnote:glassnote@localhost:5432/glassnote"

    # ── Auth ───────────────────────────────────────────────────
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days — desktop app sessions

    # ── Provider API Keys (master — used for proxying) ─────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepgram_api_key: str = ""

    # ── Stripe ─────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ── CORS ───────────────────────────────────────────────────
    cors_origins: str = "*"

    # ── Rate Limiting ──────────────────────────────────────────
    rate_limit_per_minute: int = 60

    # ── Email (SendGrid) ───────────────────────────────────────
    sendgrid_api_key: str = ""
    from_email:       str = "[EMAIL_ADDRESS]"
    reply_email:      str = "[EMAIL_ADDRESS]"

    # ── Admin ──────────────────────────────────────────────────
    # Secret header value for admin-only endpoints.
    # Set this env var on the backend; never commit the value.
    admin_secret: str = ""

    # ── Google OAuth ───────────────────────────────────────────
    google_client_id:     str = ""  # From Google Cloud Console
    google_client_secret: str = ""  # From Google Cloud Console

    # ── Pricing (per-session, in cents) ────────────────────────
    # Used for PAYG billing and quota enforcement
    session_price_cents: int = 399  # $3.99

    # ── Plan Limits ────────────────────────────────────────────
    # Imported from pricing_config.py (single source of truth)
    # To change limits, edit pricing_config.py and redeploy.
    @property
    def plan_limits(self) -> dict:
        from app.pricing_config import get_all_plan_limits
        return get_all_plan_limits()

    @property
    def is_plan_lifetime(self) -> dict:
        """Returns dict of plan_id -> True if sessions don't reset monthly."""
        from app.pricing_config import PLANS
        return {pid: p.get("sessions_lifetime", False) for pid, p in PLANS.items()}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached server settings.

    Returns:
        Settings: Server configuration singleton.
    """
    return Settings()
