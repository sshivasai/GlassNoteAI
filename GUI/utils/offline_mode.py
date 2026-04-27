"""
utils/offline_mode.py — Offline mode detection and graceful degradation.

Monitors network connectivity and queues requests when offline.

Usage:
    from utils.offline_mode import connectivity_monitor

    if connectivity_monitor.is_online():
        make_api_call()
    else:
        show_offline_message()
"""

import socket
import threading
import time
from typing import Callable, Optional, List
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QueuedRequest:
    """Queued request for retry when online."""
    func: Callable
    args: tuple
    kwargs: dict
    retry_count: int = 0
    max_retries: int = 3


class ConnectivityMonitor:
    """
    Monitor network connectivity.

    Features:
      - Periodic connectivity checks
      - State change notifications
      - Request queuing for offline mode
      - Automatic retry when online
    """

    def __init__(self):
        self._online = True
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state_change_callbacks: List[Callable[[bool], None]] = []
        self._queued_requests: List[QueuedRequest] = []

    def start_monitoring(self, interval: float = 10.0):
        """
        Start connectivity monitoring.

        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            return

        self._monitoring = True

        def _monitor():
            while self._monitoring:
                was_online = self._online
                self._online = self._check_connectivity()

                # State changed?
                if was_online != self._online:
                    logger.info(f"Connectivity changed: {'online' if self._online else 'offline'}")
                    self._notify_state_change(self._online)

                    # Process queued requests if we just came online
                    if self._online and not was_online:
                        self._process_queued_requests()

                # Sleep in small chunks
                for _ in range(int(interval * 2)):
                    if not self._monitoring:
                        break
                    time.sleep(0.5)

        self._monitor_thread = threading.Thread(
            target=_monitor,
            daemon=True,
            name="connectivity-monitor"
        )
        self._monitor_thread.start()
        logger.info("Connectivity monitoring started")

    def stop_monitoring(self):
        """Stop connectivity monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Connectivity monitoring stopped")

    def _check_connectivity(self) -> bool:
        """
        Check if we have internet connectivity.

        Returns:
            bool: True if online
        """
        # Try to resolve a known hostname
        hosts = [
            ("api.anthropic.com", 443),
            ("api.openai.com", 443),
            ("1.1.1.1", 53),  # Cloudflare DNS
            ("8.8.8.8", 53),  # Google DNS
        ]

        for host, port in hosts:
            try:
                socket.create_connection((host, port), timeout=3)
                return True
            except (socket.timeout, socket.error):
                continue

        return False

    def is_online(self) -> bool:
        """
        Check if currently online.

        Returns:
            bool: True if online
        """
        return self._online

    def force_check(self) -> bool:
        """
        Force an immediate connectivity check.

        Returns:
            bool: True if online
        """
        self._online = self._check_connectivity()
        return self._online

    def on_state_change(self, callback: Callable[[bool], None]):
        """
        Register callback for connectivity state changes.

        Args:
            callback: Function to call with new online status
        """
        with self._lock:
            if callback not in self._state_change_callbacks:
                self._state_change_callbacks.append(callback)

    def _notify_state_change(self, online: bool):
        """Notify all callbacks of state change."""
        with self._lock:
            callbacks = list(self._state_change_callbacks)

        for callback in callbacks:
            try:
                callback(online)
            except Exception as e:
                logger.error(f"State change callback error: {e}", exc_info=True)

    # ── Request Queuing ────────────────────────────────────────────────────────

    def queue_request(self, func: Callable, *args, **kwargs):
        """
        Queue a request for retry when online.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        request = QueuedRequest(
            func=func,
            args=args,
            kwargs=kwargs,
        )

        with self._lock:
            self._queued_requests.append(request)

        logger.info(f"Queued request: {func.__name__}")

    def _process_queued_requests(self):
        """Process all queued requests now that we're online."""
        with self._lock:
            requests = list(self._queued_requests)
            self._queued_requests.clear()

        if not requests:
            return

        logger.info(f"Processing {len(requests)} queued requests...")

        for request in requests:
            try:
                request.func(*request.args, **request.kwargs)
                logger.info(f"Successfully processed queued request: {request.func.__name__}")
            except Exception as e:
                logger.error(f"Failed to process queued request: {e}", exc_info=True)

                # Re-queue if we have retries left
                if request.retry_count < request.max_retries:
                    request.retry_count += 1
                    with self._lock:
                        self._queued_requests.append(request)
                    logger.info(f"Re-queued request (retry {request.retry_count}/{request.max_retries})")

    def get_queue_size(self) -> int:
        """Get number of queued requests."""
        with self._lock:
            return len(self._queued_requests)

    def clear_queue(self):
        """Clear all queued requests."""
        with self._lock:
            count = len(self._queued_requests)
            self._queued_requests.clear()

        logger.info(f"Cleared {count} queued requests")


# Singleton instance
connectivity_monitor = ConnectivityMonitor()


# ── Helper Functions ───────────────────────────────────────────────────────────

def with_connectivity_check(func: Callable):
    """
    Decorator to check connectivity before executing.

    If offline, queues the request for later retry.

    Usage:
        @with_connectivity_check
        def api_call():
            # This only runs when online
            pass
    """
    def wrapper(*args, **kwargs):
        if connectivity_monitor.is_online():
            return func(*args, **kwargs)
        else:
            logger.warning(f"Offline: queuing {func.__name__} for later")
            connectivity_monitor.queue_request(func, *args, **kwargs)
            return None

    return wrapper


def get_offline_message() -> str:
    """
    Get user-friendly offline message.

    Returns:
        str: Formatted offline message
    """
    queued = connectivity_monitor.get_queue_size()

    message = (
        "**No Internet Connection**\n\n"
        "GlassNote requires an internet connection to function.\n\n"
        "Please check:\n"
        "• Wi-Fi or Ethernet connection\n"
        "• Firewall settings\n"
        "• VPN configuration"
    )

    if queued > 0:
        message += f"\n\n{queued} request(s) queued for retry when online."

    return message
