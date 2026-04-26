"""
Performance tracker — monitors latency, token counts, API costs.

Changes in this revision
------------------------
1. Now WIRED into app_controller._dispatch_llm() on_done callback.
   Previously this module existed but record_llm_call() was never invoked.

2. Added Deepgram and OpenAI Realtime STT pricing to record_stt_call().
   
3. Added get_session_cost_breakdown() for detailed per-model cost summary.

4. Session stats include input_tokens now.

Displayed in pill tooltip and printed to console.
Helps users understand what's happening and aids debugging.
"""

import time
from typing import Optional


# API pricing per 1M tokens (approximate, mid-2025)
_PRICING = {
    # model_id: (input_cost_per_1M, output_cost_per_1M)
    "claude-opus-4-5":    (15.00, 75.00),
    "claude-sonnet-4-5":  (3.00,  15.00),
    "claude-haiku-4-5":   (0.25,  1.25),
    "gpt-4o":             (2.50,  10.00),
    "gpt-4o-mini":        (0.15,  0.60),
    "gpt-4.1":            (2.00,  8.00),
    "gpt-4.1-mini":       (0.40,  1.60),
    "gpt-4-turbo":        (10.00, 30.00),
    "o1":                 (15.00, 60.00),
    "o1-mini":            (3.00,  12.00),
    "o3-mini":            (1.10,  4.40),
    "llama3.1-8b":        (0.10,  0.10),
    "gpt-oss-120b":       (0.60,  0.60),
}

# STT pricing per minute
_STT_PRICING = {
    # provider_or_model: cost_per_minute
    "deepgram":                   0.0043,    # nova-3 base rate
    "deepgram_nova":              0.0043,
    "deepgram_flux":              0.0059,
    "gpt-4o-mini-transcribe":     0.003,
    "gpt-4o-transcribe":          0.006,
    "openai_realtime":            0.003,     # default to mini-transcribe
}


