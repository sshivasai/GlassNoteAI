"""
pricing_config.py — Single Source of Truth for GlassNote Pricing.

⚠️  THIS FILE IS A COPY. The canonical source is GUI/pricing_config.py
     The Dockerfile copies it here automatically for production builds.
     To change pricing: edit GUI/pricing_config.py then copy here.

Plans:
    free       — $0, 5 lifetime sessions, 30 min each, basic models only
    base       — $29/mo, 15 sessions/mo, 1 hour each, mid-tier models
    unlimited  — $49/mo, unlimited sessions, unlimited duration, all models
    byok       — $0 (FREE), unlimited sessions, all models, user's own API keys
"""

from datetime import datetime, timezone

# ── All available models ──────────────────────────────────────────────────────

ALL_MODELS = [
    ("Claude Opus 4.5  [Anthropic — Best]",     "anthropic", "claude-opus-4-5"),
    ("Claude Sonnet 4.5  [Anthropic — Fast]",   "anthropic", "claude-sonnet-4-5"),
    ("Claude Haiku 4.5  [Anthropic — Fastest]", "anthropic", "claude-haiku-4-5"),
    ("GPT-4o  [OpenAI — Best]",                 "openai",    "gpt-4o"),
    ("GPT-4o Mini  [OpenAI — Fast]",            "openai",    "gpt-4o-mini"),
    ("GPT-4.1  [OpenAI]",                       "openai",    "gpt-4.1"),
    ("GPT-4.1 Mini  [OpenAI — Fast]",           "openai",    "gpt-4.1-mini"),
    ("GPT-4 Turbo  [OpenAI]",                   "openai",    "gpt-4-turbo"),
    ("o1  [OpenAI — Reasoning]",                "openai",    "o1"),
    ("o1 Mini  [OpenAI — Reasoning Fast]",      "openai",    "o1-mini"),
    ("GPT-5.4 Mini  [OpenAI — Fast]",          "openai",    "gpt-5.4-mini"),
    ("GPT-5.4  [OpenAI — Best]",               "openai",    "gpt-5.4"),
    ("GPT-5.4 Nano  [OpenAI — Ultra Fast]",    "openai",    "gpt-5.4-nano"),
    ("GPT-4.1 Nano  [OpenAI — Ultra Fast]",    "openai",    "gpt-4.1-nano"),
    ("Llama 3.1 8B  [Cerebras — Ultra Fast]",   "cerebras",  "llama3.1-8b"),
    ("GPT-OSS 120B  [Cerebras — Fast]",         "cerebras",  "gpt-oss-120b"),
]

_BASIC_MODEL_IDS = {
    "claude-haiku-4-5",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-5.4-nano",
    "llama-3.2-1b-instant",
    "llama3.1-8b",
}

_STANDARD_MODEL_IDS = _BASIC_MODEL_IDS | {
    "claude-sonnet-4-5",
    "gpt-4o",
    "gpt-4.1",
    "gpt-4-turbo",
    "gpt-5.4-mini",
    "gpt-oss-120b",
}

_ALL_MODEL_IDS = _STANDARD_MODEL_IDS | {
    "claude-opus-4-5",
    "o1",
    "o1-mini",
    "gpt-5.4",
}

_BASIC_STT = ["deepgram"]
_ALL_STT   = ["deepgram", "openai_realtime"]


# ── Plan Definitions ──────────────────────────────────────────────────────────

