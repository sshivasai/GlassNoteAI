"""
Auto screenshot watcher.

Runs in a background thread. Every N seconds:
1. Captures a screenshot
2. Compares with last captured hash
3. If meaningful change → adds to queue automatically

OFF by default. User enables in settings.
"""

import threading
import time
from typing import Callable, Optional

from capture import screenshot as screencap
from capture.diff import compute_hash, has_changed


class AutoWatcher:
    def __init__(
        self,
        on_capture: Callable[[str], None],   # called with b64 image
        interval_seconds: int = 5,
        diff_threshold: float = 0.10,
    ):
        self._on_capture = on_capture
        self._interval = interval_seconds
        self._threshold = diff_threshold
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_hash: Optional[str] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[auto_watcher] Started — interval={self._interval}s threshold={self._threshold}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._last_hash = None
        print("[auto_watcher] Stopped")

    def set_interval(self, seconds: int):
        self._interval = max(2, seconds)

    def set_threshold(self, threshold: float):
        self._threshold = max(0.01, min(0.99, threshold))

    def _loop(self):
        while self._running:
            try:
                b64 = screencap.capture_fullscreen()
                new_hash = compute_hash(b64)

                if has_changed(self._last_hash, new_hash, self._threshold):
                    self._last_hash = new_hash
                    self._on_capture(b64)
                    print("[auto_watcher] Change detected — screenshot queued")

            except Exception as e:
                print(f"[auto_watcher] Error: {e}")

            time.sleep(self._interval)