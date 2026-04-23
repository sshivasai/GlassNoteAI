"""
api/usage_reporter.py

Asynchronous usage reporter — sends session metrics to the GlassNote
backend at session end.  Fire-and-forget: failures are logged and cached
locally, then flushed on next startup/report.

Design:
    - Only fires if the user is authenticated (glassnote_api_token set).
    - Uses a daemon thread so the app can close without waiting.
    - On HTTP failure, writes payload to ~/.glassnote/pending_usage.json.
    - On next call or startup, attempts to flush cached payloads first.
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Optional

import httpx


PENDING_FILE = Path.home() / ".glassnote" / "pending_usage.json"
_REPORTER_LOCK = threading.Lock()


def _cache_pending(payload: dict) -> None:
    """Save a failed payload to the local cache for later retry."""
    try:
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if PENDING_FILE.exists():
            with open(PENDING_FILE, "r") as f:
                existing = json.load(f)
        existing.append(payload)
        with open(PENDING_FILE, "w") as f:
            json.dump(existing, f)
        print(f"[usage] Cached offline payload (total pending: {len(existing)})")
    except Exception as e:
        print(f"[usage] Failed to cache payload: {e}")


def _flush_pending(api_url: str, api_token: str) -> None:
    """Attempt to flush any locally cached usage payloads to the backend."""
    with _REPORTER_LOCK:
        if not PENDING_FILE.exists():
            return
        try:
            with open(PENDING_FILE, "r") as f:
                pending = json.load(f)
        except Exception:
            return

        still_pending = []
        for payload in pending:
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(10.0, connect=5.0),
                ) as client:
                    r = client.post(
                        f"{api_url}/api/usage/report",
                        headers={
                            "Authorization": f"Bearer {api_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if r.status_code in (200, 404, 422):
                    # 200 = success, 404/422 = invalid session (stale/offline session — drop it)
                    print(f"[usage] ✓ Flushed pending payload (status={r.status_code})")
                else:
                    still_pending.append(payload)
            except Exception:
                still_pending.append(payload)

        if still_pending:
            with open(PENDING_FILE, "w") as f:
                json.dump(still_pending, f)
        else:
            PENDING_FILE.unlink(missing_ok=True)
            print(f"[usage] ✓ All pending payloads flushed")


def report_session_usage(
    api_url:          str,
    api_token:        str,
    session_id:       str,
    perf_summary:     dict,
    stt_calls:        list[dict],
    llm_calls:        list[dict],
    session_summary:  Optional[str] = None,
    conversation_json: Optional[list] = None,
):
    """
    Fire-and-forget session usage report to the GlassNote backend.

    Called from app_controller._on_end_session() when a GlassNote token
    is present.  Runs in a background daemon thread — never blocks UI.

    On failure (network or backend error), the payload is saved locally
    in ~/.glassnote/pending_usage.json and retried on next call.

    Args:
        api_url:           Base URL (e.g. https://api.glassnote.ai).
        api_token:         User's JWT.
        session_id:        Backend session UUID for correlation.
        perf_summary:      Output of perf_tracker.get_session_stats().
        stt_calls:         Raw STT call records from perf_tracker.
        llm_calls:         Raw LLM call records from perf_tracker.
        session_summary:   Short text summary of the session (e.g. last answer).
        conversation_json: Full Q&A history with screenshot placeholders.
    """
    def _send():
        # Try to flush any leftover payloads from previous offline sessions
        _flush_pending(api_url, api_token)

        payload = {
            "session_id":       session_id,
            "timestamp":        time.time(),
            "summary":          perf_summary,
            "session_summary":  session_summary or "",
            "conversation_json": conversation_json or [],
            "stt_usage": [
                {
                    "provider":         c.get("provider", ""),
                    "model":            c.get("model", ""),
                    "duration_seconds": c.get("duration_seconds", 0),
                    "cost_usd":         c.get("cost_usd", 0),
                }
                for c in stt_calls
            ],
            "llm_usage": [
                {
                    "model":         c.get("model", ""),
                    "provider":      c.get("provider", "openai"),
                    "mode":          c.get("mode", ""),
                    "latency_ms":    c.get("latency_ms", 0),
                    "output_tokens": c.get("output_tokens", 0),
                    "input_tokens":  c.get("input_tokens", 0),
                    "cost_usd":      c.get("cost_usd", 0),
                    "cache_hit":     c.get("cache_hit", False),
                }
                for c in llm_calls
            ],
        }

        try:
            with httpx.Client(
                http2=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
            ) as client:
                r = client.post(
                    f"{api_url}/api/usage/report",
                    headers={
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type":  "application/json",
                    },
                    json=payload,
                )

            if r.status_code == 200:
                print(
                    f"[usage] \u2713 Session usage reported \u2014 "
                    f"{len(stt_calls)} STT + {len(llm_calls)} LLM calls"
                )
            else:
                print(
                    f"[usage] \u26a0 Usage report failed \u2014 "
                    f"status={r.status_code}  body={r.text[:200]}"
                )
                _cache_pending(payload)

        except Exception as e:
            print(f"[usage] Usage report failed (offline?): {e}")
            _cache_pending(payload)

    threading.Thread(
        target=_send,
        daemon=True,
        name="usage-reporter",
    ).start()
