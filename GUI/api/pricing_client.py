"""
api/pricing_client.py — Dynamic pricing config loader.

Fetches the full PLANS dict from the backend's /api/public/pricing/config
endpoint on app startup and caches it to disk (~/.glassnote/pricing_cache.json).

On subsequent startups the cached version is used immediately while a
background refresh runs.  If the backend is unreachable the cached version
(or the bundled fallback) is used transparently.

Usage
-----
    from api.pricing_client import get_plans, get_plan, get_all_models

    plans     = get_plans()          # dict of plan_id -> plan_dict
    free_plan = get_plan("free")     # single plan dict
    models    = get_all_models()     # list of (display_name, provider, model_id)
"""

import json
import threading
import time
from pathlib import Path
from typing import Optional

# ── Cache file ────────────────────────────────────────────────────────────────
_CACHE_FILE   = Path.home() / ".glassnote" / "pricing_cache.json"
_CACHE_MAX_AGE = 24 * 3600   # refresh if older than 24 hours

# ── In-memory state ───────────────────────────────────────────────────────────
_lock          = threading.Lock()
_plans:    dict = {}          # plan_id -> plan_dict
_all_models: list = []        # list of {"display_name", "provider", "model_id"}
_loaded    = False
_last_fetch: float = 0.0


# ── Bundled fallback (mirrors GUI/pricing_config.py) ─────────────────────────
# Used when the backend is unreachable AND no cache exists.
# Keep in sync with GUI/pricing_config.py manually as a last resort.

_FALLBACK_ALL_MODELS = [
    {"display_name": "Claude Opus 4.5  [Anthropic — Best]",     "provider": "anthropic", "model_id": "claude-opus-4-5"},
    {"display_name": "Claude Sonnet 4.5  [Anthropic — Fast]",   "provider": "anthropic", "model_id": "claude-sonnet-4-5"},
    {"display_name": "Claude Haiku 4.5  [Anthropic — Fastest]", "provider": "anthropic", "model_id": "claude-haiku-4-5"},
    {"display_name": "GPT-4o  [OpenAI — Best]",                 "provider": "openai",    "model_id": "gpt-4o"},
    {"display_name": "GPT-4o Mini  [OpenAI — Fast]",            "provider": "openai",    "model_id": "gpt-4o-mini"},
    {"display_name": "GPT-4.1  [OpenAI]",                       "provider": "openai",    "model_id": "gpt-4.1"},
    {"display_name": "GPT-4.1 Mini  [OpenAI — Fast]",           "provider": "openai",    "model_id": "gpt-4.1-mini"},
    {"display_name": "GPT-4 Turbo  [OpenAI]",                   "provider": "openai",    "model_id": "gpt-4-turbo"},
    {"display_name": "o1  [OpenAI — Reasoning]",                "provider": "openai",    "model_id": "o1"},
    {"display_name": "o1 Mini  [OpenAI — Reasoning Fast]",      "provider": "openai",    "model_id": "o1-mini"},
    {"display_name": "GPT-5.4 Mini  [OpenAI — Fast]",           "provider": "openai",    "model_id": "gpt-5.4-mini"},
    {"display_name": "GPT-5.4  [OpenAI — Best]",                "provider": "openai",    "model_id": "gpt-5.4"},
    {"display_name": "GPT-5.4 Nano  [OpenAI — Ultra Fast]",     "provider": "openai",    "model_id": "gpt-5.4-nano"},
    {"display_name": "GPT-4.1 Nano  [OpenAI — Ultra Fast]",     "provider": "openai",    "model_id": "gpt-4.1-nano"},
]

_BASIC_IDS    = {"claude-haiku-4-5","gpt-4o-mini","gpt-4.1-mini","gpt-4.1-nano","gpt-5.4-nano","llama-3.2-1b-instant"}
_STANDARD_IDS = _BASIC_IDS | {"claude-sonnet-4-5","gpt-4o","gpt-4.1","gpt-4-turbo","gpt-5.4-mini"}
_ALL_IDS      = _STANDARD_IDS | {"claude-opus-4-5","o1","o1-mini","gpt-5.4"}

