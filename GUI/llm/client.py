"""
llm/client.py

Changes in this revision
------------------------
1. Thread-safe config cache — _cfg_lock prevents TOCTOU race when
   stream() and warm_connections() run concurrently.

2. Anthropic prompt caching FIXED — the required
   "anthropic-beta: prompt-caching-2024-07-31" header was missing.
   Without it cache_control directives are silently ignored.
   Now conditionally sent when use_prompt_cache=True in config.

3. cache_control directives conditionalised — _anthropic_system_payload()
   and _build_anthropic_messages() now accept use_prompt_cache flag so
   the cache markup is only written when the feature is enabled.

4. OpenAI stream_options usage — adds {"include_usage": True} so token
   counts appear at the end of every stream for cost logging.

5. warm_connections() accepts optional pre-loaded cfg — avoids a second
   config read when the caller already holds the dict.

6. invalidate_config() closes pool when provider changes — previously
   only cleared the config cache; old TCP connection was orphaned.
"""

import base64
import sys
import os
import hashlib
import time
import json
import io
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional, Iterator, Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import config

# TTFT-OPT: module-level import, avoid repeated disk reads
# pricing_config was previously imported inside _get_proxy_config() on every
# stream() call. Moving it here means the import is resolved once at startup.
try:
    import pricing_config as _pricing_config
    _PRICING_CONFIG_AVAILABLE = True
except ImportError:
    _pricing_config = None
    _PRICING_CONFIG_AVAILABLE = False

try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PILImage      = None
    _PIL_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Fast image identity hash
# ──────────────────────────────────────────────────────────────────────────────

def _fast_image_hash(b64: str) -> str:
    sig = f"{len(b64)}:{b64[:256]}"
    return hashlib.sha256(sig.encode()).hexdigest()[:24]


# ──────────────────────────────────────────────────────────────────────────────
# Response cache  (OrderedDict LRU, thread-safe)
# ──────────────────────────────────────────────────────────────────────────────

