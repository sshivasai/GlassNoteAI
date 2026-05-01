"""
Auth Router — registration, login, email verification, Google OAuth,
profile management, device binding, and account deletion.

Endpoints:
    POST /api/auth/register          — create account, sends OTP
    POST /api/auth/verify-otp        — verify OTP, returns token
    POST /api/auth/login             — authenticate with device binding
    POST /api/auth/google            — Google OAuth (id_token, web/mobile)
    GET  /api/auth/google-url        — get Google OAuth URL for desktop app
    POST /api/auth/google-callback   — exchange auth code (desktop OAuth flow)
    POST /api/auth/refresh           — refresh expiring token
    GET  /api/auth/me                — current user info + plan
    PUT  /api/auth/profile           — update first_name / last_name
    DELETE /api/auth/account         — permanently delete account
    POST /api/auth/unlink-device     — self-service device unlink
    POST /api/auth/resend-otp        — resend verification OTP
"""

import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import User, UsageQuota, EmailOTP, Session, ApiCall
from app.services.auth import (
    hash_password, verify_password, create_access_token, get_current_user,
)
from app.services.database import get_db
from app.config import get_settings
from app.pricing_config import get_plan, get_quota_period

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Constants ─────────────────────────────────────────────────────────────────
OTP_TTL_MINUTES  = 10
OTP_MAX_ATTEMPTS = 5
DEVICE_UNLINK_LIMIT_PER_MONTH = 2
MIN_PASSWORD_LENGTH = 8

# ── Request / Response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:      EmailStr
    password:   str
    first_name: str = ""
    last_name:  str = ""
    device_id:  str = ""

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        return v

class VerifyOTPRequest(BaseModel):
    email:     EmailStr
    code:      str
    device_id: str = ""

class LoginRequest(BaseModel):
    email:     EmailStr
    password:  str
    device_id: str = ""

class ResendOTPRequest(BaseModel):
    email: EmailStr

class GoogleAuthRequest(BaseModel):
    credential: str  # Google id_token from frontend
    device_id:  str = ""

class ProfileUpdateRequest(BaseModel):
    first_name: str = ""
    last_name:  str = ""

class DeleteAccountRequest(BaseModel):
    password: str = ""  # Required for email accounts, empty for Google accounts

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    plan:         str
    email:        str
    first_name:   str = ""
    last_name:    str = ""

class OTPSentResponse(BaseModel):
    status:  str = "otp_sent"
    message: str
    email:   str = ""

class UserResponse(BaseModel):
    id:                 str
    email:              str
    first_name:         str = ""
    last_name:          str = ""
    plan:               str
    byok_enabled:       bool = False
    is_verified:        bool
    device_bound:       bool
    auth_provider:      str = "email"
    sessions_used:      int = 0
    sessions_limit:     int = 5
    sessions_remaining: int = -1    # -1 = unlimited; BACKEND-2
    period:             str = ""

# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))

