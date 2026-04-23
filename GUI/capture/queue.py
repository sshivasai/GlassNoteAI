"""
Screenshot queue manager.

Holds captured screenshots (base64 strings) until user triggers SOLVE.
Thread-safe. Emits count updates.
"""

import threading
from typing import List, Callable, Optional
from dataclasses import dataclass, field
import time


@dataclass
class QueuedShot:
    b64_image: str
    timestamp: float = field(default_factory=time.time)
    label: str = ""      # e.g. "Screenshot 1"


class ScreenshotQueue:
    def __init__(self, on_count_change: Optional[Callable[[int], None]] = None):
        self._queue: List[QueuedShot] = []
        self._lock = threading.Lock()
        self._on_count_change = on_count_change

    def add(self, b64_image: str) -> int:
        """Add a screenshot. Returns new count."""
        with self._lock:
            label = f"Screenshot {len(self._queue) + 1}"
            self._queue.append(QueuedShot(b64_image=b64_image, label=label))
            count = len(self._queue)

        if self._on_count_change:
            self._on_count_change(count)
        return count

    def pop_all(self) -> List[QueuedShot]:
        """Return and clear all queued screenshots."""
        with self._lock:
            items = self._queue.copy()
            self._queue.clear()

        if self._on_count_change:
            self._on_count_change(0)
        return items

    def clear(self):
        """Clear queue without returning items."""
        with self._lock:
            self._queue.clear()
        if self._on_count_change:
            self._on_count_change(0)

    def count(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        return self.count() == 0

    def set_count_callback(self, cb: Callable[[int], None]):
        self._on_count_change = cb