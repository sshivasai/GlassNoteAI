"""
GlassNote Backend — FastAPI Application Entry Point.

Architecture:
    - Edge proxy for LLM calls (zero-copy SSE streaming)
    - Auth via JWT (no DB lookup on proxied requests)
    - Session/usage metering (async, non-blocking)
    - Pre-warmed HTTP/2 connection pools to Anthropic and OpenAI
    - PostgreSQL via async SQLAlchemy (asyncpg)

Start locally:
    cd backend
    uvicorn app.main:app --reload --port 8000

Production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import time
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.routers import proxy, auth, sessions, usage, billing
from app.routers import notifications
from app.routers import public
from app.routers.proxy import close_pools, eager_warm_pools
from app.services.database import create_tables, close_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    On startup:
        - Creates database tables (development; use Alembic in production)
        - Pre-warms connection pools to LLM providers
    On shutdown:
        - Closes connection pools and DB engine
    """
    settings = get_settings()
    print(f"[glassnote] Starting {settings.app_name}")
    print(f"[glassnote] Debug mode: {settings.debug}")
    print(f"[glassnote] Anthropic key: {'✓' if settings.anthropic_api_key else '✗'}")
    print(f"[glassnote] OpenAI key:    {'✓' if settings.openai_api_key else '✗'}")

    # Create database tables
    print("[glassnote] Initializing database...")
    try:
        await create_tables()
    except Exception as e:
        print(f"[glassnote] ⚠ Database init failed: {e}")
        print("[glassnote]   Ensure PostgreSQL is running and DATABASE_URL is correct")

    # TTFT-OPT: eager pool warm-up at startup
    # Pre-warm HTTP/2 connection pools so the first user request does NOT
    # pay TLS handshake overhead (~80-200 ms per provider).
    print("[glassnote] Pre-warming provider connection pools (TTFT-OPT)...")
    try:
        results = await eager_warm_pools()
        for provider, info in results.items():
            status  = info.get("status", "unknown")
            latency = info.get("latency_ms", "?")
            print(f"[glassnote]   {provider}: {status} ({latency}ms)")
    except Exception as e:
        print(f"[glassnote]   Pool warming failed (non-fatal): {e}")

    print("[glassnote] ✓ Ready — accepting requests")

    yield  # App is running

    # Cleanup
    print("[glassnote] Shutting down...")
    await close_pools()
    await close_engine()
    print("[glassnote] ✓ Shutdown complete")


# ── Create app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GlassNote API",
    description=(
        "Edge proxy API for GlassNote — zero-latency LLM streaming, "
        "session management, and usage metering."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mount routers ─────────────────────────────────────────────────────────────

app.include_router(proxy.router)              # /v1/proxy/anthropic, /v1/proxy/openai
app.include_router(auth.router)               # /api/auth/register, /api/auth/login, etc.
app.include_router(sessions.router)           # /api/sessions/start, /api/sessions/end, etc.
app.include_router(usage.router)              # /api/usage/report-stt, /api/usage/current
app.include_router(billing.router)            # /api/billing/checkout, /api/billing/webhook, etc.
app.include_router(notifications.router)      # /api/notifications/active, /create, etc.
app.include_router(public.router)             # /api/public/pricing, /api/public/testimonials


# ── Rate Limiting Middleware ────────────────────────────────────────────────────
# Sliding window counter per user (extracted from JWT in auth header).
# Applied only to proxy endpoints to avoid adding latency to non-critical paths.

_rate_lock = threading.Lock()
_rate_counters: dict[str, list[float]] = {}  # user_id -> [timestamps]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user sliding window rate limiter for proxy endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit proxy endpoints
        if not request.url.path.startswith("/v1/proxy/"):
            return await call_next(request)

        # Extract user from JWT (quick decode, no DB)
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)  # Auth middleware will reject

        try:
            from app.services.auth import decode_access_token
            token = auth_header[7:]
            payload = decode_access_token(token)
            user_id = payload.get("sub", "anon")
            # Store decoded JWT payload in request.state so downstream route
            # handlers (e.g. get_current_user) can access it via
            # request.state.jwt_payload without re-decoding the token.
            request.state.jwt_payload = payload
        except Exception:
            return await call_next(request)

        # Check rate limit
        now   = time.time()
        limit = settings.rate_limit_per_minute

        with _rate_lock:
            timestamps = _rate_counters.setdefault(user_id, [])
            # Remove timestamps older than 60s
            cutoff = now - 60
            _rate_counters[user_id] = [t for t in timestamps if t > cutoff]
            timestamps = _rate_counters[user_id]

            if len(timestamps) >= limit:
                return Response(
                    content='{"error": "Rate limit exceeded. Please wait."}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": "60"},
                )
            timestamps.append(now)

        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


# ── Root health check ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """API root — basic health check."""
    return {
        "service": "GlassNote API",
        "version": "1.0.0",
        "status":  "ok",
        "docs":    "/docs",
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns basic server status. For detailed pool health,
    use /v1/proxy/health instead.
    """
    return {"status": "ok"}