async def _send_otp_email(email: str, code: str, settings) -> None:
    if not getattr(settings, "sendgrid_api_key", ""):
        print(f"[auth] 📧 OTP for {email}: {code}  (configure SENDGRID_API_KEY for real emails)")
        return
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content, ReplyTo
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)

        # IMPORTANT: 'from_email' MUST be a domain verified in SendGrid.
        # Go to SendGrid → Settings → Sender Authentication → Domain Authentication
        # and authenticate your sending domain (e.g. glassnote.ai).
        # Using a personal Gmail as the From: address causes DMARC failures with Gmail.
        from_address = Email(settings.from_email, "GlassNote")
        to_address   = To(email)
        reply_to     = ReplyTo(settings.reply_email, "GlassNote Support")

        html_body = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"></head>
        <body style="font-family:'Segoe UI',Arial,sans-serif;background:#0d0d10;margin:0;padding:40px 0;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
            <table width="480" cellpadding="0" cellspacing="0"
                   style="background:#111115;border-radius:16px;border:1px solid #1e1e24;overflow:hidden;">
              <tr><td style="background:#111115;padding:28px 36px 20px;border-bottom:1px solid #1e1e24;">
                <span style="color:#5b8ff9;font-size:22px;font-weight:700;letter-spacing:-0.5px;">◈ GlassNote</span>
              </td></tr>
              <tr><td style="padding:32px 36px;">
                <p style="color:#e0e0e8;font-size:15px;margin:0 0 8px;">Your verification code:</p>
                <div style="background:#0d0d10;border:1px solid #252530;border-radius:10px;
                            padding:20px;text-align:center;margin:16px 0;">
                  <span style="color:#5b8ff9;font-size:38px;font-weight:700;
                               letter-spacing:16px;font-family:monospace;">{code}</span>
                </div>
                <p style="color:#888;font-size:13px;margin:0 0 6px;">⏱ This code expires in {OTP_TTL_MINUTES} minutes.</p>
                <p style="color:#555;font-size:12px;margin:0;">If you didn't create a GlassNote account, you can safely ignore this email.</p>
              </td></tr>
              <tr><td style="padding:16px 36px;border-top:1px solid #1e1e24;">
                <p style="color:#555;font-size:11px;margin:0;">© 2025 GlassNote AI • <a href="https://glassnote.ai" style="color:#5b8ff9;">glassnote.ai</a></p>
              </td></tr>
            </table>
          </td></tr></table>
        </body></html>"""

        message = Mail(
            from_email=from_address,
            to_emails=to_address,
            subject="Your GlassNote Verification Code",
            html_content=html_body,
        )
        message.reply_to = reply_to
        sg.send(message)
        print(f"[auth] 📧 Verification email sent to {email}")
    except Exception as e:
        print(f"[auth] ⚠ Email send failed for {email}: {e}")

async def _get_or_create_quota(db: AsyncSession, user_id: str, plan_id: str) -> UsageQuota:
    from app.pricing_config import get_plan_limits
    period = get_quota_period(plan_id)
    result = await db.execute(
        select(UsageQuota).where(UsageQuota.user_id == user_id, UsageQuota.period == period)
    )
    quota = result.scalar_one_or_none()
    if not quota:
        quota = UsageQuota(user_id=user_id, period=period, sessions_limit=get_plan_limits(plan_id))
        db.add(quota)
        await db.flush()
    return quota

async def _create_and_send_otp(db: AsyncSession, user: User, settings) -> str:
    existing_otps = await db.execute(
        select(EmailOTP).where(EmailOTP.user_id == user.id, EmailOTP.used == False)
    )
    for otp in existing_otps.scalars().all():
        otp.used = True
    code = _generate_otp()
    otp = EmailOTP(
        user_id=user.id, code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(otp)
    await db.flush()
    await _send_otp_email(user.email, code, settings)
    return code

def _make_token_response(user: User, token: str) -> TokenResponse:
    return TokenResponse(
        access_token=token, plan=user.plan, email=user.email,
        first_name=user.first_name or "", last_name=user.last_name or "",
    )


async def _expire_plan_if_needed(user: User, db: AsyncSession) -> bool:
    """
    Downgrade the user to free if their paid plan has passed its expiry date.

    Called on every login and /me request so expiry is enforced without
    needing a background scheduler job.

    Returns True if the plan was downgraded, False otherwise.
    """
    if user.plan == "free":
        return False  # free plan has no expiry
    if not user.plan_expires_at:
        return False  # no expiry set — admin-granted or legacy row
    now = datetime.now(timezone.utc)
    expires = user.plan_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        old_plan = user.plan
        user.plan = "free"
        user.plan_expires_at = None
        await db.flush()
        print(f"[auth] Plan expired — {user.email}: {old_plan} → free")
        return True
    return False

# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=OTPSentResponse, status_code=202)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account and send an OTP for email verification.

    Edge cases:
    - If email exists but is_verified=False → update name/password, resend OTP.
    - If email exists and is_verified=True → 409 "already have an account".
    """
    settings = get_settings()
    email = req.email.lower()

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an account. Please sign in instead.",
            )
        # Unverified — update their info and resend OTP
        existing.first_name = req.first_name or existing.first_name
        existing.last_name = req.last_name or existing.last_name
        existing.hashed_password = hash_password(req.password)
        if req.device_id:
            existing.bound_device_id = req.device_id
        await _create_and_send_otp(db, existing, settings)
        return OTPSentResponse(
            message=f"A new verification code has been sent to {email}.",
            email=email,
        )

    user = User(
        email=email, hashed_password=hash_password(req.password),
        first_name=req.first_name, last_name=req.last_name,
        plan="free", is_verified=False,
        bound_device_id=req.device_id or None,
    )
    db.add(user)
    await db.flush()
    await _get_or_create_quota(db, str(user.id), "free")
    await _create_and_send_otp(db, user, settings)
    print(f"[auth] New user registered (unverified): {email}")
    return OTPSentResponse(
        message=f"A 6-digit verification code has been sent to {email}. It expires in {OTP_TTL_MINUTES} minutes.",
        email=email,
    )