_FALLBACK_PLANS = {
    "free": {
        "display_name": "Free", "tagline": "Try GlassNote risk-free",
        "price_monthly": 0, "price_display": "Free", "price_type": "free",
        "stripe_price_id": None,
        "sessions_per_month": 5, "sessions_lifetime": True,
        "session_duration_minutes": 30,
        "allowed_model_ids": sorted(_BASIC_IDS),
        "features": {"smart_answering": False, "auto_capture": False, "prompt_caching": False,
                     "response_cache": True, "auto_model_routing": False, "http2_pooling": True,
                     "priority_support": False},
        "stt_providers": ["deepgram"], "byok_allowed": False,
        "badge_color": "#888888", "sort_order": 0,
    },
    "base": {
        "display_name": "Base", "tagline": "For regular meeting prep",
        "price_monthly": 2900, "price_display": "$29/mo", "price_type": "subscription",
        "stripe_price_id": "price_base_monthly",
        "sessions_per_month": 15, "sessions_lifetime": False,
        "session_duration_minutes": 60,
        "allowed_model_ids": sorted(_STANDARD_IDS),
        "features": {"smart_answering": True, "auto_capture": True, "prompt_caching": True,
                     "response_cache": True, "auto_model_routing": True, "http2_pooling": True,
                     "priority_support": False},
        "stt_providers": ["deepgram"], "byok_allowed": False,
        "badge_color": "#4f8ef7", "sort_order": 1,
    },
    "unlimited": {
        "display_name": "Unlimited", "tagline": "All features, all models, no limits",
        "price_monthly": 4900, "price_display": "$49/mo", "price_type": "subscription",
        "stripe_price_id": "price_unlimited_monthly",
        "sessions_per_month": 9999, "sessions_lifetime": False,
        "session_duration_minutes": 0,
        "allowed_model_ids": sorted(_ALL_IDS),
        "features": {"smart_answering": True, "auto_capture": True, "prompt_caching": True,
                     "response_cache": True, "auto_model_routing": True, "http2_pooling": True,
                     "priority_support": True},
        "stt_providers": ["deepgram", "openai_realtime"], "byok_allowed": False,
        "badge_color": "#f59e0b", "sort_order": 2,
    },
    "byok": {
        "display_name": "BYOK", "tagline": "Use your own API keys forever",
        "price_monthly": 9900, "price_display": "$99 forever", "price_type": "one_time",
        "stripe_price_id": "price_byok_lifetime",
        "sessions_per_month": 9999, "sessions_lifetime": False,
        "session_duration_minutes": 0,
        "allowed_model_ids": sorted(_ALL_IDS),
        "features": {"smart_answering": True, "auto_capture": True, "prompt_caching": True,
                     "response_cache": True, "auto_model_routing": True, "http2_pooling": True,
                     "priority_support": True},
        "stt_providers": ["deepgram", "openai_realtime"], "byok_allowed": True,
        "badge_color": "#10b981", "sort_order": 3,
    },
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_from_cache() -> bool:
    """
    Load pricing config from the disk cache.

    Returns True if the cache was loaded successfully, False otherwise.
    """
    global _plans, _all_models, _loaded, _last_fetch
    try:
        if not _CACHE_FILE.exists():
            return False
        with open(_CACHE_FILE, "r") as f:
            data = json.load(f)
        fetched_at = data.get("fetched_at", 0.0)
        plans      = data.get("plans", {})
        models     = data.get("all_models", [])
        if not plans:
            return False
        with _lock:
            _plans      = plans
            _all_models = models
            _loaded     = True
            _last_fetch = fetched_at
        print(f"[pricing] ✓ Loaded from cache ({len(plans)} plans, age={int(time.time()-fetched_at)}s)")
        return True
    except Exception as e:
        print(f"[pricing] Cache load failed: {e}")
        return False


def _save_to_cache(plans: dict, all_models: list) -> None:
    """Persist fetched pricing config to disk."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump({"fetched_at": time.time(), "plans": plans, "all_models": all_models}, f, indent=2)
    except Exception as e:
        print(f"[pricing] Cache save failed (non-fatal): {e}")


def _use_fallback() -> None:
    """Load the bundled fallback plans into memory."""
    global _plans, _all_models, _loaded
    with _lock:
        _plans      = _FALLBACK_PLANS
        _all_models = _FALLBACK_ALL_MODELS
        _loaded     = True
    print("[pricing] Using bundled fallback pricing config")


def _fetch_from_backend(api_url: str) -> bool:
    """
    Fetch pricing config from /api/public/pricing/config.

    Returns True on success, False on any error.
    """
    global _plans, _all_models, _loaded, _last_fetch
    try:
        import httpx
        url = f"{api_url.rstrip('/')}/api/public/pricing/config"
        with httpx.Client(http2=True, timeout=httpx.Timeout(8.0, connect=5.0)) as c:
            r = c.get(url)
        if r.status_code != 200:
            print(f"[pricing] Backend returned {r.status_code} — skipping")
            return False
        data       = r.json()
        plans      = data.get("plans", {})
        all_models = data.get("all_models", [])
        if not plans:
            return False
        with _lock:
            _plans      = plans
            _all_models = all_models
            _loaded     = True
            _last_fetch = time.time()
        _save_to_cache(plans, all_models)
        print(f"[pricing] ✓ Fetched from backend ({len(plans)} plans)")
        return True
    except Exception as e:
        print(f"[pricing] Backend fetch failed (non-fatal): {e}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def initialise(api_url: str = "", background: bool = True) -> None:
    """
    Initialise the pricing config.

    Call this once at app startup (before any UI is shown).

    Strategy:
      1. Load from disk cache immediately (synchronous, ~1 ms)
      2. If cache is stale (>24 h) or missing, fetch from backend
         - If background=True (default): fetch runs in a daemon thread
           so startup is not blocked
         - If background=False: fetch is synchronous (used in tests)
      3. If backend unreachable and no cache: use bundled fallback

    Args:
        api_url:    GlassNote API base URL (e.g. "http://localhost:8000").
                    If empty, only cache/fallback are used.
        background: Whether to run the backend fetch in a background thread.
    """
    global _loaded

    # Step 1: try disk cache
    cache_ok  = _load_from_cache()
    cache_age = time.time() - _last_fetch if _last_fetch > 0 else float("inf")
    needs_refresh = (not cache_ok) or (cache_age > _CACHE_MAX_AGE)

    if not cache_ok:
        # No cache — use fallback immediately so callers don't block
        _use_fallback()

    if not api_url or not needs_refresh:
        return

    # Step 2: fetch from backend (refresh cache or first-time load)
    def _do_fetch():
        ok = _fetch_from_backend(api_url)
        if not ok and not cache_ok:
            # Backend failed AND no cache — fallback already set, nothing more to do
            pass

    if background:
        threading.Thread(target=_do_fetch, daemon=True, name="pricing-fetch").start()
    else:
        _do_fetch()


def ensure_loaded(api_url: str = "") -> None:
    """
    Ensure pricing config is loaded.  Synchronous version of initialise().
    Safe to call multiple times — no-op if already loaded.
    """
    if not _loaded:
        initialise(api_url=api_url, background=False)


def get_plans() -> dict:
    """Return the full plans dict {plan_id: plan_dict}."""
    if not _loaded:
        _use_fallback()
    with _lock:
        return dict(_plans)


def get_plan(plan_id: str) -> dict:
    """
    Get a single plan dict by ID.  Falls back to 'free' for unknown IDs.
    """
    plans = get_plans()
    return plans.get(plan_id, plans.get("free", _FALLBACK_PLANS["free"]))


def get_all_models() -> list:
    """
    Return all models as a list of (display_name, provider, model_id) tuples.
    """
    if not _loaded:
        _use_fallback()
    with _lock:
        return [(m["display_name"], m["provider"], m["model_id"]) for m in _all_models]


def get_allowed_models(plan_id: str) -> list:
    """
    Return list of (display_name, provider, model_id) tuples allowed for plan.
    """
    plan        = get_plan(plan_id)
    allowed_ids = set(plan.get("allowed_model_ids", []))
    # get_all_models_raw() returns tuples (display_name, provider, model_id)
    # so index access m[2] is the model_id
    return [m for m in get_all_models_raw() if m[2] in allowed_ids]


def get_all_models_raw() -> list:
    """Return all models as (display_name, provider, model_id) tuples."""
    if not _loaded:
        _use_fallback()
    with _lock:
        return [(m["display_name"], m["provider"], m["model_id"]) for m in _all_models]


def is_model_allowed(plan_id: str, model_id: str) -> bool:
    """Check if a model is allowed on the given plan."""
    plan = get_plan(plan_id)
    return model_id in set(plan.get("allowed_model_ids", []))


def is_feature_enabled(plan_id: str, feature: str) -> bool:
    """Check if a feature is enabled for the given plan."""
    plan = get_plan(plan_id)
    return plan.get("features", {}).get(feature, False)


def get_session_duration(plan_id: str) -> int:
    """Get max session duration in minutes (0 = unlimited)."""
    return get_plan(plan_id).get("session_duration_minutes", 0)


def get_plan_limits(plan_id: str) -> int:
    """Get sessions per month for a plan."""
    return get_plan(plan_id).get("sessions_per_month", 5)


def is_stt_allowed(plan_id: str, stt_provider: str) -> bool:
    """Check if an STT provider is allowed on the given plan."""
    return stt_provider in get_plan(plan_id).get("stt_providers", [])


def format_duration(minutes: int) -> str:
    """Human-readable session duration string."""
    if minutes == 0:
        return "Unlimited"
    if minutes < 60:
        return f"{minutes} min"
    hours     = minutes // 60
    remaining = minutes % 60
    if remaining:
        return f"{hours}h {remaining}m"
    return f"{hours}h"


def format_sessions(count: int) -> str:
    """Human-readable session count string."""
    if count >= 9999:
        return "Unlimited"
    return str(count)


def get_stripe_price_map() -> dict:
    """Return {plan_id: stripe_price_id} for plans with Stripe prices."""
    plans = get_plans()
    return {pid: p["stripe_price_id"] for pid, p in plans.items() if p.get("stripe_price_id")}


def get_one_time_plans() -> set:
    """Return set of plan IDs that use one-time payment."""
    plans = get_plans()
    return {pid for pid, p in plans.items() if p.get("price_type") == "one_time"}


def get_plan_from_price(stripe_price_id: str) -> str:
    """Reverse lookup: Stripe price ID → plan ID. Returns 'free' if not found."""
    plans = get_plans()
    for pid, p in plans.items():
        if p.get("stripe_price_id") == stripe_price_id:
            return pid
    return "free"


def get_quota_period(plan_id: str) -> str:
    """
    Get the quota period key for a plan.
    Returns 'lifetime' for lifetime plans, else current YYYY-MM.
    """
    from datetime import datetime, timezone
    plan = get_plan(plan_id)
    if plan.get("sessions_lifetime", False):
        return "lifetime"
    return datetime.now(timezone.utc).strftime("%Y-%m")
