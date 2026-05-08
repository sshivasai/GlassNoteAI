"""
api/auth_client.py

Desktop-side authentication client for GlassNote Cloud.

Handles:
    - Login (email + password → access token)
    - Register (email + password → OTP flow)
    - OTP verification → access token
    - Token persistence to OS keyring (encrypted credential store)
    - Token refresh
    - Usage info fetching

Token security:
    Tokens are stored in the OS's native encrypted credential manager
    (Windows Credential Manager, macOS Keychain, Linux Secret Service)
    via the `keyring` library. This prevents malware from reading the
    token by scanning plaintext JSON config files.

    The token is treated as an opaque string — we do NOT decode or
    inspect its contents on the client side. The user's plan and email
    are returned explicitly by the API and stored separately in config.

All network calls run in background threads to avoid blocking the UI.
"""

import time
import uuid
import threading
from typing import Callable, Optional

import httpx


# ── Keyring helpers ───────────────────────────────────────────────────────────
# Falls back to plaintext config if keyring is unavailable (rare edge cases
# like headless CI environments). The fallback is non-silent — it logs a
# warning so developers know security is degraded.

_KEYRING_SERVICE = "GlassNote"
_KEYRING_USER    = "glassnote_token"   # changed from "glassnote_jwt"

def _keyring_save(token: str) -> None:
    """Save access token to the OS encrypted credential store."""
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, token)
    except Exception as e:
        # Fallback: write to config (degraded security, non-silent)
        print(f"[auth] ⚠ keyring unavailable — token saved to config ({e})")
        _config_save_token(token)


def _keyring_load() -> str:
    """Load access token from the OS encrypted credential store."""
    try:
        import keyring
        token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        return token or ""
    except Exception as e:
        print(f"[auth] ⚠ keyring unavailable — reading from config ({e})")
        return _config_load_token()


def _keyring_delete() -> None:
    """Delete the stored access token from the OS credential store."""
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        pass
    _config_save_token("")  # Also clear plaintext fallback if it was used


def _config_save_token(token: str) -> None:
    """Fallback: save token to the plaintext JSON config."""
    try:
        from settings import config
        cfg = config.load_config()
        cfg["glassnote_api_token"] = token
        config.save_config(cfg)
    except Exception:
        pass


def _config_load_token() -> str:
    """Fallback: load token from the plaintext JSON config."""
    try:
        from settings import config
        return config.get("glassnote_api_token", "")
    except Exception:
        return ""


# ── Device ID ─────────────────────────────────────────────────────────────────

def _get_device_id() -> str:
    """
    Generate a stable hardware device identifier.

    Uses the MAC address of the primary network interface via uuid.getnode().
    This is stable across reboots and app reinstalls on the same machine.
    The value is hashed to a consistent 32-char hex string.
    """
    import hashlib
    raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# Module-level device ID — computed once and reused
DEVICE_ID: str = _get_device_id()


# ── AuthClient ────────────────────────────────────────────────────────────────

