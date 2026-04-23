"""
api/notifications_client.py

Desktop-side notifications client for GlassNote Cloud.

Polls GET /api/notifications/active on startup and hourly.
Dismissed notification IDs are persisted to config so users are
never shown the same alert twice after closing it.

Design:
    - Polling runs in a daemon background thread.
    - New/unseen notifications are emitted via a Qt signal.
    - Thread-safe: QTimer.singleShot is used to cross into the Qt main thread.
"""

import threading
import time
from typing import Callable, List, Optional

import httpx


# Poll interval: check for new notifications every hour
_POLL_INTERVAL_SECONDS = 3600

# Key used to store dismissed notification IDs in the config dict
_DISMISSED_KEY = "dismissed_notification_ids"


class NotificationsClient:
    """
    Polls the GlassNote backend for active system notifications.

    Usage:
        client = NotificationsClient()
        client.configure(api_url, token, plan)
        client.set_callback(lambda notifications: ...)
        client.start()         # begins polling in background
        client.dismiss(nid)    # marks a notification as seen locally
    """

    def __init__(self):
        self._api_url:   str = ""
        self._token:     str = ""
        self._plan:      str = "free"
        self._callback:  Optional[Callable[[List[dict]], None]] = None
        self._thread:    Optional[threading.Thread] = None
        self._stop_evt:  threading.Event = threading.Event()
        self._dismissed: set = set()     # notification IDs already seen
        self._config_ref: Optional[dict] = None  # reference to live config dict

    # ── Configuration ──────────────────────────────────────────────────────────

    def configure(
        self,
        api_url: str,
        token:   str = "",
        plan:    str = "free",
    ) -> None:
        """Configure the polling client with the backend URL and user context."""
        self._api_url = api_url.rstrip("/")
        self._token   = token
        self._plan    = plan

    def load_dismissed(self, cfg: dict) -> None:
        """
        Load previously-dismissed notification IDs from the app config.

        Call this after configure() and before start(), passing the loaded
        config dict.
        """
        self._config_ref = cfg
        self._dismissed  = set(cfg.get(_DISMISSED_KEY, []))

    def set_callback(self, cb: Callable[[List[dict]], None]) -> None:
        """
        Register a callback to receive new notifications.

        The callback is called with a list of unseen notification dicts
        whenever new notifications are found. It is called in the polling
        thread — use QTimer.singleShot(0, ...) to cross into the Qt thread.
        """
        self._callback = cb

    # ── Polling lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background polling thread (daemon — dies with the app)."""
        if not self._api_url:
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="notifications-poll",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop gracefully."""
        self._stop_evt.set()

    # ── Dismiss ───────────────────────────────────────────────────────────────

    def dismiss(self, notification_id: str) -> None:
        """
        Mark a notification as dismissed locally.

        The ID is added to the dismissed set and persisted to the config
        so it is not shown again after a restart.
        """
        self._dismissed.add(notification_id)
        if self._config_ref is not None:
            self._config_ref[_DISMISSED_KEY] = list(self._dismissed)
            # Persist — caller is responsible for calling config.save_config(cfg)
            # This is done here to avoid a circular import on settings/config.
            try:
                from settings import config as cfg_module
                cfg_module.save_config(self._config_ref)
            except Exception:
                pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Background polling loop: poll immediately, then once per hour."""
        # First poll immediately on startup
        self._fetch_and_notify()

        while not self._stop_evt.wait(timeout=_POLL_INTERVAL_SECONDS):
            self._fetch_and_notify()

    def _fetch_and_notify(self) -> None:
        """Fetch notifications from the backend and invoke the callback for new ones."""
        if not self._api_url:
            return

        try:
            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            with httpx.Client(
                timeout=httpx.Timeout(10.0, connect=5.0),
                http2=True,
            ) as client:
                r = client.get(
                    f"{self._api_url}/api/notifications/active",
                    params={"plan": self._plan} if self._plan else {},
                    headers=headers,
                )

            if r.status_code != 200:
                return

            all_notifications = r.json()  # list of NotificationOut dicts

            # Filter to only NEW (not yet dismissed) notifications
            new_notifications = [
                n for n in all_notifications
                if n.get("id") not in self._dismissed
            ]

            if new_notifications and self._callback:
                self._callback(new_notifications)

        except Exception as exc:
            # Non-fatal: network issues should never crash the GUI
            print(f"[notifications] Poll failed (non-fatal): {exc}")


# Module-level singleton
notifications_client = NotificationsClient()