class PerformanceTracker:
    """
    Tracks per-call and per-session metrics.

    Thread-safe enough for our use (GIL protects simple list appends).
    All metrics are kept in memory — reset on session end.
    """

    def __init__(self):
        self._calls: list = []          # list of call dicts
        self._session_start = time.time()

    def record_llm_call(
        self,
        model: str,
        mode: str,
        latency_ms: float,
        output_tokens: int,
        input_tokens: int = 0,
        cache_hit: bool = False,
    ):
        """
        Record a single LLM API call for tracking.

        Args:
            model (str): The LLM model used (e.g. 'claude-haiku-4-5').
            mode (str): Operating mode ('solve', 'analyze', 'interview').
            latency_ms (float): Wall-clock time from dispatch to completion.
            output_tokens (int): Number of output tokens generated.
            input_tokens (int): Number of input tokens (0 = estimated).
            cache_hit (bool): Whether the response came from local cache.
        """
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        entry = {
            "type":         "llm",
            "model":        model,
            "mode":         mode,
            "latency_ms":   latency_ms,
            "output_tokens": output_tokens,
            "input_tokens": input_tokens,
            "cost_usd":     cost,
            "cache_hit":    cache_hit,
            "timestamp":    time.time(),
        }
        self._calls.append(entry)
        self._print_call(entry)

    def record_stt_call(
        self,
        provider: str,
        duration_seconds: float,
        latency_ms: float = 0.0,
        model: str = "",
    ):
        """
        Record a speech-to-text API call.

        Args:
            provider (str): STT provider ('deepgram' or 'openai_realtime').
            duration_seconds (float): Audio duration processed.
            latency_ms (float): Transcription latency.
            model (str): Specific STT model used (for more accurate pricing).
        """
        # Try model-specific pricing first, then provider-level
        price_key = model or provider
        cost_per_min = _STT_PRICING.get(price_key, _STT_PRICING.get(provider, 0.005))
        cost = (duration_seconds / 60) * cost_per_min

        entry = {
            "type":             "stt",
            "provider":         provider,
            "model":            model or provider,
            "duration_seconds": duration_seconds,
            "latency_ms":       latency_ms,
            "cost_usd":         cost,
            "timestamp":        time.time(),
        }
        self._calls.append(entry)

    def get_session_stats(self) -> dict:
        """
        Get aggregate session statistics.

        Returns:
            dict: Session metrics including call counts, costs, latency, tokens.
        """
        llm_calls  = [c for c in self._calls if c["type"] == "llm"]
        stt_calls  = [c for c in self._calls if c["type"] == "stt"]
        cache_hits = [c for c in llm_calls if c.get("cache_hit")]

        total_cost = sum(c.get("cost_usd", 0) for c in self._calls)
        avg_latency = (
            sum(c["latency_ms"] for c in llm_calls) / len(llm_calls)
            if llm_calls else 0
        )
        total_output_tokens = sum(c.get("output_tokens", 0) for c in llm_calls)
        total_input_tokens  = sum(c.get("input_tokens", 0) for c in llm_calls)
        total_stt_minutes   = sum(c.get("duration_seconds", 0) for c in stt_calls) / 60
        session_mins = (time.time() - self._session_start) / 60

        return {
            "session_minutes":    round(session_mins, 1),
            "llm_calls":          len(llm_calls),
            "stt_calls":          len(stt_calls),
            "cache_hits":         len(cache_hits),
            "avg_latency_ms":     round(avg_latency),
            "total_output_tokens": total_output_tokens,
            "total_input_tokens":  total_input_tokens,
            "total_stt_minutes":   round(total_stt_minutes, 1),
            "total_cost_usd":     round(total_cost, 4),
            "cost_per_call_usd":  round(total_cost / max(len(llm_calls), 1), 4),
        }

    def get_session_cost_breakdown(self) -> dict:
        """
        Get per-model cost breakdown for the session.

        Returns:
            dict: {model_name: {"calls": N, "cost_usd": X.XX, "tokens": N}}
        """
        breakdown = {}
        for call in self._calls:
            key = call.get("model") or call.get("provider", "unknown")
            if key not in breakdown:
                breakdown[key] = {"calls": 0, "cost_usd": 0.0, "tokens": 0}
            breakdown[key]["calls"]    += 1
            breakdown[key]["cost_usd"] += call.get("cost_usd", 0)
            breakdown[key]["tokens"]   += call.get("output_tokens", 0)
        # Round costs
        for key in breakdown:
            breakdown[key]["cost_usd"] = round(breakdown[key]["cost_usd"], 4)
        return breakdown

    def get_summary_line(self) -> str:
        """
        One-line summary for pill tooltip and session end log.

        Returns:
            str: Human-readable session summary.
        """
        stats = self.get_session_stats()
        return (
            f"{stats['llm_calls']} calls · "
            f"~{stats['avg_latency_ms']}ms avg · "
            f"${stats['total_cost_usd']:.3f} · "
            f"{stats['session_minutes']}min"
        )

    def get_calls_raw(self) -> list[dict]:
        """
        Get all raw call records for the session.

        Used by the backend API to report usage to the server.

        Returns:
            list[dict]: List of all call records.
        """
        return list(self._calls)

    def reset(self):
        """Reset all metrics — called at session end."""
        self._calls.clear()
        self._session_start = time.time()

    def _estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """
        Estimate the USD cost of an LLM call.

        Args:
            model (str): Model ID.
            input_tokens (int): Input token count (0 = estimated as 500).
            output_tokens (int): Output token count.

        Returns:
            float: Estimated cost in USD.
        """
        pricing = _PRICING.get(model, (3.00, 15.00))  # Default to Sonnet pricing
        input_cost  = (input_tokens  / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        # Estimate if not provided: assume 500 input tokens
        if input_tokens == 0:
            input_cost = (500 / 1_000_000) * pricing[0]
        return input_cost + output_cost

    def _print_call(self, entry: dict):
        """Print a formatted call record to console."""
        cache = " [CACHE HIT]" if entry.get("cache_hit") else ""
        print(
            f"[perf] {entry['mode'].upper()} → {entry['model']} | "
            f"{entry['latency_ms']:.0f}ms | "
            f"~{entry['output_tokens']} tokens | "
            f"${entry['cost_usd']:.4f}{cache}"
        )


# Session-level singleton
tracker = PerformanceTracker()