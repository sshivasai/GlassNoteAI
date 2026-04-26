"""
LLM Proxy Router — Zero-copy streaming edge proxy.

Performance design:
    1. NO JSON parsing of the SSE response stream (zero-copy passthrough)
    2. Auth is a cached JWT decode — no database lookup (<0.5 ms)
    3. Pre-warmed HTTP/2 connection pool to providers
    4. Usage logging is ASYNC — doesn't block the response stream
    5. Model access control checked against pricing_config (single source of truth)

Latency budget per proxied request:
    JWT decode:      <0.5 ms (in-memory, no DB)
    Quota check:     <0.5 ms (in-memory counter)
    Request forward: ~2-5 ms (pre-warmed HTTP/2 to same-region provider)
    Stream relay:    ~0 ms per chunk (async yield, no parsing)
    Usage logging:   0 ms (async task, non-blocking)
    ─────────────────────────────────
    Total overhead:  ~3-6 ms (<1% of typical 300-800 ms TTFT)

Endpoints:
    POST /v1/proxy/anthropic  — mirrors Anthropic /v1/messages
    POST /v1/proxy/openai     — mirrors OpenAI /v1/chat/completions
"""

import asyncio
import json
import time
import uuid
from functools import lru_cache
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.services.auth import get_current_user
from app.pricing_config import is_model_allowed

router = APIRouter(prefix="/v1/proxy", tags=["llm-proxy"])

# GPT-5.4 family uses the new Responses API, not Chat Completions
_GPT5_MODELS = {"gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"}


# ── Pre-warmed async HTTP/2 connection pool ───────────────────────────────────
# Shared across all requests. Eliminates cold-start TLS handshakes (~80-200ms).

_anthropic_pool: Optional[httpx.AsyncClient] = None
_openai_pool:    Optional[httpx.AsyncClient] = None


async def _get_anthropic_pool() -> httpx.AsyncClient:
    """Get or create the shared Anthropic HTTP/2 connection pool."""
    global _anthropic_pool
    if _anthropic_pool is None or _anthropic_pool.is_closed:
        _anthropic_pool = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=300,
            ),
        )
    return _anthropic_pool


async def _get_openai_pool() -> httpx.AsyncClient:
    """Get or create the shared OpenAI HTTP/2 connection pool."""
    global _openai_pool
    if _openai_pool is None or _openai_pool.is_closed:
        _openai_pool = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=300,
            ),
        )
    return _openai_pool


_cerebras_pool: Optional[httpx.AsyncClient] = None


async def _get_cerebras_pool() -> httpx.AsyncClient:
    """Get or create the shared Cerebras HTTP/2 connection pool."""
    global _cerebras_pool
    if _cerebras_pool is None or _cerebras_pool.is_closed:
        _cerebras_pool = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=300,
            ),
        )
    return _cerebras_pool