PLANS = {
    "free": {
        "display_name":             "Free",
        "tagline":                  "Try GlassNote risk-free",
        "price_monthly":            0,
        "price_display":            "Free",
        "price_type":               "free",
        "stripe_price_id":          None,
        # BUG-8 fix: free plan has 5 LIFETIME sessions (not monthly).
        # sessions_per_month is kept for backward compat but the canonical
        # limit is sessions_lifetime_limit when sessions_lifetime=True.
        # Backend quota uses get_plan_limits() → sessions_per_month (= 5).
        # get_quota_period() returns "lifetime" so the quota row is shared
        # across all months — the 5-session cap is enforced correctly.
        "sessions_per_month":       5,
        "sessions_lifetime":        True,
        "session_duration_minutes": 30,
        "allowed_model_ids":        _BASIC_MODEL_IDS,
        "features": {
            "smart_answering":    False,
            "auto_capture":       False,
            "prompt_caching":     False,
            "response_cache":     True,
            "auto_model_routing": False,
            "http2_pooling":      True,
            "priority_support":   False,
        },
        "stt_providers":  _BASIC_STT,
        "byok_allowed":   False,
        "badge_color":    "#888888",
        "sort_order":     0,
    },
    "base": {
        "display_name":             "Base",
        "tagline":                  "For regular meeting prep",
        "price_monthly":            29_00,
        "price_display":            "$29/mo",
        "price_type":               "subscription",
        "stripe_price_id":          "price_base_monthly",
        "sessions_per_month":       15,
        "sessions_lifetime":        False,
        "session_duration_minutes": 60,
        "allowed_model_ids":        _STANDARD_MODEL_IDS,
        "features": {
            "smart_answering":    True,
            "auto_capture":       True,
            "prompt_caching":     True,
            "response_cache":     True,
            "auto_model_routing": True,
            "http2_pooling":      True,
            "priority_support":   False,
        },
        "stt_providers":  _BASIC_STT,
        "byok_allowed":   False,
        "badge_color":    "#4f8ef7",
        "sort_order":     1,
    },
    "unlimited": {
        "display_name":             "Unlimited",
        "tagline":                  "All features, all models, no limits",
        "price_monthly":            49_00,
        "price_display":            "$49/mo",
        "price_type":               "subscription",
        "stripe_price_id":          "price_unlimited_monthly",
        "sessions_per_month":       9999,
        "sessions_lifetime":        False,
        "session_duration_minutes": 0,
        "allowed_model_ids":        _ALL_MODEL_IDS,
        "features": {
            "smart_answering":    True,
            "auto_capture":       True,
            "prompt_caching":     True,
            "response_cache":     True,
            "auto_model_routing": True,
            "http2_pooling":      True,
            "priority_support":   True,
        },
        "stt_providers":  _ALL_STT,
        "byok_allowed":   False,
        "badge_color":    "#f59e0b",
        "sort_order":     2,
    },
    "byok": {
        "display_name":             "BYOK",
        "tagline":                  "Use your own API keys forever",
        "price_monthly":            0,          # FIX: BYOK is now FREE (was $99)
        "price_display":            "Free",     # FIX: Show "Free" not "$99 forever"
        "price_type":               "free",     # FIX: Changed from "one_time" to "free"
        "stripe_price_id":          None,       # FIX: No Stripe (was "price_byok_lifetime")
        "sessions_per_month":       9999,
        "sessions_lifetime":        True,       # FIX: Changed to True (lifetime like free plan)
        "session_duration_minutes": 0,
        "allowed_model_ids":        _ALL_MODEL_IDS,
        "features": {
            "smart_answering":    True,
            "auto_capture":       True,
            "prompt_caching":     True,
            "response_cache":     True,
            "auto_model_routing": True,
            "http2_pooling":      True,
            "priority_support":   True,
        },
        "stt_providers":  _ALL_STT,
        "byok_allowed":   True,
        "badge_color":    "#10b981",
        "sort_order":     3,
    },
}


# ── Helper functions ──────────────────────────────────────────────────────────

def get_plan(plan_id: str) -> dict:
    """Get a plan dict by ID. Falls back to 'free' for unknown plan IDs."""
    return PLANS.get(plan_id, PLANS["free"])

def get_plan_limits(plan_id: str) -> int:
    return get_plan(plan_id)["sessions_per_month"]

def get_session_duration(plan_id: str) -> int:
    return get_plan(plan_id)["session_duration_minutes"]

def get_allowed_models(plan_id: str) -> list:
    allowed_ids = get_plan(plan_id)["allowed_model_ids"]
    return [m for m in ALL_MODELS if m[2] in allowed_ids]

def is_model_allowed(plan_id: str, model_id: str) -> bool:
    return model_id in get_plan(plan_id)["allowed_model_ids"]

def is_feature_enabled(plan_id: str, feature: str) -> bool:
    return get_plan(plan_id).get("features", {}).get(feature, False)

def is_stt_allowed(plan_id: str, stt_provider: str) -> bool:
    return stt_provider in get_plan(plan_id).get("stt_providers", [])

def get_stripe_price_map() -> dict:
    return {pid: p["stripe_price_id"] for pid, p in PLANS.items() if p["stripe_price_id"]}

def get_one_time_plans() -> set:
    """
    Return plan IDs that require one-time payment.

    FIX: BYOK is now free (price_type="free"), so this returns empty set.
    Kept for backward compatibility with billing code.
    """
    return {pid for pid, p in PLANS.items() if p["price_type"] == "one_time"}

def get_plan_from_price(stripe_price_id: str) -> str:
    for pid, p in PLANS.items():
        if p["stripe_price_id"] == stripe_price_id:
            return pid
    return "free"

def get_all_plan_limits() -> dict:
    return {pid: p["sessions_per_month"] for pid, p in PLANS.items()}

def get_quota_period(plan_id: str) -> str:
    """Return 'lifetime' for lifetime plans, else current YYYY-MM."""
    plan = get_plan(plan_id)
    if plan.get("sessions_lifetime", False):
        return "lifetime"
    return datetime.now(timezone.utc).strftime("%Y-%m")

def format_duration(minutes: int) -> str:
    if minutes == 0:
        return "Unlimited"
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining = minutes % 60
    if remaining:
        return f"{hours}h {remaining}m"
    return f"{hours}h"

def format_sessions(count: int) -> str:
    if count >= 9999:
        return "Unlimited"
    return str(count)