# ── Verify OTP ────────────────────────────────────────────────────────────────

@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    email = req.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")

    otp_result = await db.execute(
        select(EmailOTP).where(EmailOTP.user_id == user.id, EmailOTP.used == False)
        .order_by(EmailOTP.created_at.desc()).limit(1)
    )
    otp = otp_result.scalar_one_or_none()
    if not otp:
        raise HTTPException(400, "No active verification code found. Please request a new one.")

    now = datetime.now(timezone.utc)
    if otp.expires_at.replace(tzinfo=timezone.utc) < now:
        otp.used = True
        raise HTTPException(400, "Verification code has expired. Please request a new one.")
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        otp.used = True
        raise HTTPException(400, "Too many failed attempts. Please request a new verification code.")
    if otp.code != req.code.strip():
        otp.attempts += 1
        remaining = OTP_MAX_ATTEMPTS - otp.attempts
        raise HTTPException(400, f"Incorrect verification code. {remaining} attempts remaining.")

    otp.used = True
    user.is_verified = True
    if req.device_id and not user.bound_device_id:
        user.bound_device_id = req.device_id

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        byok_enabled=user.byok_enabled
    )
    print(f"[auth] ✓ Email verified: {user.email} (plan={user.plan}, byok={user.byok_enabled})")
    return _make_token_response(user, token)

# ── Resend OTP ────────────────────────────────────────────────────────────────