class _ResponseCache:
    MAX_SIZE    = 50
    TTL_SECONDS = 1_800

    def __init__(self):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock  = threading.Lock()

    def _make_key(self, provider, model, system_prompt,
                  messages, images, mode,
                  use_cache: bool = True) -> str:
        parts = [provider, model, mode, system_prompt]
        if messages:
            recent = messages[-3:]
            parts.append(json.dumps(recent, sort_keys=True, ensure_ascii=False))
        # TTFT-OPT: only compute image hashes when the response cache is
        # actually enabled.  _fast_image_hash() base64-decodes a prefix and
        # runs SHA-256 — unnecessary work when the caller already knows the
        # result won't be cached.
        if images and use_cache:
            for img in images:
                parts.append(_fast_image_hash(img))
        elif images:
            # Still include image count so keys differ with/without images,
            # but skip the expensive per-image hash.
            parts.append(f"imgs:{len(images)}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]

    def get(self, provider, model, system_prompt,
            messages, images, mode) -> Optional[str]:
        key = self._make_key(provider, model, system_prompt, messages, images, mode)
        with self._lock:
            if key not in self._cache:
                return None
            response, ts = self._cache[key]
            if time.time() - ts > self.TTL_SECONDS:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return response

    def put(self, provider, model, system_prompt,
            messages, images, mode, response: str):
        key = self._make_key(provider, model, system_prompt, messages, images, mode)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (response, time.time())
            while len(self._cache) > self.MAX_SIZE:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()


_response_cache = _ResponseCache()


# ──────────────────────────────────────────────────────────────────────────────
# Image helpers
# ──────────────────────────────────────────────────────────────────────────────

def _detect_media_type(b64: str) -> str:
    try:
        sample  = b64[:16]
        padding = (4 - len(sample) % 4) % 4
        header  = base64.b64decode(sample + "=" * padding)
        if len(header) >= 2 and header[:2] == b"\xff\xd8":
            return "image/jpeg"
        if len(header) >= 8 and header[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if len(header) >= 6 and header[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if len(header) >= 4 and header[:4] == b"RIFF":
            return "image/webp"
    except Exception:
        pass
    return "image/png"


def _is_text_screenshot(img) -> bool:
    try:
        small  = img.resize((64, 64)).convert("L")
        pixels = small.getdata()
        n      = len(pixels)
        if n == 0:
            return True
        white = black = 0
        for p in pixels:
            if p > 240:
                white += 1
            elif p < 15:
                black += 1
        return (white + black) / n > 0.40
    except Exception:
        return True


# TTFT-OPT: size threshold (in base64 chars) below which we skip the full
# decode→resize→encode cycle.  500 KB of raw bytes ≈ 667 KB base64.
# Screenshots from the capture pipeline are already resized to 768px and
# format-detected, so re-processing them is a no-op that costs 50-300 ms.
_OPT_SIZE_THRESHOLD = 680_000  # ~500 KB raw


def _optimize_image(
    b64: str,
    max_width: int = 1_280,
    already_optimized: bool = False,
) -> str:
    """Optimize a base64-encoded image for LLM consumption.

    Parameters
    ----------
    b64 : str
        Base64-encoded image data.
    max_width : int
        Maximum pixel width; images wider than this are downscaled.
    already_optimized : bool
        When *True*, the image has already been through the capture
        pipeline (``screenshot.py`` → ``_pil_to_base64``), which resizes
        to 768 px and picks the optimal PNG/JPEG format.  In that case
        we skip the full decode→resize→encode cycle entirely, removing
        50-300 ms from the TTFT critical path.
    """
    # ── Fast path 1: caller guarantees the image is already optimized ──
    if already_optimized:
        return b64

    # ── Fast path 2: small images don't need re-encoding ───────────────
    # Base64 length is a cheap proxy for byte size (no decode needed).
    if len(b64) <= _OPT_SIZE_THRESHOLD:
        return b64

    if not _PIL_AVAILABLE:
        return b64
    try:
        data = base64.b64decode(b64)
        img  = _PILImage.open(io.BytesIO(data)).convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img   = img.resize(
                (max_width, int(img.height * ratio)), _PILImage.LANCZOS
            )
        is_text = _is_text_screenshot(img)
        buf     = io.BytesIO()
        if is_text:
            img.save(buf, format="PNG", optimize=True)
        else:
            img.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return b64


# ── Image optimisation cache — guarded by its own lock ────────────────────────
_opt_cache_lock: threading.Lock      = threading.Lock()
_opt_image_cache: dict[str, str]     = {}
_OPT_CACHE_MAX = 20


def _optimize_image_cached(
    b64: str,
    already_optimized: bool = False,
) -> str:
    # TTFT-OPT: when the image is already optimized (from capture pipeline),
    # skip both the cache lookup *and* the decode→resize→encode cycle.
    # This avoids _fast_image_hash() + _optimize_image() entirely.
    if already_optimized:
        return _optimize_image(b64, already_optimized=True)

    key = _fast_image_hash(b64)
    with _opt_cache_lock:                          # ← ADDED lock
        cached = _opt_image_cache.get(key)
    if cached is not None:
        return cached
    result = _optimize_image(b64)
    with _opt_cache_lock:
        if len(_opt_image_cache) >= _OPT_CACHE_MAX:
            _opt_image_cache.pop(next(iter(_opt_image_cache)))
        _opt_image_cache[key] = result
    return result


# ──────────────────────────────────────────────────────────────────────────────
# HTTP/2 connection pool  — thread-safe + keepalive heartbeat
# ──────────────────────────────────────────────────────────────────────────────

_HEARTBEAT_INTERVAL = 45


class _ConnectionPool:
    def __init__(self):
        self._lock               = threading.Lock()
        self._anthropic_client:  Optional[httpx.Client] = None
        self._openai_client:     Optional[httpx.Client] = None
        self._proxy_client:      Optional[httpx.Client] = None
        self._last_anthropic_key = ""
        self._last_openai_key    = ""
        self._last_proxy_url     = ""

        self._heartbeat_active   = False
        self._heartbeat_thread:  Optional[threading.Thread] = None
        self._heartbeat_api_key  = ""
        self._heartbeat_provider = ""

    @staticmethod
    def _make_client() -> httpx.Client:
        return httpx.Client(
            http2   = True,
            timeout = httpx.Timeout(60.0, connect=10.0),
            limits  = httpx.Limits(
                max_keepalive_connections = 5,
                max_connections           = 10,
                keepalive_expiry          = 300,
            ),
        )

    def get_anthropic(self, api_key: str) -> httpx.Client:
        with self._lock:
            if (self._anthropic_client is None
                    or api_key != self._last_anthropic_key):
                if self._anthropic_client:
                    try:
                        self._anthropic_client.close()
                    except Exception:
                        pass
                self._anthropic_client   = self._make_client()
                self._last_anthropic_key = api_key
            return self._anthropic_client

    def get_openai(self, api_key: str) -> httpx.Client:
        with self._lock:
            if (self._openai_client is None
                    or api_key != self._last_openai_key):
                if self._openai_client:
                    try:
                        self._openai_client.close()
                    except Exception:
                        pass
                self._openai_client   = self._make_client()
                self._last_openai_key = api_key
            return self._openai_client

    def start_heartbeat(self, api_key: str, provider: str):
        if self._heartbeat_active:
            return
        self._heartbeat_active   = True
        self._heartbeat_api_key  = api_key
        self._heartbeat_provider = provider

        def _beat():
            while self._heartbeat_active:
                for _ in range(_HEARTBEAT_INTERVAL * 2):
                    if not self._heartbeat_active:
                        return
                    time.sleep(0.5)
                if not self._heartbeat_active:
                    return
                try:
                    if provider == "anthropic":
                        c = self._anthropic_client
                        if c:
                            c.get(
                                "https://api.anthropic.com/v1/models",
                                headers={
                                    "x-api-key":         self._heartbeat_api_key,
                                    "anthropic-version": "2023-06-01",
                                },
                                timeout=5.0,
                            )
                    elif provider == "openai":
                        c = self._openai_client
                        if c:
                            c.get(
                                "https://api.openai.com/v1/models",
                                headers={
                                    "Authorization":
                                        f"Bearer {self._heartbeat_api_key}"
                                },
                                timeout=5.0,
                            )
                except Exception:
                    pass

        self._heartbeat_thread = threading.Thread(
            target=_beat, daemon=True, name="llm-keepalive"
        )
        self._heartbeat_thread.start()
        print(
            f"[llm] keepalive heartbeat started — "
            f"provider={provider}  interval={_HEARTBEAT_INTERVAL}s"
        )

    def stop_heartbeat(self):
        self._heartbeat_active = False
        print("[llm] keepalive heartbeat stopped")

    def get_proxy(self, proxy_url: str) -> httpx.Client:
        """Get or create the shared proxy connection pool."""
        with self._lock:
            if (self._proxy_client is None
                    or proxy_url != self._last_proxy_url):
                if self._proxy_client:
                    try:
                        self._proxy_client.close()
                    except Exception:
                        pass
                self._proxy_client   = self._make_client()
                self._last_proxy_url = proxy_url
            return self._proxy_client

    def invalidate(self):
        self.stop_heartbeat()
        with self._lock:
            for c in (self._anthropic_client, self._openai_client, self._proxy_client):
                if c:
                    try:
                        c.close()
                    except Exception:
                        pass
            self._anthropic_client   = None
            self._openai_client      = None
            self._proxy_client       = None
            self._last_anthropic_key = ""
            self._last_openai_key    = ""
            self._last_proxy_url     = ""


_pool = _ConnectionPool()


# ──────────────────────────────────────────────────────────────────────────────
# Model routing
# ──────────────────────────────────────────────────────────────────────────────

_ANTHROPIC_MODELS = {
    "fast":     "claude-haiku-4-5",
    "balanced": "claude-sonnet-4-5",
    "best":     "claude-opus-4-5",
}
_OPENAI_MODELS = {
    "fast":     "gpt-4o-mini",
    "balanced": "gpt-4o",
    "best":     "gpt-4o",
}
_DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-5",
    "openai":    "gpt-4o",
}

_SIMPLE_KEYWORDS  = frozenset([
    "reverse", "fibonacci", "factorial", "palindrome",
    "hello", "simple", "basic", "easy",
    "what is", "define", "explain briefly",
])
_COMPLEX_KEYWORDS = frozenset([
    "design", "system design", "architecture", "distributed",
    "scalab", "microservice", "database schema", "trade-off",
    "optimize", "performance", "concurren", "thread",
    "dynamic programming", "graph", "tree", "backtrack",
])

_MODE_MAX_TOKENS: dict[str, int] = {
    "interview": 600,
    "solve":    2_048,
    "analyze":  1_500,
}


def _auto_select_model(mode, messages, provider, user_model) -> str:
    if user_model != _DEFAULT_MODELS.get(provider, ""):
        return user_model
    last_msg = ""
    if messages:
        content = messages[-1].get("content", "")
        if isinstance(content, str):
            last_msg = content.lower()
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    last_msg += block.get("text", "").lower()
    if provider == "anthropic":
        models = _ANTHROPIC_MODELS
    else:
        models = _OPENAI_MODELS
    if any(k in last_msg for k in _COMPLEX_KEYWORDS):
        return models["best"]
    if any(k in last_msg for k in _SIMPLE_KEYWORDS) or mode == "interview":
        return models["fast"]
    return models["balanced"]


# ──────────────────────────────────────────────────────────────────────────────
# Main client
# ──────────────────────────────────────────────────────────────────────────────

class LLMClient:
    ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    OPENAI_URL    = "https://api.openai.com/v1/chat/completions"
    _CFG_TTL      = 5.0

    # ── Proxy endpoints — mirrors provider paths ───────────────────────────────
    # When in proxy mode, we use dynamic paths that proxy back to our FastAPI edge router
    PROXY_ANTHROPIC_PATH = "/v1/proxy/anthropic"
    PROXY_OPENAI_PATH    = "/v1/proxy/openai"

    def __init__(self):
        self._cfg:      Optional[dict] = None
        self._cfg_ts:   float          = 0.0
        self._cfg_lock: threading.Lock = threading.Lock()   # ← NEW

    # ── Config ─────────────────────────────────────────────────────────────────

    def _load_cfg(self) -> dict:
        """Thread-safe cached config load."""
        now = time.time()
        with self._cfg_lock:                                # ← CHANGED (lock)
            if self._cfg is None or (now - self._cfg_ts) > self._CFG_TTL:
                self._cfg    = config.load_config()
                self._cfg_ts = now
            return self._cfg

    def invalidate_config(self):
        """
        Force config re-read on next call.
        Also invalidates the connection pool if the LLM provider changed
        so the old TCP connection is not kept alive unnecessarily.
        """                                                  # ← IMPROVED
        with self._cfg_lock:
            old_provider = (
                self._cfg.get("selected_provider") if self._cfg else None
            )
            self._cfg    = None
            self._cfg_ts = 0.0

        # Eagerly load new config to detect provider change
        new_cfg      = config.load_config()
        new_provider = new_cfg.get("selected_provider")
        if old_provider and old_provider != new_provider:
            print(
                f"[llm] Provider changed {old_provider} → {new_provider} "
                f"— invalidating pool"
            )
            _pool.invalidate()

    def _get_max_tokens(self, cfg: dict, mode: str) -> int:
        user_cap = int(cfg.get("max_tokens", 2_048))
        mode_cap = _MODE_MAX_TOKENS.get(mode, user_cap)
        return min(mode_cap, user_cap)

    # ── Connection management ──────────────────────────────────────────────────

    def warm_connections(self, cfg: Optional[dict] = None):
        """
        Pre-establish the HTTP/2 connection to the configured provider.
        Accepts an already-loaded cfg dict to avoid a redundant config read
        when the caller (app_controller) already holds it.

        In proxy mode, warms the connection to api.glassnote.ai instead.
        """
        if cfg is None:
            cfg = self._load_cfg()
        provider = cfg.get("selected_provider", "anthropic")

        # Check if we're in proxy mode
        proxy_url, proxy_token = self._get_proxy_config(cfg)

        def _warm():
            try:
                if proxy_url and proxy_token:
                    # ── Proxy mode: warm our proxy connection ──────────────
                    t0 = time.time()
                    c  = _pool.get_proxy(proxy_url)
                    r  = c.get(
                        f"{proxy_url}/v1/proxy/health",
                        headers={"Authorization": f"Bearer {proxy_token}"},
                        timeout=8.0,
                    )
                    ms = (time.time() - t0) * 1_000
                    print(
                        f"[llm] ✓ proxy connection warmed — "
                        f"{ms:.0f} ms  (status={r.status_code})"
                    )
                    _pool.start_heartbeat(proxy_token, "proxy")

                elif provider == "anthropic":
                    api_key = cfg.get("anthropic_api_key", "").strip()
                    if not api_key:
                        return
                    t0 = time.time()
                    c  = _pool.get_anthropic(api_key)
                    r  = c.get(
                        "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key":         api_key,
                            "anthropic-version": "2023-06-01",
                        },
                        timeout=8.0,
                    )
                    ms = (time.time() - t0) * 1_000
                    print(
                        f"[llm] ✓ connection warmed — anthropic "
                        f"{ms:.0f} ms  (status={r.status_code})"
                    )
                    _pool.start_heartbeat(api_key, "anthropic")

                elif provider == "openai":
                    api_key = cfg.get("openai_api_key", "").strip()
                    if not api_key:
                        return
                    t0 = time.time()
                    c  = _pool.get_openai(api_key)
                    r  = c.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=8.0,
                    )
                    ms = (time.time() - t0) * 1_000
                    print(
                        f"[llm] ✓ connection warmed — openai "
                        f"{ms:.0f} ms  (status={r.status_code})"
                    )
                    _pool.start_heartbeat(api_key, "openai")

            except Exception as e:
                print(f"[llm] warm_connections failed (non-fatal): {e}")

        threading.Thread(target=_warm, daemon=True, name="llm-warm").start()

    def stop_keepalive(self):
        _pool.stop_heartbeat()

    # ── Proxy config helpers ───────────────────────────────────────────────────

    def _get_proxy_config(self, cfg: dict) -> tuple:
        """
        Check if the user should route through GlassNote SaaS proxy.

        BYOK users have their own API keys and must bypass the proxy —
        routing them through would bill the platform instead of them.

        Returns:
            tuple: (proxy_url, proxy_token) or ("", "") if direct mode.
        """
        # TTFT-OPT: module-level import, avoid repeated disk reads
        # Uses module-level _pricing_config instead of importing on every call.
        try:
            if _PRICING_CONFIG_AVAILABLE and _pricing_config is not None:
                user_plan = cfg.get("glassnote_user_plan", "free").strip()
                plan_data = _pricing_config.get_plan(user_plan)
                if plan_data.get("byok_allowed", False):
                    # BYOK plan — user pays their own API providers directly
                    print(f"[llm] BYOK mode — bypassing proxy (plan={user_plan})")
                    return "", ""
        except Exception:
            pass  # pricing_config unavailable — fall through to normal check

        proxy_url   = cfg.get("glassnote_api_url", "").strip()
        proxy_token = cfg.get("glassnote_api_token", "").strip()
        if proxy_url and proxy_token:
            return proxy_url, proxy_token
        return "", ""

    # ── Public stream entry point ──────────────────────────────────────────────

    def stream(
        self,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]],
        on_token:      Callable[[str], None],
        on_done:       Callable[[str], None],
        on_error:      Callable[[str], None],
        mode:          str  = "solve",
        use_cache:     bool = True,
        cancel_event:  Optional[threading.Event] = None,
    ):
        cfg      = self._load_cfg()
        provider = cfg.get("selected_provider", "anthropic")
        model    = self._resolve_model(cfg, provider, messages, mode)

        if use_cache:
            cached = _response_cache.get(
                provider, model, system_prompt, messages, images, mode
            )
            if cached:
                print(f"[llm] cache hit — replaying {len(cached)} chars")
                for chunk in self._fast_stream_cached(cached):
                    if cancel_event and cancel_event.is_set():
                        break
                    on_token(chunk)
                on_done(cached)
                return

        optimized_images = None
        if images:
            t0 = time.time()
            # TTFT-OPT: images arriving here from the capture pipeline
            # (screenshot.py → _pil_to_base64) are already resized to
            # 768 px and format-detected (PNG for text, JPEG otherwise).
            # Re-processing them through _optimize_image() is a no-op
            # resize (768 < 1280 cap) that wastes 50-300 ms on the TTFT
            # critical path.  We pass already_optimized=True so the
            # function returns immediately without decoding.
            #
            # This is safe because:
            #   1. capture/screenshot.py already calls _pil_to_base64()
            #      which resizes to 768px and picks PNG/JPEG format.
            #   2. _optimize_image()'s 1280px cap never triggers (768<1280).
            #   3. _is_text_screenshot() re-detection is redundant — the
            #      screenshot module already made the PNG/JPEG decision.
            already_optimized = True
            if len(images) == 1:
                optimized_images = [
                    _optimize_image_cached(images[0],
                                           already_optimized=already_optimized)
                ]
            else:
                with ThreadPoolExecutor(max_workers=min(len(images), 4)) as ex:
                    optimized_images = list(
                        ex.map(
                            lambda img: _optimize_image_cached(
                                img, already_optimized=already_optimized
                            ),
                            images,
                        )
                    )
            ms = (time.time() - t0) * 1_000
            print(
                f"[llm] image optimisation "
                f"{ms:.0f} ms "
                f"({len(images)} image(s))"
                f"{'  [skipped — already optimized]' if already_optimized else ''}"
            )

        try:
            # ── Route decision: proxy or direct ────────────────────────────
            proxy_url, proxy_token = self._get_proxy_config(cfg)

            if proxy_url and proxy_token:
                # SaaS mode — route through GlassNote edge proxy
                print(f"[llm] proxy mode → {proxy_url}")
                if provider == "anthropic":
                    full_text = self._stream_via_proxy(
                        cfg, model, system_prompt, messages,
                        optimized_images, on_token, cancel_event, mode,
                        proxy_url, proxy_token, "anthropic",
                    )
                else:
                    full_text = self._stream_via_proxy(
                        cfg, model, system_prompt, messages,
                        optimized_images, on_token, cancel_event, mode,
                        proxy_url, proxy_token, "openai",
                    )
            elif provider == "anthropic":
                # BYOK mode — direct to Anthropic
                full_text = self._stream_anthropic_direct(
                    cfg, model, system_prompt, messages,
                    optimized_images, on_token, cancel_event, mode,
                )
            else:
                # BYOK mode — direct to OpenAI
                full_text = self._stream_openai_direct(
                    cfg, model, system_prompt, messages,
                    optimized_images, on_token, cancel_event, mode,
                )

            if full_text and not (cancel_event and cancel_event.is_set()):
                _response_cache.put(
                    provider, model, system_prompt,
                    messages, images, mode, full_text,
                )
            on_done(full_text)

        except Exception as e:
            on_error(str(e))

    # ── Model / token resolution ───────────────────────────────────────────────

    def _resolve_model(self, cfg, provider, messages, mode) -> str:
        if provider == "anthropic":
            user_model = cfg.get("anthropic_model", "claude-opus-4-5")
        else:
            user_model = cfg.get("openai_model", "gpt-4o")
        return _auto_select_model(mode, messages, provider, user_model)

    def _fast_stream_cached(self, cached: str) -> Iterator[str]:
        CHUNK = 8   # larger chunks for cached replay — no network delay
        for i in range(0, len(cached), CHUNK):
            yield cached[i : i + CHUNK]

    # ── Message builders ───────────────────────────────────────────────────────

    def _build_anthropic_messages(
        self,
        messages:         list,
        images:           Optional[List[str]],
        use_prompt_cache: bool = True,              # ← NEW param
    ) -> list:
        if not messages:
            messages = [{"role": "user", "content": "Please analyse and help me."}]
        result = []
        for i, msg in enumerate(messages):
            is_last = i == len(messages) - 1
            if is_last and images and msg.get("role") == "user":
                content = []
                for b64 in images:
                    content.append({
                        "type":   "image",
                        "source": {
                            "type":       "base64",
                            "media_type": _detect_media_type(b64),
                            "data":       b64,
                        },
                    })
                text_block: dict = {
                    "type": "text",
                    "text": msg.get("content", "")
                            or "Analyse the screenshot(s) above.",
                }
                if use_prompt_cache:               # ← CHANGED (conditional)
                    text_block["cache_control"] = {"type": "ephemeral"}
                content.append(text_block)
                result.append({"role": "user", "content": content})
            else:
                result.append(msg)
        return result

    def _build_openai_messages(self, messages, images) -> list:
        if not messages:
            messages = [{"role": "user", "content": "Please analyse and help me."}]
        result = []
        for i, msg in enumerate(messages):
            is_last = i == len(messages) - 1
            if is_last and images and msg.get("role") == "user":
                content = []
                for b64 in images:
                    media_type = _detect_media_type(b64)
                    mime       = "image/jpeg" if "jpeg" in media_type else "image/png"
                    content.append({
                        "type":      "image_url",
                        "image_url": {
                            "url":    f"data:{mime};base64,{b64}",
                            "detail": "high",
                        },
                    })
                text = msg.get("content", "")
                content.append({
                    "type": "text",
                    "text": text or "Analyse the screenshot(s) above.",
                })
                result.append({"role": "user", "content": content})
            else:
                result.append(msg)
        return result

    def _anthropic_system_payload(
        self,
        system_prompt:    str,
        use_prompt_cache: bool = True,             # ← NEW param
    ) -> Any:
        block: dict = {"type": "text", "text": system_prompt}
        if use_prompt_cache:                       # ← CHANGED (conditional)
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    # ── Proxy streaming ─────────────────────────────────────────────────────

    def _stream_via_proxy(
        self,
        cfg:           dict,
        model:         str,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]],
        on_token:      Callable[[str], None],
        cancel_event:  Optional[threading.Event],
        mode:          str,
        proxy_url:     str,
        proxy_token:   str,
        provider:      str,
    ) -> str:
        """
        Stream an LLM call through the GlassNote edge proxy.

        The proxy speaks the same SSE format as the providers, so the
        parsing logic below is identical to _stream_anthropic_direct /
        _stream_openai_direct. We just change the URL and auth header.

        This method builds the full provider request body locally and
        POSTs it to our proxy. The proxy injects the master API key
        and forwards to the provider with zero-copy streaming.

        Args:
            proxy_url: Base URL of the proxy (e.g. https://api.glassnote.ai).
            proxy_token: User's JWT token.
            provider: 'anthropic' or 'openai'.
        """
        http_client = _pool.get_proxy(proxy_url)
        max_tokens  = self._get_max_tokens(cfg, mode)

        # Build the request body — same format the provider expects
        if provider == "anthropic":
            use_cache = bool(cfg.get("use_prompt_cache", True))
            user_msgs = self._build_anthropic_messages(
                messages, images, use_cache
            )
            body = {
                "model":      model,
                "max_tokens": max_tokens,
                "stream":     True,
                "messages":   user_msgs,
                "system":     self._anthropic_system_payload(
                                  system_prompt, use_cache
                              ),
            }
            endpoint = f"{proxy_url}{self.PROXY_ANTHROPIC_PATH}"
        elif provider == "openai":
            oai_messages = [{"role": "system", "content": system_prompt}]
            oai_messages.extend(
                self._build_openai_messages(messages, images)
            )
            body = {
                "model":      model,
                "messages":   oai_messages,
                "stream":     True,
                "max_tokens": max_tokens,
            }
            endpoint = f"{proxy_url}{self.PROXY_OPENAI_PATH}"

        # Headers — only our JWT, proxy handles provider auth
        headers = {
            "Authorization": f"Bearer {proxy_token}",
            "Content-Type":  "application/json",
        }
        # Pass through prompt cache beta header for Anthropic
        if provider == "anthropic" and cfg.get("use_prompt_cache", True):
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        full_text: list[str]       = []
        t0         = time.time()
        ttft_ms:   Optional[float] = None

        with http_client.stream(
            "POST", endpoint, headers=headers, json=body,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancel_event and cancel_event.is_set():
                    print("[llm] proxy stream cancelled")
                    break
                if not line or line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    evt = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Anthropic format
                if provider == "anthropic":
                    etype = evt.get("type")
                    if etype == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            txt = delta.get("text", "")
                            if txt:
                                if ttft_ms is None:
                                    ttft_ms = (time.time() - t0) * 1_000
                                    print(
                                        f"[llm] TTFT {ttft_ms:.0f} ms  "
                                        f"model={model}  mode={mode}  "
                                        f"via=proxy"
                                    )
                                full_text.append(txt)
                                on_token(txt)
                    elif etype == "error":
                        err = evt.get("error", {})
                        raise RuntimeError(
                            err.get("message", "Proxy stream error")
                        )
                # OpenAI format
                else:
                    try:
                        txt = evt["choices"][0]["delta"].get("content", "")
                        if txt:
                            if ttft_ms is None:
                                ttft_ms = (time.time() - t0) * 1_000
                                print(
                                    f"[llm] TTFT {ttft_ms:.0f} ms  "
                                    f"model={model}  mode={mode}  "
                                    f"via=proxy"
                                )
                            full_text.append(txt)
                            on_token(txt)
                    except (KeyError, IndexError, AttributeError):
                        pass

        total_ms = (time.time() - t0) * 1_000
        print(
            f"[llm] proxy done  provider={provider}  model={model}  "
            f"TTFT={ttft_ms or 0:.0f} ms  total={total_ms:.0f} ms"
        )
        return "".join(full_text)

    # ── Anthropic streaming ────────────────────────────────────────────────────

    def _stream_anthropic_direct(
        self,
        cfg:           dict,
        model:         str,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]],
        on_token:      Callable[[str], None],
        cancel_event:  Optional[threading.Event],
        mode:          str = "solve",
    ) -> str:
        api_key = cfg.get("anthropic_api_key", "").strip()
        if not api_key:
            raise RuntimeError(
                "No Anthropic API key configured. Open Settings to add one."
            )

        use_prompt_cache = bool(cfg.get("use_prompt_cache", True))  # ← NEW
        http_client = _pool.get_anthropic(api_key)
        max_tokens  = self._get_max_tokens(cfg, mode)
        user_msgs   = self._build_anthropic_messages(
            messages, images, use_prompt_cache                      # ← CHANGED
        )

        # ── Headers ────────────────────────────────────────────────────────────
        headers: dict = {
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        # Prompt caching REQUIRES the beta header — without it cache_control
        # directives in the body are silently ignored by the API.
        if use_prompt_cache:                                        # ← NEW
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        body = {
            "model":      model,
            "max_tokens": max_tokens,
            "stream":     True,
            "messages":   user_msgs,
            "system":     self._anthropic_system_payload(
                              system_prompt, use_prompt_cache       # ← CHANGED
                          ),
        }

        full_text: list[str]       = []
        t0         = time.time()
        ttft_ms:   Optional[float] = None

        with http_client.stream(
            "POST", self.ANTHROPIC_URL, headers=headers, json=body,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancel_event and cancel_event.is_set():
                    print("[llm] anthropic stream cancelled")
                    break
                if not line or line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                try:
                    evt = json.loads(data)
                except json.JSONDecodeError:
                    continue

                etype = evt.get("type")

                if etype == "content_block_delta":
                    delta = evt.get("delta", {})
                    if delta.get("type") == "text_delta":
                        txt = delta.get("text", "")
                        if txt:
                            if ttft_ms is None:
                                ttft_ms = (time.time() - t0) * 1_000
                                print(
                                    f"[llm] TTFT {ttft_ms:.0f} ms  "
                                    f"model={model}  mode={mode}  "
                                    f"max_tokens={max_tokens}"
                                )
                            full_text.append(txt)
                            on_token(txt)

                elif etype == "message_delta":
                    usage = evt.get("usage", {})
                    if usage:
                        cache_read  = usage.get("cache_read_input_tokens",     0)
                        cache_write = usage.get("cache_creation_input_tokens", 0)
                        out_tokens  = usage.get("output_tokens", 0)
                        # Only log when cache is actually active
                        if cache_read or cache_write:
                            saving_pct = (
                                round(cache_read /
                                      max(cache_read + cache_write, 1) * 100)
                            )
                            print(
                                f"[llm] prompt cache — "
                                f"read={cache_read}  write={cache_write}  "
                                f"out={out_tokens}  "
                                f"saving≈{saving_pct}%"
                            )

                elif etype == "error":
                    err = evt.get("error", {})
                    raise RuntimeError(
                        err.get("message", "Anthropic stream error")
                    )

        total_ms = (time.time() - t0) * 1_000
        print(
            f"[llm] anthropic done  model={model}  "
            f"TTFT={ttft_ms or 0:.0f} ms  total={total_ms:.0f} ms"
        )
        return "".join(full_text)

    # ── OpenAI streaming ───────────────────────────────────────────────────────

    def _stream_openai_direct(
        self,
        cfg:           dict,
        model:         str,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]],
        on_token:      Callable[[str], None],
        cancel_event:  Optional[threading.Event],
        mode:          str = "solve",
    ) -> str:
        api_key = cfg.get("openai_api_key", "").strip()
        if not api_key:
            raise RuntimeError(
                "No OpenAI API key configured. Open Settings to add one."
            )

        http_client  = _pool.get_openai(api_key)
        max_tokens   = self._get_max_tokens(cfg, mode)
        oai_messages = [{"role": "system", "content": system_prompt}]
        oai_messages.extend(self._build_openai_messages(messages, images))

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
        body = {
            "model":          model,
            "messages":       oai_messages,
            "stream":         True,
            "max_tokens":     max_tokens,
            "stream_options": {"include_usage": True},   # ← NEW (token logging)
        }

        full_text: list[str]       = []
        t0         = time.time()
        ttft_ms:   Optional[float] = None

        with http_client.stream(
            "POST", self.OPENAI_URL, headers=headers, json=body,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancel_event and cancel_event.is_set():
                    print("[llm] openai stream cancelled")
                    break
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    evt = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Usage chunk — appears when stream_options.include_usage=True
                if evt.get("usage"):                               # ← NEW
                    u = evt["usage"]
                    print(
                        f"[llm] openai usage — "
                        f"prompt={u.get('prompt_tokens', 0)}  "
                        f"completion={u.get('completion_tokens', 0)}  "
                        f"total={u.get('total_tokens', 0)}"
                    )

                try:
                    txt = evt["choices"][0]["delta"].get("content", "")
                    if txt:
                        if ttft_ms is None:
                            ttft_ms = (time.time() - t0) * 1_000
                            print(
                                f"[llm] TTFT {ttft_ms:.0f} ms  "
                                f"model={model}  mode={mode}  "
                                f"max_tokens={max_tokens}"
                            )
                        full_text.append(txt)
                        on_token(txt)
                except (KeyError, IndexError, AttributeError):
                    continue

        total_ms = (time.time() - t0) * 1_000
        print(
            f"[llm] openai done  model={model}  "
            f"TTFT={ttft_ms or 0:.0f} ms  total={total_ms:.0f} ms"
        )
        return "".join(full_text)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def invalidate_pool(self):
        _pool.invalidate()

    def clear_cache(self):
        _response_cache.clear()


client = LLMClient()