"""
Auth service — JWT token management and password hashing.

Provides:
    - Password hashing with bcrypt
    - JWT creation and verification
    - FastAPI dependency for extracting current user from requests
"""
import warnings
warnings.filterwarnings("ignore", message=".*bcrypt version.*")


from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# ── Password hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    Args:
        password: Plain-text password.

    Returns:
        str: bcrypt hash string.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.

    Args:
        plain_password: User-provided password.
        hashed_password: Stored bcrypt hash.

    Returns:
        bool: True if password matches.
    """
    if not hashed_password:
        return False
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Catch UnknownHashError or others if the stored string is invalid
        return False


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    email: str,
    plan: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    The token contains the user's ID, email, and plan in the payload.
    This avoids a database lookup on every proxied request (critical
    for keeping proxy latency <1ms).

    Args:
        user_id: User UUID as string.
        email: User email.
        plan: User's subscription plan.
        expires_delta: Custom expiry (defaults to settings.jwt_expire_minutes).

    Returns:
        str: Signed JWT string.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub":   user_id,
        "email": email,
        "plan":  plan,
        "exp":   expire,
        "iat":   datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT string from Authorization header.

    Returns:
        dict: Decoded payload with 'sub', 'email', 'plan'.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """
    FastAPI dependency: extract and verify the current user from JWT.

    This is the auth check used on every proxied request.
    It does NOT hit the database — all user info is in the JWT payload.
    This keeps auth overhead at <0.5ms.

    In debug mode, allows unauthenticated access for local testing.

    Returns:
        dict: User info with 'sub' (user_id), 'email', 'plan'.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    settings = get_settings()

    if settings.debug and (not credentials or not credentials.credentials):
        # Return a mock user for local development
        return {
            "sub": "local-dev-user",
            "email": "dev@localhost",
            "plan": "pro"
        }

    return decode_access_token(credentials.credentials)
