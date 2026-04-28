"""
llm/model_registry.py

Model capability registry for hybrid fallback routing.

When a text-only model (e.g., Cerebras) is selected but the user sends
an image-based request (analyze/solve modes), we automatically fallback
to a fast vision-capable model.

This ensures:
  1. Analyze mode always works even when Cerebras is selected
  2. Interview mode continues using the selected text-only model
  3. Users get consistent behavior without manual model switching
"""

# ── Text-only models (no vision support) ──────────────────────────────────────
# These models will trigger hybrid fallback when images are present.

TEXT_ONLY_MODELS = {
    # Cerebras models (ultra-fast inference, no vision)
    "llama3.1-8b",
    "gpt-oss-120b",

    # OpenAI text-only models
    "o1",
    "o1-mini",
    "o3-mini",

    # Future text-only models can be added here
}


# ── Vision-capable models ─────────────────────────────────────────────────────
# These models support both text and images.

VISION_MODELS = {
    # Anthropic Claude (all variants support vision)
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",

    # OpenAI GPT-4/4.1/4o family (vision-capable)
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4-turbo",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
}


# ── Hybrid fallback configuration ─────────────────────────────────────────────
# When a text-only model is selected but images are needed, use this mapping.

DEFAULT_VISION_FALLBACK = {
    "anthropic": "claude-haiku-4-5",    # Fast, cheap, vision-capable
    "openai":    "gpt-4o-mini",         # Fast, cheap, vision-capable
    "cerebras":  "gpt-4o-mini",         # Fallback to OpenAI (Cerebras has no vision)
}


def is_text_only(model: str) -> bool:
    """
    Check if a model supports only text (no vision).

    Args:
        model: Model ID (e.g., "llama3.1-8b", "gpt-4o-mini")

    Returns:
        True if the model is text-only, False if it supports vision.
    """
    return model in TEXT_ONLY_MODELS


def is_vision_capable(model: str) -> bool:
    """
    Check if a model supports vision (images + text).

    Args:
        model: Model ID (e.g., "gpt-4o-mini", "claude-opus-4-5")

    Returns:
        True if the model supports vision, False otherwise.
    """
    return model in VISION_MODELS


def get_vision_fallback(provider: str, original_model: str) -> tuple[str, str]:
    """
    Get the vision-capable fallback model for a text-only model.

    When a text-only model is selected but the user sends an image-based
    request (analyze/solve modes), this returns the appropriate fallback.

    Args:
        provider: Current provider ("anthropic", "openai", "cerebras")
        original_model: The text-only model currently selected

    Returns:
        Tuple of (fallback_provider, fallback_model)

    Example:
        >>> get_vision_fallback("cerebras", "llama3.1-8b")
        ("openai", "gpt-4o-mini")
    """
    # If Cerebras is selected, always fallback to OpenAI
    # (Cerebras has no vision-capable models)
    if provider == "cerebras":
        return "openai", DEFAULT_VISION_FALLBACK["openai"]

    # For other providers, use their own fast vision model
    fallback_model = DEFAULT_VISION_FALLBACK.get(provider, "gpt-4o-mini")
    return provider, fallback_model


def needs_vision_fallback(provider: str, model: str, has_images: bool, mode: str) -> bool:
    """
    Determine if a request needs vision fallback.

    Args:
        provider: Current provider ("anthropic", "openai", "cerebras")
        model: Currently selected model
        has_images: Whether the request includes images
        mode: Request mode ("analyze", "solve", "interview")

    Returns:
        True if hybrid fallback should be used, False otherwise.

    Rules:
        - Interview mode: never fallback (text-only is fine)
        - Analyze/solve with images: fallback if model is text-only
        - No images: no fallback needed
    """
    # Interview mode is always text-only — no fallback needed
    if mode == "interview":
        return False

    # No images — no fallback needed
    if not has_images:
        return False

    # Analyze/solve with images — fallback if text-only
    return is_text_only(model) or provider == "cerebras"