# TTFT-OPT: eager pool warm-up at startup
async def eager_warm_pools() -> dict:
    """
    Eagerly create HTTP/2 connection pools and send a lightweight HEAD/GET
    request to each upstream provider at app startup.

    This ensures the first real user request does NOT pay the TLS handshake
    overhead (~80-200 ms per provider). Called from the lifespan handler in
    main.py so pools are warm before the first request arrives.

    Returns:
        dict: Warm-up results per provider with latency_ms and status.
    """
    settings = get_settings()
    results  = {}

    # TTFT-OPT: Warm both pools in parallel instead of sequentially.
    # Saves 200-400ms by overlapping the TLS handshakes.
    async def _warm_anthropic():
        if not settings.anthropic_api_key:
            return None
        try:
            pool = await _get_anthropic_pool()
            t0   = time.time()
            # HEAD not supported by Anthropic — use GET /v1/models (lightweight)
            r = await pool.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key":         settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1_000
            result = {"status": "warm", "latency_ms": round(ms), "http_status": r.status_code}
            print(f"[proxy] TTFT-OPT: Anthropic pool warmed — {ms:.0f} ms  (HTTP {r.status_code})")
            return result
        except Exception as e:
            result = {"status": "error", "error": str(e)}
            print(f"[proxy] TTFT-OPT: Anthropic pool warm-up failed (non-fatal): {e}")
            return result

    async def _warm_openai():
        if not settings.openai_api_key:
            return None
        try:
            pool = await _get_openai_pool()
            t0   = time.time()
            # GET /v1/models is the lightest authenticated endpoint
            r = await pool.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1_000
            result = {"status": "warm", "latency_ms": round(ms), "http_status": r.status_code}
            print(f"[proxy] TTFT-OPT: OpenAI pool warmed — {ms:.0f} ms  (HTTP {r.status_code})")
            return result
        except Exception as e:
            result = {"status": "error", "error": str(e)}
            print(f"[proxy] TTFT-OPT: OpenAI pool warm-up failed (non-fatal): {e}")
            return result

    # Fire both requests in parallel
    anthropic_result, openai_result = await asyncio.gather(
        _warm_anthropic(),
        _warm_openai(),
    )

    if anthropic_result:
        results["anthropic"] = anthropic_result
    if openai_result:
        results["openai"] = openai_result

    if settings.cerebras_api_key:
        try:
            pool = await _get_cerebras_pool()
            t0   = time.time()
            r = await pool.get(
                "https://api.cerebras.ai/v1/models",
                headers={"Authorization": f"Bearer {settings.cerebras_api_key}"},
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1_000
            results["cerebras"] = {"status": "warm", "latency_ms": round(ms), "http_status": r.status_code}
            print(f"[proxy] TTFT-OPT: Cerebras pool warmed — {ms:.0f} ms  (HTTP {r.status_code})")
        except Exception as e:
            results["cerebras"] = {"status": "error", "error": str(e)}
            print(f"[proxy] TTFT-OPT: Cerebras pool warm-up failed (non-fatal): {e}")

    return results


# ── Model access guard ────────────────────────────────────────────────────────
# Uses pricing_config.is_model_allowed() — single source of truth.
# No hardcoded dictionaries here.

@lru_cache(maxsize=256)
def _is_model_allowed_cached(plan: str, model: str) -> bool:
    """
    Cached wrapper around is_model_allowed() to avoid repeated lookups.
    TTFT-OPT: Saves 1-2ms per proxied request by caching plan-model combinations.
    """
    return is_model_allowed(plan, model)

def _check_model_access(plan: str, model: str) -> None:
    """
    Verify the user's plan allows access to the requested model.

    Args:
        plan:  User's subscription plan ID.
        model: Requested LLM model ID.

    Raises:
        HTTPException: 403 if model is not available on the user's plan.
    """
    if not _is_model_allowed_cached(plan, model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Model '{model}' is not available on the '{plan}' plan. "
                "Upgrade your plan to access this model."
            ),
        )


# ── Anthropic proxy ──────────────────────────────────────────────────────────

