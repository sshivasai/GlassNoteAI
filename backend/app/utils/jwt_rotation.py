"""
backend/app/utils/jwt_rotation.py — JWT key rotation support.

Allows seamless key rotation by supporting multiple valid signing keys
during the transition period.

Usage:
    from app.utils.jwt_rotation import MultiKeyJWT

    jwt_manager = MultiKeyJWT(
        current_key="new-secret",
        old_keys=["old-secret-1", "old-secret-2"]
    )

    token = jwt_manager.encode(payload)
    payload = jwt_manager.decode(token)  # Works with any valid key
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from jose import JWTError, jwt


class MultiKeyJWT:
    """
    JWT manager with support for key rotation.

    Features:
      - Sign with current key
      - Verify with current + old keys (transition period)
      - Automatic key expiry
    """

    def __init__(
        self,
        current_key: str,
        old_keys: Optional[List[str]] = None,
        algorithm: str = "HS256",
    ):
        """
        Initialize JWT manager.

        Args:
            current_key: Current signing key
            old_keys: List of old keys that are still valid
            algorithm: JWT algorithm
        """
        self.current_key = current_key
        self.old_keys = old_keys or []
        self.algorithm = algorithm

    def encode(
        self,
        payload: dict,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Encode payload to JWT using current key.

        Args:
            payload: JWT payload
            expires_delta: Optional expiry time

        Returns:
            str: Signed JWT token
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
            payload = payload.copy()
            payload["exp"] = expire

        return jwt.encode(payload, self.current_key, algorithm=self.algorithm)

    def decode(self, token: str) -> dict:
        """
        Decode JWT using current or old keys.

        Tries current key first, then falls back to old keys.

        Args:
            token: JWT token to decode

        Returns:
            dict: Decoded payload

        Raises:
            JWTError: If token is invalid or expired
        """
        # Try current key first
        try:
            return jwt.decode(token, self.current_key, algorithms=[self.algorithm])
        except JWTError:
            pass  # Fall through to try old keys

        # Try old keys
        for old_key in self.old_keys:
            try:
                payload = jwt.decode(token, old_key, algorithms=[self.algorithm])
                # Token was signed with old key — still valid but should be rotated
                return payload
            except JWTError:
                continue

        # No valid key found
        raise JWTError("Token signature verification failed with all keys")

    def add_old_key(self, key: str):
        """
        Add a key to the list of valid old keys.

        Args:
            key: Key to add
        """
        if key and key not in self.old_keys:
            self.old_keys.append(key)

    def remove_old_key(self, key: str):
        """
        Remove a key from old keys list.

        Args:
            key: Key to remove
        """
        if key in self.old_keys:
            self.old_keys.remove(key)

    def rotate_key(self, new_key: str):
        """
        Rotate to a new signing key.

        The current key becomes an old key (valid during transition).

        Args:
            new_key: New signing key
        """
        self.old_keys.append(self.current_key)
        self.current_key = new_key


# ── Key Rotation Strategy ─────────────────────────────────────────────────────

class KeyRotationSchedule:
    """
    Manages scheduled key rotation.

    Automatically rotates keys based on age.
    """

    def __init__(
        self,
        jwt_manager: MultiKeyJWT,
        rotation_days: int = 90,
        transition_days: int = 7,
    ):
        """
        Initialize rotation schedule.

        Args:
            jwt_manager: JWT manager to rotate
            rotation_days: Days before rotating key
            transition_days: Days to keep old keys valid
        """
        self.jwt_manager = jwt_manager
        self.rotation_days = rotation_days
        self.transition_days = transition_days
        self.last_rotation = datetime.now(timezone.utc)
        self.old_key_expiry = {}  # key -> expiry datetime

    def should_rotate(self) -> bool:
        """Check if key should be rotated."""
        age = datetime.now(timezone.utc) - self.last_rotation
        return age.days >= self.rotation_days

    def rotate_key(self, new_key: str):
        """
        Rotate to new key and schedule old key expiry.

        Args:
            new_key: New signing key
        """
        old_key = self.jwt_manager.current_key
        expiry = datetime.now(timezone.utc) + timedelta(days=self.transition_days)

        self.jwt_manager.rotate_key(new_key)
        self.old_key_expiry[old_key] = expiry
        self.last_rotation = datetime.now(timezone.utc)

        print(f"[auth] Key rotated — old key valid until {expiry.isoformat()}")

    def cleanup_expired_keys(self):
        """Remove expired old keys."""
        now = datetime.now(timezone.utc)
        expired = [
            key for key, expiry in self.old_key_expiry.items()
            if now >= expiry
        ]

        for key in expired:
            self.jwt_manager.remove_old_key(key)
            del self.old_key_expiry[key]
            print(f"[auth] Expired key removed from valid list")

        return len(expired)


# ── Integration Example ───────────────────────────────────────────────────────

def setup_jwt_rotation(settings):
    """
    Setup JWT rotation for production use.

    Args:
        settings: App settings

    Returns:
        MultiKeyJWT: Configured JWT manager
    """
    # In production, load old keys from secure storage
    current_key = settings.jwt_secret
    old_keys = getattr(settings, "jwt_old_keys", [])

    jwt_manager = MultiKeyJWT(
        current_key=current_key,
        old_keys=old_keys,
        algorithm=settings.jwt_algorithm,
    )

    return jwt_manager