@router.post("/resend-otp", response_model=OTPSentResponse, status_code=202)
async def resend_otp(req: ResendOTPRequest, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    email = req.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return OTPSentResponse(message=f"If an account exists for {email}, a new code has been sent.", email=email)
    if user.is_verified:
        raise HTTPException(400, "This account is already verified. Please sign in.")
    await _create_and_send_otp(db, user, settings)
    return OTPSentResponse(message=f"A new verification code has been sent to {email}.", email=email)

# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Edge cases:
    - Invalid credentials → 401
    - Account inactive → 403
    - Unverified → 403, auto-resend OTP, return needs_verification flag
    - Device mismatch → 403
    """
    settings = get_settings()
    email = req.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password.")

    if not user.is_active:
        raise HTTPException(403, "Your account has been deactivated. Please update billing at glassnote.ai.")

    if not user.is_verified:
        # Auto-resend OTP and tell frontend to show verification screen
        await _create_and_send_otp(db, user, settings)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first. A new code has been sent to your inbox.",
        )

    # Device binding
    incoming_device = req.device_id
    if incoming_device:
        if not user.bound_device_id:
            user.bound_device_id = incoming_device
        elif user.bound_device_id != incoming_device:
            raise HTTPException(403, "This account is linked to a different device. Unlink at glassnote.ai.")

    # Expire plan if needed before issuing token
    await _expire_plan_if_needed(user, db)

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        byok_enabled=user.byok_enabled
    )
    print(f"[auth] Login: {user.email} (plan={user.plan}, byok={user.byok_enabled})")
    return _make_token_response(user, token)

# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.post("/google", response_model=TokenResponse)
async def google_auth(req: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify Google id_token and either log in or create a new verified account.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(500, "Google OAuth not configured on server.")

    # Verify Google token
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            req.credential, google_requests.Request(), settings.google_client_id
        )
    except Exception as e:
        raise HTTPException(401, f"Invalid Google credential: {e}")

    google_id = idinfo.get("sub", "")
    email = idinfo.get("email", "").lower()
    first_name = idinfo.get("given_name", "")
    last_name = idinfo.get("family_name", "")

    if not email:
        raise HTTPException(400, "Google account has no email.")

    # Check if user exists by google_id or email
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        # Existing user — link Google if not already
        if not user.google_id:
            user.google_id = google_id
            user.auth_provider = "google"
        user.is_verified = True
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if req.device_id and not user.bound_device_id:
            user.bound_device_id = req.device_id
    else:
        # New user — create verified account instantly
        user = User(
            email=email, hashed_password="GOOGLE_OAUTH_NO_PASSWORD",
            first_name=first_name, last_name=last_name,
            auth_provider="google", google_id=google_id,
            plan="free", is_verified=True,
            bound_device_id=req.device_id or None,
        )
        db.add(user)
        await db.flush()
        await _get_or_create_quota(db, str(user.id), "free")
        print(f"[auth] New Google user: {email}")

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        byok_enabled=user.byok_enabled
    )
    return _make_token_response(user, token)


# ── Google OAuth — URL Generator (desktop app uses this) ─────────────────────

@router.get("/google-url")
async def get_google_auth_url():
    """
    Generate the Google OAuth authorization URL for the desktop app.

    The desktop app opens this URL in the system browser. The user logs in
    with Google. Google redirects to localhost:9999/callback with a 'code'.
    The desktop app then calls /api/auth/google-callback with that code.

    Keeping the client_id server-side means the GUI never needs to know it.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(500, "Google OAuth not configured on server.")

    # Build Google OAuth URL
    import urllib.parse
    params = {
        "client_id":     settings.google_client_id,
        "redirect_uri":  "http://localhost:9999/callback",
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": url}


# ── Google OAuth — Code Exchange (desktop callback) ───────────────────────────

class GoogleCallbackRequest(BaseModel):
    code:      str
    device_id: str = ""

@router.post("/google-callback", response_model=TokenResponse)
async def google_callback(req: GoogleCallbackRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange the Google authorization code (from localhost callback) for a GlassNote token.

    Called by the desktop app after receiving the code from the browser redirect.
    The server exchanges the code with Google directly for the id_token.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(500, "Google OAuth not configured on server.")

    # Exchange code for tokens with Google
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient() as client:
            r = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code":          req.code,
                    "client_id":     settings.google_client_id,
                    "client_secret": getattr(settings, "google_client_secret", ""),
                    "redirect_uri":  "http://localhost:9999/callback",
                    "grant_type":    "authorization_code",
                },
            )
        if r.status_code != 200:
            raise HTTPException(401, f"Google token exchange failed: {r.text[:200]}")
        tokens = r.json()
        id_token_str = tokens.get("id_token", "")
    except Exception as e:
        raise HTTPException(401, f"Google OAuth error: {e}")

    # Verify the id_token
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.google_client_id
        )
    except Exception as e:
        raise HTTPException(401, f"Invalid Google id_token: {e}")

    google_id  = idinfo.get("sub", "")
    email      = idinfo.get("email", "").lower()
    first_name = idinfo.get("given_name", "")
    last_name  = idinfo.get("family_name", "")

    if not email:
        raise HTTPException(400, "Google account has no email.")

    # Upsert user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()
    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id    = google_id
            user.auth_provider = "google"
        user.is_verified = True
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if req.device_id and not user.bound_device_id:
            user.bound_device_id = req.device_id
    else:
        user = User(
            email=email, hashed_password="GOOGLE_OAUTH_NO_PASSWORD",
            first_name=first_name, last_name=last_name,
            auth_provider="google", google_id=google_id,
            plan="free", is_verified=True,
            bound_device_id=req.device_id or None,
        )
        db.add(user)
        await db.flush()
        await _get_or_create_quota(db, str(user.id), "free")
        print(f"[auth] New Google user (desktop): {email}")

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        byok_enabled=user.byok_enabled
    )
    return _make_token_response(user, token)

# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    plan  = db_user.plan  if db_user else user.get("plan", "free")
    email = db_user.email if db_user else user.get("email", "")
    byok_enabled = db_user.byok_enabled if db_user else user.get("byok_enabled", False)
    token = create_access_token(user_id=user["sub"], email=email, plan=plan, byok_enabled=byok_enabled)
    if db_user:
        return _make_token_response(db_user, token)
    return TokenResponse(access_token=token, plan=plan, email=email)

# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found.")

    # Check and apply plan expiry before returning current state
    await _expire_plan_if_needed(db_user, db)

    plan = db_user.plan
    period = get_quota_period(plan)
    quota_result = await db.execute(
        select(UsageQuota).where(UsageQuota.user_id == user["sub"], UsageQuota.period == period)
    )
    quota      = quota_result.scalar_one_or_none()
    plan_cfg   = get_plan(plan)
    used       = quota.sessions_used if quota else 0
    limit      = plan_cfg["sessions_per_month"]
    # -1 = unlimited for plans with limit >= 9999 (unlimited plan)
    remaining  = -1 if limit >= 9999 else max(0, limit - used)

    return UserResponse(
        id=user["sub"], email=db_user.email,
        first_name=db_user.first_name or "", last_name=db_user.last_name or "",
        plan=plan,
        byok_enabled=db_user.byok_enabled,
        is_verified=db_user.is_verified,
        device_bound=bool(db_user.bound_device_id),
        auth_provider=db_user.auth_provider or "email",
        sessions_used=used,
        sessions_limit=limit,
        sessions_remaining=remaining,
        period=period,
    )