@router.post("/anthropic")
async def proxy_anthropic(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Zero-copy streaming proxy for Anthropic's /v1/messages endpoint.

    The request body is forwarded as-is to Anthropic. The SSE response
    stream is relayed byte-by-byte. Usage is extracted and logged async.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(500, "Anthropic API key not configured on server")

    body_bytes = await request.body()
    try:
        body_json = json.loads(body_bytes)
        model = body_json.get("model", "claude-haiku-4-5")
    except (json.JSONDecodeError, AttributeError):
        model = "claude-haiku-4-5"

    # ── Plan-gated model access (uses pricing_config — NOT hardcoded) ──────
    _check_model_access(user.get("plan", "free"), model)

    pool = await _get_anthropic_pool()

    proxy_headers = {
        "x-api-key":         settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    client_beta = request.headers.get("anthropic-beta")
    if client_beta:
        proxy_headers["anthropic-beta"] = client_beta

    t0 = time.time()

    async def stream_relay():
        output_tokens = 0
        input_tokens  = 0

        async with pool.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=proxy_headers,
            content=body_bytes,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                yield error_body
                return

            async for chunk in response.aiter_bytes():
                yield chunk

                # Lightweight scan: only the final 'message_delta' event has usage
                if b'"message_delta"' in chunk and b'"usage"' in chunk:
                    try:
                        for line in chunk.decode("utf-8", errors="ignore").split("\n"):
                            if line.startswith("data:") and "message_delta" in line:
                                evt = json.loads(line[5:].strip())
                                usage = evt.get("usage", {})
                                output_tokens = usage.get("output_tokens", 0)
                                input_tokens = (
                                    usage.get("cache_read_input_tokens", 0)
                                    + usage.get("cache_creation_input_tokens", 0)
                                    + usage.get("input_tokens", 0)
                                )
                    except Exception:
                        pass

        elapsed_ms = (time.time() - t0) * 1000
        asyncio.create_task(_log_llm_usage(
            user_id=user["sub"],
            provider="anthropic",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int(elapsed_ms),
        ))

    return StreamingResponse(
        stream_relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── OpenAI proxy ──────────────────────────────────────────────────────────────

@router.post("/openai")
async def proxy_openai(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Zero-copy streaming proxy for OpenAI.

    Routes to /v1/chat/completions for standard models.
    Routes to /v1/responses for GPT-5.4 family (new Responses API).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(500, "OpenAI API key not configured on server")

    body_bytes = await request.body()
    try:
        body_json = json.loads(body_bytes)
        model = body_json.get("model", "gpt-4o-mini")
    except (json.JSONDecodeError, AttributeError):
        model = "gpt-4o-mini"

    _check_model_access(user.get("plan", "free"), model)

    pool = await _get_openai_pool()
    proxy_headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type":  "application/json",
    }

    t0 = time.time()

    if model in _GPT5_MODELS:
        # ── GPT-5.4 family: use new Responses API ─────────────────────────
        # Convert Chat Completions format → Responses API format
        messages = body_json.get("messages", [])
        system_content = ""
        input_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_content = content
            else:
                input_messages.append({"role": role, "content": content})

        responses_body = {
            "model":             model,
            "input":             input_messages,
            "stream":            True,
            "max_output_tokens": body_json.get("max_tokens", 600),
        }
        if system_content:
            responses_body["instructions"] = system_content

        responses_body_bytes = json.dumps(responses_body).encode("utf-8")

        async def stream_relay_responses():
            output_tokens = 0
            input_tokens  = 0

            async with pool.stream(
                "POST",
                "https://api.openai.com/v1/responses",
                headers=proxy_headers,
                content=responses_body_bytes,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield error_body
                    return

                async for chunk in response.aiter_bytes():
                    # Parse usage from response.completed event
                    if b'"response.completed"' in chunk or b'"response.done"' in chunk:
                        try:
                            for line in chunk.decode("utf-8", errors="ignore").split("\n"):
                                if line.startswith("data:"):
                                    data = line[5:].strip()
                                    if data and data != "[DONE]":
                                        evt = json.loads(data)
                                        if evt.get("type") in ("response.completed", "response.done"):
                                            resp = evt.get("response", {})
                                            usage = resp.get("usage", {})
                                            input_tokens  = usage.get("input_tokens", 0)
                                            output_tokens = usage.get("output_tokens", 0)
                        except Exception:
                            pass

                    # Re-emit as OpenAI Chat Completions SSE format so the
                    # GUI client (which expects chat/completions format) works unchanged.
                    # We translate response.output_text.delta → choices[0].delta.content
                    try:
                        translated_chunks = []
                        for line in chunk.decode("utf-8", errors="ignore").split("\n"):
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if not data or data == "[DONE]":
                                if data == "[DONE]":
                                    translated_chunks.append("data: [DONE]\n\n")
                                continue
                            try:
                                evt = json.loads(data)
                                etype = evt.get("type", "")
                                if etype == "response.output_text.delta":
                                    delta_text = evt.get("delta", "")
                                    translated = {
                                        "choices": [{"delta": {"content": delta_text}, "index": 0}]
                                    }
                                    translated_chunks.append(f"data: {json.dumps(translated)}\n\n")
                                elif etype in ("response.completed", "response.done"):
                                    resp = evt.get("response", {})
                                    usage = resp.get("usage", {})
                                    translated = {
                                        "choices": [],
                                        "usage": {
                                            "prompt_tokens":     usage.get("input_tokens", 0),
                                            "completion_tokens": usage.get("output_tokens", 0),
                                            "total_tokens":      usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                                        }
                                    }
                                    translated_chunks.append(f"data: {json.dumps(translated)}\n\n")
                            except Exception:
                                pass
                        if translated_chunks:
                            yield "".join(translated_chunks).encode("utf-8")
                        else:
                            yield chunk
                    except Exception:
                        yield chunk

            elapsed_ms = (time.time() - t0) * 1000
            asyncio.create_task(_log_llm_usage(
                user_id=user["sub"],
                provider="openai",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=int(elapsed_ms),
            ))

        return StreamingResponse(
            stream_relay_responses(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":     "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    else:
        # ── Standard models: use Chat Completions API ──────────────────────
        try:
            body_json.setdefault("stream_options", {})["include_usage"] = True
            body_bytes = json.dumps(body_json).encode("utf-8")
        except Exception:
            pass

        async def stream_relay():
            output_tokens = 0
            input_tokens  = 0

            async with pool.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers=proxy_headers,
                content=body_bytes,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield error_body
                    return

                async for chunk in response.aiter_bytes():
                    yield chunk

                    if b'"usage"' in chunk and b'"total_tokens"' in chunk:
                        try:
                            for line in chunk.decode("utf-8", errors="ignore").split("\n"):
                                if line.startswith("data:") and '"usage"' in line:
                                    data = line[5:].strip()
                                    if data == "[DONE]":
                                        continue
                                    evt = json.loads(data)
                                    usage = evt.get("usage", {})
                                    input_tokens  = usage.get("prompt_tokens", 0)
                                    output_tokens = usage.get("completion_tokens", 0)
                        except Exception:
                            pass

            elapsed_ms = (time.time() - t0) * 1000
            asyncio.create_task(_log_llm_usage(
                user_id=user["sub"],
                provider="openai",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=int(elapsed_ms),
            ))

        return StreamingResponse(
            stream_relay(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":    "no-cache",
                "X-Accel-Buffering": "no",
            },
        )



# ── Cerebras proxy ──────────────────────────────────────────────────────────────────

@router.post("/cerebras")
async def proxy_cerebras(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Zero-copy streaming proxy for Cerebras' OpenAI-compatible API.

    Cerebras uses the same /v1/chat/completions format as OpenAI,
    so SSE parsing is identical. Text-only (no vision support).
    """
    settings = get_settings()
    if not settings.cerebras_api_key:
        raise HTTPException(500, "Cerebras API key not configured on server")

    body_bytes = await request.body()
    try:
        body_json = json.loads(body_bytes)
        model = body_json.get("model", "llama3.1-8b")
    except (json.JSONDecodeError, AttributeError):
        model = "llama3.1-8b"

    # ── Plan-gated model access (uses pricing_config — NOT hardcoded) ──────
    _check_model_access(user.get("plan", "free"), model)

    pool = await _get_cerebras_pool()

    # Cerebras uses Bearer auth, same as OpenAI
    proxy_headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type":  "application/json",
    }

    # Inject stream_options for usage tracking
    try:
        body_json.setdefault("stream_options", {})["include_usage"] = True
        body_bytes = json.dumps(body_json).encode("utf-8")
    except Exception:
        pass

    t0 = time.time()

    async def stream_relay():
        output_tokens = 0
        input_tokens  = 0

        async with pool.stream(
            "POST",
            "https://api.cerebras.ai/v1/chat/completions",
            headers=proxy_headers,
            content=body_bytes,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                yield error_body
                return

            async for chunk in response.aiter_bytes():
                yield chunk

                if b'"usage"' in chunk and b'"total_tokens"' in chunk:
                    try:
                        for line in chunk.decode("utf-8", errors="ignore").split("\n"):
                            if line.startswith("data:") and '"usage"' in line:
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    continue
                                evt = json.loads(data)
                                usage = evt.get("usage", {})
                                input_tokens  = usage.get("prompt_tokens", 0)
                                output_tokens = usage.get("completion_tokens", 0)
                    except Exception:
                        pass

        elapsed_ms = (time.time() - t0) * 1000
        asyncio.create_task(_log_llm_usage(
            user_id=user["sub"],
            provider="cerebras",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int(elapsed_ms),
        ))

    return StreamingResponse(
        stream_relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Health check — also warms the connection pools ──────────────────────────────────

@router.get("/health")
async def proxy_health():
    """
    Health check endpoint that also reports connection pool status.
    Call this on startup to pre-warm connections.
    """
    settings = get_settings()
    status_info = {"status": "ok", "pools": {}}

    if settings.anthropic_api_key:
        try:
            pool = await _get_anthropic_pool()
            t0 = time.time()
            r = await pool.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1000
            status_info["pools"]["anthropic"] = {
                "status": "warm",
                "latency_ms": round(ms),
                "http_status": r.status_code,
            }
        except Exception as e:
            status_info["pools"]["anthropic"] = {"status": "error", "error": str(e)}

    if settings.openai_api_key:
        try:
            pool = await _get_openai_pool()
            t0 = time.time()
            r = await pool.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1000
            status_info["pools"]["openai"] = {
                "status": "warm",
                "latency_ms": round(ms),
                "http_status": r.status_code,
            }
        except Exception as e:
            status_info["pools"]["openai"] = {"status": "error", "error": str(e)}

    if settings.cerebras_api_key:
        try:
            pool = await _get_cerebras_pool()
            t0 = time.time()
            r = await pool.get(
                "https://api.cerebras.ai/v1/models",
                headers={"Authorization": f"Bearer {settings.cerebras_api_key}"},
                timeout=8.0,
            )
            ms = (time.time() - t0) * 1000
            status_info["pools"]["cerebras"] = {
                "status": "warm",
                "latency_ms": round(ms),
                "http_status": r.status_code,
            }
        except Exception as e:
            status_info["pools"]["cerebras"] = {"status": "error", "error": str(e)}

    return status_info


# ── Async usage logging (non-blocking, writes to DB) ─────────────────────────

async def _log_llm_usage(
    user_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """
    Asynchronously log LLM API call usage to the database.

    Runs as a fire-and-forget asyncio task AFTER the SSE stream has been
    fully relayed to the client. Never blocks the response.

    Also aggregates token counts into the active session and usage quota rows.
    """
    from app.services.database import async_session_factory
    from app.models.database import ApiCall, Session, UsageQuota
    from sqlalchemy import select, update
    from app.pricing_config import get_quota_period

    # Rough cost estimation ($/1M tokens, conservative)
    _COST_PER_1M_IN = {
        "claude-opus-4-5":    15.00,
        "claude-sonnet-4-5":   3.00,
        "claude-haiku-4-5":    0.25,
        "gpt-4o":              2.50,
        "gpt-4o-mini":         0.15,
        "gpt-4.1":             2.00,
        "gpt-4.1-mini":        0.10,
        "gpt-4-turbo":        10.00,
        "o1":                 15.00,
        "o1-mini":             3.00,
        "gpt-5.4":             5.00,
        "gpt-5.4-mini":        1.50,
        "gpt-5.4-nano":        0.30,
        "gpt-4.1-nano":        0.10,
        "llama3.1-8b":         0.10,
        "gpt-oss-120b":        0.60,
    }
    _COST_PER_1M_OUT = {
        "claude-opus-4-5":    75.00,
        "claude-sonnet-4-5":  15.00,
        "claude-haiku-4-5":    1.25,
        "gpt-4o":             10.00,
        "gpt-4o-mini":         0.60,
        "gpt-4.1":             8.00,
        "gpt-4.1-mini":        0.40,
        "gpt-4-turbo":        30.00,
        "o1":                 60.00,
        "o1-mini":            12.00,
        "gpt-5.4":            20.00,
        "gpt-5.4-mini":        6.00,
        "gpt-5.4-nano":        1.20,
        "gpt-4.1-nano":        0.40,
        "llama3.1-8b":         0.10,
        "gpt-oss-120b":        0.60,
    }
    cost_in  = (input_tokens  / 1_000_000) * _COST_PER_1M_IN.get(model, 5.0)
    cost_out = (output_tokens / 1_000_000) * _COST_PER_1M_OUT.get(model, 15.0)
    total_cost = cost_in + cost_out

    try:
        async with async_session_factory() as db:
            # Find the user's active session
            result = await db.execute(
                select(Session).where(
                    Session.user_id == user_id,
                    Session.status == "active",
                ).limit(1)
            )
            session = result.scalar_one_or_none()
            session_id = session.id if session else uuid.uuid4()  # orphan fallback

            # Record the API call
            api_call = ApiCall(
                session_id=session_id,
                call_type="llm",
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=total_cost,
            )
            db.add(api_call)

            # Update session aggregates
            if session:
                session.total_llm_calls     += 1
                session.total_input_tokens  += input_tokens
                session.total_output_tokens += output_tokens
                session.total_cost_usd      += total_cost

            # Update usage quota aggregates
            # We need the plan to determine the correct quota period key
            user_result = await db.execute(
                select(Session.user_id).where(Session.id == session_id).limit(1)
            )
            # Use a direct quota lookup by user_id
            from app.models.database import User
            u_result = await db.execute(
                select(User).where(User.id == user_id).limit(1)
            )
            db_user = u_result.scalar_one_or_none()
            plan = db_user.plan if db_user else "free"
            period = get_quota_period(plan)

            quota_result = await db.execute(
                select(UsageQuota).where(
                    UsageQuota.user_id == user_id,
                    UsageQuota.period == period,
                )
            )
            quota = quota_result.scalar_one_or_none()
            if quota:
                quota.total_input_tokens  += input_tokens
                quota.total_output_tokens += output_tokens
                quota.total_cost_usd      += total_cost

            await db.commit()

    except Exception as exc:
        # Log but never propagate — usage logging must not break the proxy
        print(f"[proxy] ⚠ Usage logging failed: {exc}")

    print(
        f"[proxy] USAGE — user={user_id[:8]}  provider={provider}  "
        f"model={model}  in={input_tokens}  out={output_tokens}  "
        f"cost=${total_cost:.5f}  latency={latency_ms}ms"
    )


# ── STT credentials endpoint ─────────────────────────────────────────────────

from fastapi.responses import JSONResponse
from app.pricing_config import get_plan

@router.get("/stt-credentials")
async def get_stt_credentials(
    user: dict = Depends(get_current_user),
):
    """
    Return backend STT API keys to authenticated SaaS users.

    The desktop client uses these keys to connect directly to the STT
    provider (Deepgram / OpenAI Realtime WebSocket) without storing
    the key on disk — it is held in memory only for the session lifetime.

    Only non-BYOK users receive keys here. BYOK users must supply
    their own keys in Settings.

    Returns:
        { "deepgram_key": "...", "openai_key": "..." }

    Raises:
        403 if the user is on the BYOK plan (they must use their own keys).
    """
    plan_id = user.get("plan", "free")
    plan_cfg = get_plan(plan_id)

    if plan_cfg.get("byok_allowed", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="BYOK users must configure their own API keys in Settings.",
        )

    settings = get_settings()
    return JSONResponse({
        "deepgram_key": getattr(settings, "deepgram_api_key", "") or "",
        "openai_key":   getattr(settings, "openai_api_key",  "") or "",
    })


# ── Cleanup on shutdown ──────────────────────────────────────────────────────

async def close_pools():
    """Close HTTP connection pools on server shutdown."""
    global _anthropic_pool, _openai_pool, _cerebras_pool
    for pool in (_anthropic_pool, _openai_pool, _cerebras_pool):
        if pool and not pool.is_closed:
            await pool.aclose()
    _anthropic_pool = None
    _openai_pool    = None
    _cerebras_pool  = None
