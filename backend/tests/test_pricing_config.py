"""
tests/test_pricing_config.py

Unit tests for pricing_config.py — the single source of truth for
GlassNote plans, models, and feature gates.

These are pure unit tests — no database required.

Run:
    pytest tests/test_pricing_config.py -v
"""


import pytest
from app.pricing_config import (
    PLANS,
    ALL_MODELS,
    get_plan,
    get_plan_limits,
    get_session_duration,
    get_allowed_models,
    is_model_allowed,
    is_feature_enabled,
    is_stt_allowed,
    get_stripe_price_map,
    get_one_time_plans,
    get_plan_from_price,
    get_all_plan_limits,
    get_quota_period,
    format_duration,
    format_sessions,
)


# ── Plan structure ─────────────────────────────────────────────────────────────

class TestPlanStructure:
    """All plans must have required fields and valid values."""

    REQUIRED_FIELDS = [
        "display_name", "price_monthly", "price_display", "price_type",
        "sessions_per_month", "sessions_lifetime", "session_duration_minutes",
        "allowed_model_ids", "features", "stt_providers", "byok_allowed",
        "badge_color", "sort_order",
    ]
    REQUIRED_FEATURES = [
        "smart_answering", "auto_capture", "prompt_caching",
        "response_cache", "auto_model_routing", "http2_pooling",
        "priority_support",
    ]

    def test_all_plans_present(self):
        assert set(PLANS.keys()) == {"free", "base", "unlimited", "byok"}, \
            "Expected exactly: free, base, unlimited, byok"

    @pytest.mark.parametrize("plan_id", ["free", "base", "unlimited", "byok"])
    def test_required_fields_present(self, plan_id):
        plan = PLANS[plan_id]
        for field in self.REQUIRED_FIELDS:
            assert field in plan, f"Plan '{plan_id}' missing field '{field}'"

    @pytest.mark.parametrize("plan_id", ["free", "base", "unlimited", "byok"])
    def test_required_features_present(self, plan_id):
        features = PLANS[plan_id]["features"]
        for f in self.REQUIRED_FEATURES:
            assert f in features, f"Plan '{plan_id}' missing feature '{f}'"

    def test_sort_order_is_unique(self):
        orders = [p["sort_order"] for p in PLANS.values()]
        assert len(orders) == len(set(orders)), "Duplicate sort_order values"

    @pytest.mark.parametrize("plan_id", ["free", "base", "unlimited", "byok"])
    def test_price_type_valid(self, plan_id):
        valid_types = {"free", "subscription", "one_time"}
        assert PLANS[plan_id]["price_type"] in valid_types

    def test_free_plan_has_no_stripe_id(self):
        assert PLANS["free"]["stripe_price_id"] is None

    def test_paid_plans_have_stripe_ids(self):
        for pid in ("base", "unlimited", "byok"):
            assert PLANS[pid]["stripe_price_id"], f"Plan '{pid}' missing stripe_price_id"


# ── Pricing correctness ───────────────────────────────────────────────────────

class TestPricing:
    """Verify the exact prices match product requirements."""

    def test_free_plan_price(self):
        assert PLANS["free"]["price_monthly"] == 0

    def test_base_plan_price(self):
        assert PLANS["base"]["price_monthly"] == 29_00, "Base plan should be $29/mo"

    def test_unlimited_plan_price(self):
        assert PLANS["unlimited"]["price_monthly"] == 49_00, "Unlimited should be $49/mo"

    def test_byok_plan_price(self):
        assert PLANS["byok"]["price_monthly"] == 99_00, "BYOK should be $99 one-time"

    def test_byok_is_one_time(self):
        assert PLANS["byok"]["price_type"] == "one_time"

    def test_base_unlimited_are_subscriptions(self):
        assert PLANS["base"]["price_type"]      == "subscription"
        assert PLANS["unlimited"]["price_type"] == "subscription"


# ── Session limits ────────────────────────────────────────────────────────────

class TestSessionLimits:
    """Verify session counts and durations match requirements."""

    def test_free_plan_sessions(self):
        assert get_plan_limits("free") == 5

    def test_base_plan_sessions(self):
        assert get_plan_limits("base") == 15

    def test_unlimited_sessions_effectively_unlimited(self):
        assert get_plan_limits("unlimited") >= 9999

    def test_byok_sessions_effectively_unlimited(self):
        assert get_plan_limits("byok") >= 9999

    def test_free_is_lifetime(self):
        assert PLANS["free"]["sessions_lifetime"] is True

    def test_paid_plans_not_lifetime(self):
        for pid in ("base", "unlimited", "byok"):
            assert PLANS[pid]["sessions_lifetime"] is False, \
                f"Plan '{pid}' should not be lifetime"

    def test_free_duration_30min(self):
        assert get_session_duration("free") == 30

    def test_base_duration_60min(self):
        assert get_session_duration("base") == 60

    def test_unlimited_duration_unlimited(self):
        assert get_session_duration("unlimited") == 0

    def test_byok_duration_unlimited(self):
        assert get_session_duration("byok") == 0


# ── Model access ──────────────────────────────────────────────────────────────

