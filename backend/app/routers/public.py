"""
Public Router — unauthenticated endpoints for the marketing website.

These endpoints require NO authentication and are served with aggressive
CORS so the GlassNote website can fetch live data.

Endpoints:
    GET /api/public/pricing         — live pricing plans from pricing_config.py
    GET /api/public/pricing/config  — full PLANS dict for GUI dynamic loading
    GET /api/public/testimonials    — curated user testimonials (managed in DB or static)
"""

from fastapi import APIRouter
from typing import Optional

from app.pricing_config import PLANS, ALL_MODELS

router = APIRouter(prefix="/api/public", tags=["public"])


# ── Static testimonials ───────────────────────────────────────────────────────
# These are managed here (single source of truth) and served live to the
# website. No hardcoding on the frontend. Add/edit testimonials here and
# redeploy — website updates immediately.

_TESTIMONIALS = [
    {
        "text": (
            "I used GlassNote for my Amazon loop and it was incredible. "
            "The overlay answered system design questions in real-time while "
            "being completely invisible on Chime. Got the offer."
        ),
        "author": "Alex K.",
        "role": "Software Engineer → Amazon",
        "initial": "A",
        "plan": "unlimited",
        "stars": 5,
    },
    {
        "text": (
            "The speed is unreal. Claude Opus starts answering before I even "
            "finish reading the question. The transparent overlay feels like "
            "having a second brain on screen."
        ),
        "author": "Sarah M.",
        "role": "SDE II → Google",
        "initial": "S",
        "plan": "unlimited",
        "stars": 5,
    },
    {
        "text": (
            "BYOK mode is genius — I use my own Anthropic key so there's zero "
            "platform fee. The auto model routing picks the right model every time."
        ),
        "author": "Raj P.",
        "role": "Full Stack → Microsoft",
        "initial": "R",
        "plan": "byok",
        "stars": 5,
    },
    {
        "text": (
            "The Base plan is perfect for my weekly practice sessions. "
            "15 sessions a month is more than enough, and the quality of "
            "answers has genuinely improved my system design explanations."
        ),
        "author": "James T.",
        "role": "Backend Engineer → Meta",
        "initial": "J",
        "plan": "base",
        "stars": 5,
    },
    {
        "text": (
            "Started on the Free plan to test it out. The 5 sessions were "
            "enough to convince me — upgraded to Unlimited the same day. "
            "Best investment for interview prep I've made."
        ),
        "author": "Priya S.",
        "role": "ML Engineer → Stripe",
        "initial": "P",
        "plan": "free",
        "stars": 5,
    },
    {
        "text": (
            "What surprised me most is how invisible it is. Screenshare on "
            "Zoom, Teams, Google Meet — nobody ever notices. Passed my "
            "FAANG onsite after struggling for months."
        ),
        "author": "Chen W.",
        "role": "SWE → Apple",
        "initial": "C",
        "plan": "unlimited",
        "stars": 5,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_plan(plan_id: str, plan: dict) -> dict:
    """
    Serialize a pricing_config plan dict into a JSON-safe response dict.

    Converts Python sets (allowed_model_ids) to sorted lists so they
    serialize cleanly. Exposes only what the frontend needs.
    """
    allowed_ids = plan.get("allowed_model_ids", set())
    allowed_models = [
        {"display_name": m[0], "provider": m[1], "model_id": m[2]}
        for m in ALL_MODELS
        if m[2] in allowed_ids
    ]

    return {
        "id":                   plan_id,
        "display_name":         plan["display_name"],
        "tagline":              plan["tagline"],
        "price_monthly":        plan["price_monthly"],      # cents (0, 2900, 4900, 9900)
        "price_display":        plan["price_display"],      # "$29/mo", "Free", etc.
        "price_type":           plan["price_type"],         # free | subscription | one_time
        "sessions_per_month":   plan["sessions_per_month"],
        "sessions_lifetime":    plan["sessions_lifetime"],
        "session_duration_min": plan["session_duration_minutes"],
        "allowed_models":       allowed_models,
        "features":             plan["features"],
        "stt_providers":        plan["stt_providers"],
        "byok_allowed":         plan["byok_allowed"],
        "badge_color":          plan["badge_color"],
        "sort_order":           plan["sort_order"],
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pricing")
async def get_pricing():
    """
    Return all pricing plans live from pricing_config.py.

    The website fetches this on page load so pricing is always in sync
    with the backend config — no hardcoding on the frontend.

    Returns:
        List of plan dicts ordered by sort_order.
    """
    plans_list = [
        _serialize_plan(pid, plan)
        for pid, plan in PLANS.items()
    ]
    # Sort by sort_order so the order is always canonical
    plans_list.sort(key=lambda p: p["sort_order"])
    return {"plans": plans_list}


@router.get("/pricing/config")
async def get_pricing_config():
    """
    Return the full PLANS dict in a format the desktop GUI can consume directly.

    This is the single source of truth for plan features, session limits,
    duration limits, and allowed models.  The GUI fetches this on startup
    and caches it locally so it never needs a bundled copy.

    The response mirrors the structure of GUI/pricing_config.py PLANS so
    the GUI can hot-swap its local dict with the server version.

    Returns:
        dict: { "plans": { plan_id: plan_dict, ... }, "all_models": [...] }
    """
    serialized = {}
    for plan_id, plan in PLANS.items():
        # Convert Python sets to sorted lists for JSON serialisation
        allowed_ids = plan.get("allowed_model_ids", set())
        serialized[plan_id] = {
            "display_name":             plan["display_name"],
            "tagline":                  plan["tagline"],
            "price_monthly":            plan["price_monthly"],
            "price_display":            plan["price_display"],
            "price_type":               plan["price_type"],
            "stripe_price_id":          plan.get("stripe_price_id"),
            "sessions_per_month":       plan["sessions_per_month"],
            "sessions_lifetime":        plan["sessions_lifetime"],
            "session_duration_minutes": plan["session_duration_minutes"],
            "allowed_model_ids":        sorted(list(allowed_ids)),
            "features":                 plan["features"],
            "stt_providers":            plan["stt_providers"],
            "byok_allowed":             plan["byok_allowed"],
            "badge_color":              plan["badge_color"],
            "sort_order":               plan["sort_order"],
        }

    all_models_list = [
        {"display_name": m[0], "provider": m[1], "model_id": m[2]}
        for m in ALL_MODELS
    ]

    return {
        "plans":      serialized,
        "all_models": all_models_list,
    }


@router.get("/testimonials")
async def get_testimonials(limit: Optional[int] = None):
    """
    Return curated user testimonials.

    Testimonials are managed in this file (backend single source of truth).
    The website calls this endpoint instead of hardcoding them.

    Query params:
        limit: Optional max number of testimonials to return.

    Returns:
        List of testimonial dicts.
    """
    result = _TESTIMONIALS
    if limit and limit > 0:
        result = result[:limit]
    return {"testimonials": result}
