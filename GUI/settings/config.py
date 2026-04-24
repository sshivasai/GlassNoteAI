"""
settings/config.py — JSON config load/save with in-memory cache.

Optimisation
------------
load_config() now checks the file's mtime before reading from disk.
If the file has not been modified since the last read, the cached dict
is returned immediately (~50 ns vs ~200 µs for a disk read).

save_config() always invalidates the cache so the next load_config()
picks up the fresh values.

This eliminates the ~200 µs disk read that was previously happening
on every 100 ms silence-poll, every hotkey press, and every UI paint.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".glassnote" / "config.json"

DEFAULTS = {
    # ── API Keys ───────────────────────────────────────────────
    "anthropic_api_key":  "",
    "openai_api_key":     "",
    "deepgram_api_key":   "",

    # ── Model settings ─────────────────────────────────────────
    "selected_provider":  "anthropic",
    "anthropic_model":    "claude-opus-4-5",
    "openai_model":       "gpt-4o",
    # User-configurable ceiling. Mode-specific caps in _get_max_tokens()
    # (e.g. 600 for interview) provide the actual per-request limits via
    # min(mode_cap, user_cap), so this high default won't overshoot.
    "max_tokens":         16384,

    # ── STT Provider ───────────────────────────────────────────
    # "deepgram"       → DeepgramStreamingSTT  (WebSocket, ultra-low latency)
    # "openai_realtime"→ OpenAIRealtimeSTT     (WebSocket, server VAD, no hallucinations)
    # NOTE: "whisper" removed — replaced by openai_realtime
    "stt_provider":       "deepgram",            # ← CHANGED (was "whisper")

    # ── Deepgram model ─────────────────────────────────────────
    # "flux-general-en" → V2 API  (ultra low latency, EndOfTurn events)
    # "nova-3"          → V1 API  (highest accuracy, speech_final events)
    # "nova-2"          → V1 API  (stable, widely supported)
    "deepgram_model":     "flux-general-en",

    # ── OpenAI Realtime STT model ──────────────────────────────
    # Used when stt_provider == "openai_realtime".
    # Both use wss://api.openai.com/v1/realtime?intent=transcription
    # with server-side VAD — zero hallucinations on silence.
    #
    # "gpt-4o-mini-transcribe" → $0.003 / min  (50% cheaper, fast)
    # "gpt-4o-transcribe"      → $0.006 / min  (best accuracy)
    "openai_stt_model":   "gpt-4o-mini-transcribe",

    # ── Overlay settings ───────────────────────────────────────
    "opacity":            0.93,
    "overlay_position":   {"x": 100, "y": 100},
    "pill_position":      {"x": 50,  "y": 50},
    "theme":              "dark",

    # ── Capture settings ───────────────────────────────────────
    "auto_capture":           False,
    "auto_capture_interval":  5,
    "capture_region":         None,

    # ── Audio settings ─────────────────────────────────────────
    "audio_source":       "system",
    "auto_answer":        False,
    "silence_threshold":  1.5,

    # ── Smart Answering ────────────────────────────────────────
    # When True the STT provider's own end-of-utterance / final-transcript
    # signal is used together with the silence threshold to decide when to
    # dispatch to the LLM.  The two signals are OR-ed:
    #   • STT says "this is a final / end-of-turn segment"  → dispatch immediately
    #   • OR silence_threshold seconds of quiet pass        → dispatch (fallback)
    # When False only the silence-threshold path is active (legacy behaviour).
    #
    # Provider behaviour with Smart Answering ON:
    #   Deepgram flux      → EndOfTurn event         (V2 API)
    #   Deepgram nova-3/2  → speech_final=True        (V1 API)
    #   OpenAI Realtime    → transcription.completed  (server VAD committed)
    "smart_answering":    False,

    # ── Session defaults ───────────────────────────────────────
    "default_language":   "English",
    "simple_language":    False,
    "save_transcript":    True,

    # ── Optimisation settings ──────────────────────────────────
    "use_response_cache": True,
    "use_prompt_cache":   True,
    "auto_model_routing": True,
    "image_max_width":    1280,
    "use_http2":          True,

    # ── GlassNote API (SaaS mode) ─────────────────────────────────────────────
    # When glassnote_api_token is set, the app routes LLM/STT calls
    # through api.glassnote.ai instead of directly to providers.
    # Provider API keys are NOT needed in SaaS mode.
    "glassnote_api_url":   "http://localhost:8000",   # no trailing slash
    "glassnote_api_token": "",
    "glassnote_user_email": "",
    "glassnote_user_plan":  "",                        # set after login
}


# ── In-memory cache ───────────────────────────────────────────────────────────
# Eliminates repeated disk reads.  Invalidated only by save_config().
# Thread-safe via _cache_lock.

_cache_lock:  threading.Lock       = threading.Lock()
_cached_cfg:  dict | None          = None
_cached_mtime: float               = 0.0


def load_config() -> dict:
    """
    Load config from disk with mtime-based caching.

    Returns the cached dict if the config file has not been modified
    since the last read (~50 ns).  Otherwise reads from disk (~200 µs)
    and updates the cache.

    Returns:
        dict: Merged config (DEFAULTS + stored values).
    """
    global _cached_cfg, _cached_mtime

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        save_config(DEFAULTS.copy())
        return DEFAULTS.copy()

    current_mtime = CONFIG_PATH.stat().st_mtime

    with _cache_lock:
        if _cached_cfg is not None and current_mtime == _cached_mtime:
            return _cached_cfg.copy()

    # Cache miss — read from disk
    with open(CONFIG_PATH, "r") as f:
        stored = json.load(f)

    # Always merge so new keys added to DEFAULTS appear automatically
    merged = DEFAULTS.copy()
    merged.update(stored)

    with _cache_lock:
        _cached_cfg   = merged
        _cached_mtime = current_mtime

    return merged.copy()


def save_config(cfg: dict) -> None:
    """
    Save config to disk and invalidate the in-memory cache.

    Args:
        cfg (dict): The config dict to persist.
    """
    global _cached_cfg, _cached_mtime

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

    # Invalidate cache — next load_config() will re-read
    with _cache_lock:
        _cached_cfg   = None
        _cached_mtime = 0.0


def invalidate_cache() -> None:
    """
    Force cache invalidation without writing to disk.
    
    Useful when external processes may have modified the config file.
    """
    global _cached_cfg, _cached_mtime
    with _cache_lock:
        _cached_cfg   = None
        _cached_mtime = 0.0


def get(key: str, fallback: Any = None) -> Any:
    """Get a single config value by key."""
    return load_config().get(key, fallback)


def set(key: str, value: Any) -> None:
    """Set a single config value and persist to disk."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


def reset() -> None:
    """Reset config to defaults."""
    save_config(DEFAULTS.copy())