class TestModelAccess:
    """Verify model gating per plan."""

    # Free plan: only basic models
    def test_free_allows_haiku(self):
        assert is_model_allowed("free", "claude-haiku-4-5")

    def test_free_allows_gpt4o_mini(self):
        assert is_model_allowed("free", "gpt-4o-mini")

    def test_free_blocks_sonnet(self):
        assert not is_model_allowed("free", "claude-sonnet-4-5")

    def test_free_blocks_opus(self):
        assert not is_model_allowed("free", "claude-opus-4-5")

    # Base plan: standard tier
    def test_base_allows_sonnet(self):
        assert is_model_allowed("base", "claude-sonnet-4-5")

    def test_base_allows_gpt4o(self):
        assert is_model_allowed("base", "gpt-4o")

    def test_base_blocks_opus(self):
        assert not is_model_allowed("base", "claude-opus-4-5")

    def test_base_blocks_o1(self):
        assert not is_model_allowed("base", "o1")

    # Unlimited plan: all models
    def test_unlimited_allows_opus(self):
        assert is_model_allowed("unlimited", "claude-opus-4-5")

    def test_unlimited_allows_o1(self):
        assert is_model_allowed("unlimited", "o1")

    # BYOK: all models
    def test_byok_allows_all_models(self):
        for _, _, model_id in ALL_MODELS:
            assert is_model_allowed("byok", model_id), \
                f"BYOK should allow model '{model_id}'"

    def test_unknown_plan_falls_back_to_free_restrictions(self):
        assert not is_model_allowed("nonexistent_plan", "claude-opus-4-5")
        assert is_model_allowed("nonexistent_plan", "claude-haiku-4-5")


# ── STT providers ─────────────────────────────────────────────────────────────

class TestSTTProviders:
    def test_free_only_deepgram(self):
        assert is_stt_allowed("free", "deepgram")
        assert not is_stt_allowed("free", "openai_realtime")

    def test_base_only_deepgram(self):
        assert is_stt_allowed("base", "deepgram")
        assert not is_stt_allowed("base", "openai_realtime")

    def test_unlimited_all_stt(self):
        assert is_stt_allowed("unlimited", "deepgram")
        assert is_stt_allowed("unlimited", "openai_realtime")

    def test_byok_all_stt(self):
        assert is_stt_allowed("byok", "deepgram")
        assert is_stt_allowed("byok", "openai_realtime")


# ── Feature gates ─────────────────────────────────────────────────────────────

class TestFeatureGates:
    def test_free_no_smart_answering(self):
        assert not is_feature_enabled("free", "smart_answering")

    def test_free_no_auto_capture(self):
        assert not is_feature_enabled("free", "auto_capture")

    def test_base_has_smart_answering(self):
        assert is_feature_enabled("base", "smart_answering")

    def test_unlimited_has_priority_support(self):
        assert is_feature_enabled("unlimited", "priority_support")

    def test_byok_allowed_only_for_byok_plan(self):
        assert PLANS["byok"]["byok_allowed"]      is True
        assert PLANS["free"]["byok_allowed"]      is False
        assert PLANS["base"]["byok_allowed"]      is False
        assert PLANS["unlimited"]["byok_allowed"] is False


# ── Helper functions ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_get_plan_fallback_to_free(self):
        assert get_plan("does_not_exist") == PLANS["free"]

    def test_get_stripe_price_map_excludes_free(self):
        price_map = get_stripe_price_map()
        assert "free" not in price_map
        assert len(price_map) == 3   # base, unlimited, byok

    def test_get_one_time_plans_contains_byok_only(self):
        one_time = get_one_time_plans()
        assert "byok" in one_time
        assert "free" not in one_time
        assert "base" not in one_time

    def test_get_plan_from_price_roundtrip(self):
        for pid, plan in PLANS.items():
            if plan["stripe_price_id"]:
                assert get_plan_from_price(plan["stripe_price_id"]) == pid

    def test_get_plan_from_price_unknown_returns_free(self):
        assert get_plan_from_price("nonexistent_price_id") == "free"

    def test_get_all_plan_limits_has_all_plans(self):
        limits = get_all_plan_limits()
        assert set(limits.keys()) == set(PLANS.keys())

    def test_quota_period_free_is_lifetime(self):
        assert get_quota_period("free") == "lifetime"

    def test_quota_period_base_is_monthly_format(self):
        period = get_quota_period("base")
        assert len(period) == 7        # YYYY-MM
        assert "-" in period

    def test_quota_period_unlimited_is_monthly(self):
        period = get_quota_period("unlimited")
        assert len(period) == 7

    def test_quota_period_byok_is_monthly(self):
        period = get_quota_period("byok")
        assert len(period) == 7

    def test_format_duration_zero_is_unlimited(self):
        assert format_duration(0) == "Unlimited"

    def test_format_duration_minutes_under_hour(self):
        assert format_duration(30) == "30 min"

    def test_format_duration_exact_hour(self):
        assert format_duration(60) == "1h"

    def test_format_duration_hour_and_minutes(self):
        assert format_duration(90) == "1h 30m"

    def test_format_sessions_at_threshold_is_unlimited(self):
        assert format_sessions(9999)  == "Unlimited"
        assert format_sessions(10000) == "Unlimited"

    def test_format_sessions_below_threshold_is_number(self):
        assert format_sessions(5)  == "5"
        assert format_sessions(15) == "15"