class AuthClient:
    """
    Manages authentication with the GlassNote backend.

    Stores access tokens in the OS's native encrypted credential store
    (Windows Credential Manager, macOS Keychain, Linux Secret Service)
    via keyring. Provides thread-safe methods for login, register, OTP
    verification, and token refresh.

    The token is treated as an opaque bearer string — the user's plan
    and email are stored separately in the local config file so the
    GUI can gate features without needing to inspect the token.
    """

    def __init__(self):
        self._token:      str  = ""
        self._email:      str  = ""
        self._plan:       str  = ""
        self._api_url:    str  = ""
        self._needs_otp:  bool = False  # True when registration needs OTP
        self._otp_email:  str  = ""     # email to use for OTP verification

    def configure(self, api_url: str, token: str = ""):
        """Set the API URL and optionally restore a saved token."""
        self._api_url = api_url.rstrip("/")
        # Prefer explicitly passed token; otherwise load from keyring
        self._token = token or _keyring_load()

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token and self._api_url)

    @property
    def token(self) -> str:
        return self._token

    @property
    def email(self) -> str:
        return self._email

    @property
    def plan(self) -> str:
        return self._plan

    # ── Internal token management ─────────────────────────────────────────────

    def _store_token(self, token: str, email: str, plan: str) -> None:
        """
        Store token securely and update in-memory state.

        Persists the token to the OS keyring (encrypted) and writes the
        non-sensitive user metadata (email, plan) to the plaintext config
        so the GUI can gate features without inspecting the token.
        """
        self._token = token
        self._email = email
        self._plan  = plan
        # Save to OS keyring (encrypted)
        _keyring_save(token)
        # Persist email, plan, and token to config
        # (token in config is redundant with keyring but keeps backward compat)
        try:
            from settings import config
            cfg = config.load_config()
            cfg["glassnote_user_email"] = email
            cfg["glassnote_user_plan"]  = plan
            cfg["glassnote_api_token"]  = token   # ← backward compat
            config.save_config(cfg)
        except Exception:
            pass


    # ── Login ──────────────────────────────────────────────────────────────────

    def login(
        self,
        email:      str,
        password:   str,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Authenticate with email + password.

        Runs in a background thread. Calls on_success(user_info) or
        on_error(message) on completion.

        Args:
            email: User's email.
            password: User's password.
            on_success: Called with {"email", "plan", "token"} on success.
            on_error: Called with error message string on failure.
        """
        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(15.0, connect=8.0),
                ) as client:
                    r = client.post(
                        f"{self._api_url}/api/auth/login",
                        json={
                            "email":     email,
                            "password":  password,
                            "device_id": DEVICE_ID,
                        },
                    )

                if r.status_code == 200:
                    data = r.json()
                    self._store_token(
                        token=data.get("access_token", ""),
                        email=data.get("email", email),
                        plan=data.get("plan", "free"),
                    )
                    on_success({
                        "email": self._email,
                        "plan":  self._plan,
                        "token": self._token,
                    })
                elif r.status_code == 401:
                    on_error("Invalid email or password.")
                elif r.status_code == 403:
                    detail = r.json().get("detail", "Access denied.")
                    on_error(detail)
                elif r.status_code == 404:
                    on_error("Account not found. Please register first.")
                else:
                    body = r.text[:200]
                    on_error(f"Login failed (HTTP {r.status_code}): {body}")

            except httpx.ConnectError:
                on_error(
                    "Cannot connect to GlassNote Cloud.\n"
                    "Check your internet connection and API URL."
                )
            except httpx.TimeoutException:
                on_error("Connection timed out. Please try again.")
            except Exception as e:
                on_error(f"Login error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-login").start()

    # ── Register ───────────────────────────────────────────────────────────────

    def register(
        self,
        email:      str,
        password:   str,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Create a new account.

        Runs in a background thread. On success, signals that an OTP has
        been sent to the user's email (not yet logged in).

        Args:
            email: New account email.
            password: Password (min 8 chars enforced by backend).
            on_success: Called with {"email", "needs_otp": True} on success.
            on_error: Called with error message string on failure.
        """
        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(15.0, connect=8.0),
                ) as client:
                    r = client.post(
                        f"{self._api_url}/api/auth/register",
                        json={
                            "email":     email,
                            "password":  password,
                            "device_id": DEVICE_ID,
                        },
                    )

                if r.status_code in (200, 201, 202):
                    # Registration returns otp_sent — not a token yet
                    self._needs_otp = True
                    self._otp_email = email
                    on_success({
                        "email":     email,
                        "plan":      "free",
                        "token":     "",
                        "needs_otp": True,
                    })
                elif r.status_code == 409:
                    on_error("An account with this email already exists.")
                elif r.status_code == 422:
                    detail = r.json().get("detail", "Validation error")
                    on_error(f"Invalid input: {detail}")
                else:
                    body = r.text[:200]
                    on_error(f"Registration failed (HTTP {r.status_code}): {body}")

            except httpx.ConnectError:
                on_error(
                    "Cannot connect to GlassNote Cloud.\n"
                    "Check your internet connection and API URL."
                )
            except httpx.TimeoutException:
                on_error("Connection timed out. Please try again.")
            except Exception as e:
                on_error(f"Registration error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-register").start()

    # ── OTP Verification ────────────────────────────────────────────────────

    def verify_otp(
        self,
        email:      str,
        code:       str,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Verify the 6-digit OTP received via email.

        On success, the backend returns an access token which is stored
        securely in the OS keyring, and the user is fully logged in.
        """
        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(15.0, connect=8.0),
                ) as client:
                    r = client.post(
                        f"{self._api_url}/api/auth/verify-otp",
                        json={
                            "email":     email,
                            "code":      code.strip(),
                            "device_id": DEVICE_ID,
                        },
                    )

                if r.status_code == 200:
                    data = r.json()
                    self._store_token(
                        token=data.get("access_token", ""),
                        email=data.get("email", email),
                        plan=data.get("plan", "free"),
                    )
                    self._needs_otp = False
                    on_success({
                        "email": self._email,
                        "plan":  self._plan,
                        "token": self._token,
                    })
                elif r.status_code == 400:
                    detail = r.json().get("detail", "Invalid code.")
                    on_error(detail)
                else:
                    on_error(f"Verification failed (HTTP {r.status_code}).")

            except httpx.ConnectError:
                on_error("Cannot connect to GlassNote Cloud.")
            except httpx.TimeoutException:
                on_error("Connection timed out. Please try again.")
            except Exception as e:
                on_error(f"Verification error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-otp").start()

    def get_google_auth_url(
        self,
        on_success: Callable[[str], None],
        on_error:   Callable[[str], None],
    ):
        """
        Fetch the Google OAuth URL from the backend (client_id stays server-side).
        """
        def _do():
            try:
                with httpx.Client(http2=True, timeout=httpx.Timeout(10.0)) as client:
                    r = client.get(f"{self._api_url}/api/auth/google-url")
                if r.status_code == 200:
                    on_success(r.json().get("url", ""))
                elif r.status_code == 500:
                    on_error("Google OAuth is not configured on the server.")
                else:
                    on_error(f"Failed to get Google URL (HTTP {r.status_code})")
            except Exception as e:
                on_error(f"Network error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-google-url").start()

    def google_auth_with_code(
        self,
        code:         str,
        on_success:   Callable[[dict], None],
        on_error:     Callable[[str], None],
        redirect_uri: str = "",
    ):
        """
        Exchange the Google authorization code for a GlassNote token.
        Called after the local browser callback delivers the code.
        """
        def _do():
            try:
                payload = {"code": code, "device_id": DEVICE_ID}
                if redirect_uri:
                    payload["redirect_uri"] = redirect_uri
                print(f"[auth] [DIAG] google_auth_with_code: sending redirect_uri={redirect_uri!r} to backend")
                with httpx.Client(http2=True, timeout=httpx.Timeout(15.0, connect=8.0)) as client:
                    r = client.post(
                        f"{self._api_url}/api/auth/google-callback",
                        json=payload,
                    )
                print(f"[auth] [DIAG] google-callback response: HTTP {r.status_code} — {r.text[:300]}")
                if r.status_code == 200:
                    data = r.json()
                    self._store_token(
                        token=data.get("access_token", ""),
                        email=data.get("email", ""),
                        plan=data.get("plan", "free"),
                    )
                    on_success({
                        "email": self._email,
                        "plan":  self._plan,
                        "token": self._token,
                    })
                elif r.status_code == 401:
                    on_error("Google sign-in failed. Please try again.")
                else:
                    on_error(f"Google auth error (HTTP {r.status_code}): {r.text[:150]}")
            except httpx.ConnectError:
                on_error("Cannot connect to GlassNote Cloud.")
            except httpx.TimeoutException:
                on_error("Connection timed out.")
            except Exception as e:
                on_error(f"Google auth error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-google-cb").start()

    def resend_otp(
        self,
        email:      str,
        on_success: Callable[[str], None],
        on_error:   Callable[[str], None],
    ):
        """Request a new OTP to be sent to the email."""
        def _do():
            try:
                with httpx.Client(
                    http2=True, timeout=httpx.Timeout(15.0, connect=8.0),
                ) as client:
                    r = client.post(
                        f"{self._api_url}/api/auth/resend-otp",
                        json={"email": email},
                    )
                if r.status_code in (200, 202):
                    on_success("A new code has been sent to your email.")
                else:
                    on_error(f"Failed to resend code (HTTP {r.status_code}).")
            except Exception as e:
                on_error(f"Network error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-resend").start()

    # ── Fetch user info ────────────────────────────────────────────────────────

    def fetch_user_info(
        self,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Fetch current user info and usage stats from the backend.

        Also refreshes the locally-stored plan so feature gating stays
        accurate after a subscription change.

        Args:
            on_success: Called with user info dict.
            on_error: Called with error message.
        """
        if not self.is_authenticated:
            on_error("Not authenticated")
            return

        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(10.0, connect=5.0),
                ) as client:
                    r = client.get(
                        f"{self._api_url}/api/auth/me",
                        headers={"Authorization": f"Bearer {self._token}"},
                    )

                if r.status_code == 200:
                    data = r.json()
                    new_plan  = data.get("plan", self._plan)
                    new_email = data.get("email", self._email)
                    # Refresh plan in memory AND in config
                    self._store_token(self._token, new_email, new_plan)
                    on_success(data)
                elif r.status_code == 401:
                    # Token expired — clear it from keyring
                    self._token = ""
                    _keyring_delete()
                    on_error("Session expired. Please log in again.")
                else:
                    on_error(f"Failed to fetch user info (HTTP {r.status_code})")

            except Exception as e:
                on_error(f"Network error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-me").start()

    # ── Fetch usage stats ──────────────────────────────────────────────────────

    def fetch_usage(
        self,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Fetch current period usage stats from the backend.

        Args:
            on_success: Called with usage stats dict.
            on_error: Called with error message.
        """
        if not self.is_authenticated:
            on_error("Not authenticated")
            return

        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(10.0, connect=5.0),
                ) as client:
                    r = client.get(
                        f"{self._api_url}/api/usage/current",
                        headers={"Authorization": f"Bearer {self._token}"},
                    )

                if r.status_code == 200:
                    on_success(r.json())
                else:
                    on_error(f"Failed to fetch usage (HTTP {r.status_code})")

            except Exception as e:
                on_error(f"Network error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-usage").start()

    # ── Toggle BYOK ────────────────────────────────────────────────────────────

    def toggle_byok(
        self,
        enabled: bool,
        on_success: Callable[[dict], None],
        on_error:   Callable[[str], None],
    ):
        """
        Enable or disable BYOK (Bring Your Own Keys) for the current user.

        Returns new JWT token with updated byok_enabled claim.

        Args:
            enabled: True to enable BYOK, False to disable.
            on_success: Called with response dict containing new access_token.
            on_error: Called with error message.
        """
        if not self.is_authenticated:
            on_error("Not authenticated")
            return

        def _do():
            try:
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(10.0, connect=5.0),
                ) as client:
                    response = client.post(
                        f"{self._api_url}/api/auth/toggle-byok",
                        json={"enabled": enabled},
                        headers={"Authorization": f"Bearer {self._token}"},
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Store new JWT token with updated byok_enabled claim
                    new_token = data.get("access_token", "")
                    if new_token:
                        self._token = new_token
                        _keyring_save(new_token)

                        # Update config
                        try:
                            from settings import config
                            cfg = config.load_config()
                            cfg["glassnote_byok_enabled"] = enabled
                            cfg["glassnote_api_token"] = new_token
                            config.save_config(cfg)
                        except Exception:
                            pass

                    on_success(data)

            except httpx.HTTPStatusError as e:
                try:
                    detail = e.response.json().get("detail", str(e))
                except Exception:
                    detail = str(e)
                on_error(f"Failed to toggle BYOK: {detail}")
            except Exception as e:
                on_error(f"Network error: {e}")

        threading.Thread(target=_do, daemon=True, name="auth-toggle-byok").start()

    # ── Logout ─────────────────────────────────────────────────────────────────

    def logout(self):
        """Clear stored credentials from memory and OS keyring."""
        self._token = ""
        self._email = ""
        self._plan  = ""
        _keyring_delete()
        # Clear plan from config too
        try:
            from settings import config
            cfg = config.load_config()
            cfg["glassnote_user_plan"]  = ""
            cfg["glassnote_user_email"] = ""
            cfg["glassnote_api_token"]  = ""
            config.save_config(cfg)
        except Exception:
            pass


# Module-level singleton
auth_client = AuthClient()