# ── Profile Update ────────────────────────────────────────────────────────────

@router.put("/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found.")

    if req.first_name:
        db_user.first_name = req.first_name
    if req.last_name:
        db_user.last_name = req.last_name

    return {"status": "ok", "first_name": db_user.first_name, "last_name": db_user.last_name}


# ── Toggle BYOK ───────────────────────────────────────────────────────────────

class ToggleBYOKRequest(BaseModel):
    enabled: bool


@router.post("/toggle-byok")
async def toggle_byok(
    req: ToggleBYOKRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable or disable BYOK (Bring Your Own Keys) for the current user.

    BYOK is now a user account setting, not a plan. Any user on any plan
    (Free, Base, Unlimited) can toggle BYOK to use their own API keys
    instead of the platform's proxy.

    When BYOK is enabled:
    - User must configure their own API keys in the GUI Settings
    - /stt-credentials endpoint returns 403
    - LLM client bypasses the proxy and uses user's keys directly

    Plan limits still apply (Free users with BYOK enabled still get
    basic models only, unless they upgrade to Base/Unlimited).

    Returns:
        New JWT token with updated byok_enabled claim, plus confirmation.
    """
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found")

    # Update BYOK status
    db_user.byok_enabled = req.enabled
    await db.commit()

    # Issue new JWT with updated byok_enabled claim
    new_token = create_access_token(
        user_id=str(db_user.id),
        email=db_user.email,
        plan=db_user.plan,
        byok_enabled=req.enabled
    )

    action = "enabled" if req.enabled else "disabled"
    print(f"[auth] BYOK {action}: {db_user.email} (plan={db_user.plan})")

    return {
        "access_token": new_token,
        "byok_enabled": req.enabled,
        "message": f"BYOK {action} successfully. "
                   f"{'Configure your API keys in Settings to use BYOK.' if req.enabled else 'You are now using the platform proxy.'}"
    }


# ── Delete Account ────────────────────────────────────────────────────────────

@router.delete("/account")
async def delete_account(
    req: DeleteAccountRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found.")

    # Require password confirmation for email accounts
    if db_user.auth_provider == "email":
        if not req.password:
            raise HTTPException(400, "Password confirmation required to delete account.")
        if not verify_password(req.password, db_user.hashed_password):
            raise HTTPException(401, "Incorrect password.")

    user_id = db_user.id
    # Delete related data
    await db.execute(sa_delete(EmailOTP).where(EmailOTP.user_id == user_id))
    await db.execute(sa_delete(ApiCall).where(
        ApiCall.session_id.in_(select(Session.id).where(Session.user_id == user_id))
    ))
    await db.execute(sa_delete(Session).where(Session.user_id == user_id))
    await db.execute(sa_delete(UsageQuota).where(UsageQuota.user_id == user_id))
    await db.delete(db_user)

    print(f"[auth] Account deleted: {db_user.email}")
    return {"status": "ok", "message": "Your account has been permanently deleted."}

# ── Unlink Device ─────────────────────────────────────────────────────────────

@router.post("/unlink-device")
async def unlink_device(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user or not db_user.bound_device_id:
        raise HTTPException(400, "No device is currently linked to this account.")

    now = datetime.now(timezone.utc)
    if db_user.device_unlink_reset_at:
        reset_ts = db_user.device_unlink_reset_at.replace(tzinfo=timezone.utc)
        if now > reset_ts:
            db_user.device_unlink_count = 0
            db_user.device_unlink_reset_at = now + timedelta(days=30)
    else:
        db_user.device_unlink_reset_at = now + timedelta(days=30)

    if db_user.device_unlink_count >= DEVICE_UNLINK_LIMIT_PER_MONTH:
        raise HTTPException(429, f"Device unlink limit ({DEVICE_UNLINK_LIMIT_PER_MONTH}/month) exceeded.")

    db_user.bound_device_id = None
    db_user.device_unlink_count += 1
    return {
        "status": "ok",
        "message": "Device unlinked. Your next login on any device will bind it.",
        "unlinks_remaining": DEVICE_UNLINK_LIMIT_PER_MONTH - db_user.device_unlink_count,
    }
