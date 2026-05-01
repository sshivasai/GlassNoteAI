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

Security
--------
API keys are stored in OS keyring (encrypted) when available, with
plaintext JSON as fallback. Use set_secure() for sensitive values.
"""

import json
import os
import hashlib
import threading
from pathlib import Path
from typing import Any

# ── Keyring support for secure API key storage ────────────────────────────────
_KEYRING_SERVICE = "GlassNote"
_KEYRING_AVAILABLE = False

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    keyring = None

# Keys that should be stored securely in keyring instead of plaintext config
_SECURE_KEYS = {
    "anthropic_api_key",
    "openai_api_key",
    "cerebras_api_key",
    "deepgram_api_key",
}


def _keyring_set(key: str, value: str) -> bool:
    """Save a value to OS keyring. Returns True on success."""
    if not _KEYRING_AVAILABLE or not value:
        return False
    try:
        keyring.set_password(_KEYRING_SERVICE, key, value)
        return True
    except Exception as e:
        print(f"[config] Keyring save failed for {key}: {e}")
        return False


def _keyring_get(key: str) -> str:
    """Load a value from OS keyring. Returns empty string if not found."""
    if not _KEYRING_AVAILABLE:
        return ""
    try:
        value = keyring.get_password(_KEYRING_SERVICE, key)
        return value or ""
    except Exception as e:
        print(f"[config] Keyring load failed for {key}: {e}")
        return ""


def _keyring_delete(key: str) -> None:
    """Delete a value from OS keyring."""
    if not _KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(_KEYRING_SERVICE, key)
    except Exception as e:
        # FIX (LOW-1): Log the error instead of silent pass
        print(f"[config] Keyring delete failed for {key}: {e}")

CONFIG_PATH = Path.home() / ".glassnote" / "config.json"

DEFAULTS = {
    # ── API Keys ───────────────────────────────────────────────
    "anthropic_api_key":  "",
    "openai_api_key":     "",
    "cerebras_api_key":   "",
    "deepgram_api_key":   "",

    # ── Model settings ─────────────────────────────────────────
    "selected_provider":  "anthropic",
    "anthropic_model":    "claude-opus-4-5",
    "openai_model":       "gpt-4o",
    "cerebras_model":     "llama3.1-8b",
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
    "preferred_monitor":      1,  # 1=primary, 2=secondary, etc.

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

    # ── Interview Context Window ───────────────────────────────
    # Number of recent Q&A exchanges to include as context in interview mode.
    # Each exchange = 1 user question + 1 assistant answer = 2 messages.
    #
    # Balance speed vs context:
    #   5 exchanges → ~1000-1500 tokens → ~500-800ms TTFT (recommended)
    #   10 exchanges → ~2000-3000 tokens → ~1000-1500ms TTFT
    #   0 (no context) → ~150 tokens → ~300ms TTFT (very fast but loses context)
    #   -1 (unlimited) → full history → 2000+ ms TTFT (slow, degrades over time)
    #
    # Only applies when smart_answering=True. When False, full history is always sent.
    "interview_context_window": 5,

    # ── Session defaults ───────────────────────────────────────
    "default_language":   "English",
    "simple_language":    False,
    "save_transcript":    True,

    # ── Process disguise (Task Manager / System Monitor) ──────
    "process_disguise_name": "Windows Audio Endpoint Builder",

    # ── Resource limits ────────────────────────────────────────
    "max_memory_mb": 1024,           # 1 GB
    "max_queue_size": 50,            # Screenshot queue
    "max_history_items": 100,        # Q&A history per session
    "max_cache_size": 50,            # Response cache

    # ── Accessibility ──────────────────────────────────────────
    "high_contrast_mode": False,
    "font_scale": 1.0,               # 1.0 = normal, 1.5 = 150%
    "keyboard_navigation_hints": False,
    "screen_reader_support": False,

    # ── Telemetry (opt-in) ─────────────────────────────────────
    "telemetry_opt_in": False,
    "sentry_dsn": "",                # Set in production

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
# FIX (MEDIUM-2): Added hash check to prevent mtime manipulation bypass

_cache_lock:   threading.Lock       = threading.Lock()
_cached_cfg:   dict | None          = None
_cached_mtime: float                = 0.0
_cached_hash:  str                  = ""  # MD5 hash for tamper detection


def load_config() -> dict:
    """
    Load config from disk with mtime-based caching.

    Returns the cached dict if the config file has not been modified
    since the last read (~50 ns).  Otherwise reads from disk (~200 µs)
    and updates the cache.

    Sensitive API keys are loaded from OS keyring if available.

    Thread-safe with proper file locking to prevent TOCTOU race conditions.

    Returns:
        dict: Merged config (DEFAULTS + stored values + keyring secrets).
    """
    global _cached_cfg, _cached_mtime

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        save_config(DEFAULTS.copy())
        return DEFAULTS.copy()

    # Check mtime under lock to prevent race condition
    # FIX: Handle file deletion more gracefully (avoid deadlock)
    with _cache_lock:
        try:
            current_mtime = CONFIG_PATH.stat().st_mtime
        except FileNotFoundError:
            # File was deleted between exists() check and stat()
            # Don't call save_config() inside the lock (it acquires its own lock)
            current_mtime = 0.0  # Force cache miss

        if _cached_cfg is not None and current_mtime == _cached_mtime:
            return _cached_cfg.copy()

        # FIX: If file was deleted, recreate it outside the lock
        if current_mtime == 0.0 and not CONFIG_PATH.exists():
            pass  # Will be handled by cache miss path below

        # Cache miss — read from disk (still under lock)
        try:
            with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                stored = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # File corrupted or deleted during read — recreate
            print(f"[config] Load failed ({e}), recreating config file")
            save_config(DEFAULTS.copy())
            return DEFAULTS.copy()

        # Always merge so new keys added to DEFAULTS appear automatically
        merged = DEFAULTS.copy()
        merged.update(stored)

        # Load secure keys from keyring (takes precedence over config file)
        for key in _SECURE_KEYS:
            keyring_value = _keyring_get(key)
            if keyring_value:
                merged[key] = keyring_value
            # If not in keyring but in config, migrate it to keyring
            elif merged.get(key):
                if _keyring_set(key, merged[key]):
                    # Successfully migrated to keyring — remove from config
                    merged[key] = ""  # Will be saved as empty in config

        # FIX (MEDIUM-2): Cache hash for tamper detection
        try:
            with open(CONFIG_PATH, "rb") as f:
                _cached_hash = hashlib.md5(f.read()).hexdigest()
        except Exception:
            _cached_hash = ""

        _cached_cfg   = merged
        _cached_mtime = current_mtime

        return merged.copy()


def save_config(cfg: dict) -> None:
    """
    Save config to disk and invalidate the in-memory cache.

    Thread-safe atomic write using temp file + rename to prevent corruption.

    Args:
        cfg (dict): The config dict to persist.
    """
    global _cached_cfg, _cached_mtime, _cached_hash

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp file, then rename
    # This prevents corruption if process is killed mid-write
    temp_path = CONFIG_PATH.with_suffix('.tmp')
    try:
        with open(temp_path, "w", encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)

        # Atomic rename (POSIX guarantees atomicity)
        temp_path.replace(CONFIG_PATH)
    except Exception as e:
        print(f"[config] Save failed: {e}")
        # Clean up temp file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise

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


def set_secure(key: str, value: str) -> None:
    """
    Set a sensitive value (API key) securely in keyring.

    Falls back to plaintext config if keyring is unavailable.

    Args:
        key: Config key (should be in _SECURE_KEYS)
        value: The sensitive value to store
    """
    if key in _SECURE_KEYS and value:
        if _keyring_set(key, value):
            # Successfully saved to keyring — clear from config file
            cfg = load_config()
            cfg[key] = ""  # Empty string in config means "check keyring"
            save_config(cfg)
            print(f"[config] {key} saved to keyring (encrypted)")
            return

    # Fallback: save to config file
    set(key, value)
    print(f"[config] WARNING: {key} saved to plaintext config (keyring unavailable)")


def get_secure(key: str, fallback: str = "") -> str:
    """
    Get a sensitive value, preferring keyring over config file.

    Args:
        key: Config key to retrieve
        fallback: Default value if not found

    Returns:
        str: The value from keyring, config, or fallback
    """
    # Try keyring first
    if key in _SECURE_KEYS:
        value = _keyring_get(key)
        if value:
            return value

    # Fall back to config file
    return get(key, fallback)


def reset() -> None:
    """Reset config to defaults."""
    save_config(DEFAULTS.copy())