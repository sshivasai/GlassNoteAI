"""
pricing_config.py — Dynamic pricing config shim for the GlassNote desktop app.

Previously this file contained a hardcoded copy of the PLANS dict that had to
be kept manually in sync with the backend.  It is now a thin shim that
delegates all calls to api.pricing_client, which:

  1. Fetches the live PLANS dict from /api/public/pricing/config on startup
  2. Caches the result to ~/.glassnote/pricing_cache.json (24-hour TTL)
  3. Falls back to a bundled copy if the backend is unreachable

This means pricing changes deployed to the backend are automatically picked up
by the desktop app on the next startup — no new app release needed.

All existing call sites (setup_ui.py, settings/ui.py, etc.) continue to work
unchanged because this module exposes the same public API as before.
"""

import os
import sys

# Ensure the GUI root is on the path so api.pricing_client can be imported
# regardless of how this module is loaded (direct import vs packaged app).
_GUI_ROOT = os.path.dirname(os.path.abspath(__file__))
if _GUI_ROOT not in sys.path:
    sys.path.insert(0, _GUI_ROOT)

from api.pricing_client import (
    get_plans,
    get_plan,
    get_all_models_raw as _get_all_models_raw,
    get_allowed_models,
    is_model_allowed,
    is_feature_enabled,
    get_session_duration,
    get_plan_limits,
    is_stt_allowed,
    format_duration,
    format_sessions,
    get_stripe_price_map,
    get_one_time_plans,
    get_plan_from_price,
    get_quota_period,
    initialise as _initialise,
)


# ── Compatibility shims ───────────────────────────────────────────────────────
# The old pricing_config.py exposed PLANS and ALL_MODELS as module-level
# constants.  Some code may import them directly.  These properties delegate
# to the dynamic loader so they always reflect the latest fetched config.

def _lazy_plans() -> dict:
    """Return the live PLANS dict (fetched or cached)."""
    return get_plans()


def _lazy_all_models() -> list:
    """Return ALL_MODELS as list of (display_name, provider, model_id) tuples."""
    return _get_all_models_raw()


# Module-level PLANS / ALL_MODELS — populated lazily on first access.
# Direct attribute access (pricing_config.PLANS) works via __getattr__.

def __getattr__(name: str):
    if name == "PLANS":
        return _lazy_plans()
    if name == "ALL_MODELS":
        return _lazy_all_models()
    raise AttributeError(f"module 'pricing_config' has no attribute {name!r}")


# ── Auto-initialise on import ─────────────────────────────────────────────────
# When this module is first imported, kick off the background pricing fetch
# so the config is ready by the time the UI needs it.
# We read the API URL from config here; if config isn't available yet we
# defer to the caller (main.py calls initialise() explicitly after config load).

def _auto_init():
    try:
        from settings import config as _cfg
        api_url = _cfg.get("glassnote_api_url", "").strip()
        if api_url:
            _initialise(api_url=api_url, background=True)
        else:
            # No API URL configured — use cache/fallback immediately
            _initialise(api_url="", background=False)
    except Exception:
        # Config not available yet — use fallback; main.py will call
        # initialise() again once config is loaded.
        _initialise(api_url="", background=False)


_auto_init()
