"""
utils/resource_monitor.py — Memory and resource usage monitoring.

Tracks memory usage, queue sizes, and warns when approaching limits.

Usage:
    from utils.resource_monitor import resource_monitor

    resource_monitor.track_queue_size(queue_name, size)
    resource_monitor.check_limits()  # Returns warnings if over limits
"""

import psutil
import os
import threading
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceLimits:
    """Resource usage limits."""
    max_memory_mb: int = 1024  # 1 GB
    max_queue_size: int = 50
    max_history_items: int = 100
    max_cache_size: int = 50
    warning_threshold: float = 0.8  # Warn at 80% of limit


@dataclass
class ResourceUsage:
    """Current resource usage."""
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    queue_sizes: Dict[str, int] = None
    history_count: int = 0
    cache_size: int = 0

    def __post_init__(self):
        if self.queue_sizes is None:
            self.queue_sizes = {}


class ResourceMonitor:
    """
    Monitor and enforce resource limits.

    Tracks:
      - Memory usage
      - Queue sizes
      - Cache sizes
      - History length
    """

    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._usage = ResourceUsage()
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self, interval: float = 30.0):
        """
        Start background monitoring.

        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            return

        self._monitoring = True

        def _monitor():
            while self._monitoring:
                self.update_memory_usage()
                warnings = self.check_limits()

                if warnings:
                    for warning in warnings:
                        logger.warning(f"Resource limit warning: {warning}")

                # Sleep in small chunks so we can stop quickly
                for _ in range(int(interval * 2)):
                    if not self._monitoring:
                        break
                    time.sleep(0.5)

        self._monitor_thread = threading.Thread(
            target=_monitor,
            daemon=True,
            name="resource-monitor"
        )
        self._monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Resource monitoring stopped")

    def update_memory_usage(self):
        """Update current memory usage."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            with self._lock:
                self._usage.memory_mb = memory_info.rss / (1024 * 1024)
                self._usage.memory_percent = process.memory_percent()

        except Exception as e:
            logger.debug(f"Failed to update memory usage: {e}")

    def track_queue_size(self, queue_name: str, size: int):
        """
        Track size of a queue.

        Args:
            queue_name: Name of the queue
            size: Current size
        """
        with self._lock:
            self._usage.queue_sizes[queue_name] = size

    def track_history_count(self, count: int):
        """Track session history count."""
        with self._lock:
            self._usage.history_count = count

    def track_cache_size(self, size: int):
        """Track cache size."""
        with self._lock:
            self._usage.cache_size = size

    def check_limits(self) -> List[str]:
        """
        Check if any resources are approaching limits.

        Returns:
            List[str]: Warning messages
        """
        warnings = []

        with self._lock:
            usage = self._usage

            # Memory
            if usage.memory_mb > self.limits.max_memory_mb * self.limits.warning_threshold:
                warnings.append(
                    f"Memory usage high: {usage.memory_mb:.0f} MB / "
                    f"{self.limits.max_memory_mb} MB "
                    f"({usage.memory_percent:.1f}%)"
                )

            # Queues
            for queue_name, size in usage.queue_sizes.items():
                if size > self.limits.max_queue_size * self.limits.warning_threshold:
                    warnings.append(
                        f"Queue '{queue_name}' size high: {size} / "
                        f"{self.limits.max_queue_size}"
                    )

            # History
            if usage.history_count > self.limits.max_history_items * self.limits.warning_threshold:
                warnings.append(
                    f"History count high: {usage.history_count} / "
                    f"{self.limits.max_history_items}"
                )

            # Cache
            if usage.cache_size > self.limits.max_cache_size * self.limits.warning_threshold:
                warnings.append(
                    f"Cache size high: {usage.cache_size} / "
                    f"{self.limits.max_cache_size}"
                )

        return warnings

    def should_trim_history(self) -> bool:
        """Check if history should be trimmed."""
        with self._lock:
            return self._usage.history_count >= self.limits.max_history_items

    def should_clear_queue(self, queue_name: str) -> bool:
        """Check if a queue should be cleared."""
        with self._lock:
            size = self._usage.queue_sizes.get(queue_name, 0)
            return size >= self.limits.max_queue_size

    def should_evict_cache(self) -> bool:
        """Check if cache should be evicted."""
        with self._lock:
            return self._usage.cache_size >= self.limits.max_cache_size

    def get_usage_stats(self) -> dict:
        """
        Get current usage statistics.

        Returns:
            dict: Usage stats
        """
        with self._lock:
            return {
                "memory_mb": round(self._usage.memory_mb, 1),
                "memory_percent": round(self._usage.memory_percent, 1),
                "queue_sizes": dict(self._usage.queue_sizes),
                "history_count": self._usage.history_count,
                "cache_size": self._usage.cache_size,
                "limits": {
                    "max_memory_mb": self.limits.max_memory_mb,
                    "max_queue_size": self.limits.max_queue_size,
                    "max_history_items": self.limits.max_history_items,
                    "max_cache_size": self.limits.max_cache_size,
                },
            }

    def print_status(self):
        """Print current resource usage."""
        stats = self.get_usage_stats()

        logger.info("=== Resource Usage ===")
        logger.info(f"Memory: {stats['memory_mb']} MB ({stats['memory_percent']}%)")

        if stats['queue_sizes']:
            logger.info("Queues:")
            for name, size in stats['queue_sizes'].items():
                logger.info(f"  {name}: {size}")

        logger.info(f"History: {stats['history_count']}")
        logger.info(f"Cache: {stats['cache_size']}")


# Singleton instance
resource_monitor = ResourceMonitor()


# ── Automatic Cleanup Helpers ──────────────────────────────────────────────────

def auto_trim_history(session):
    """
    Automatically trim session history if it exceeds limits.

    Args:
        session: SessionContext object
    """
    if resource_monitor.should_trim_history():
        keep_count = resource_monitor.limits.max_history_items // 2
        if len(session.history) > keep_count:
            removed = len(session.history) - keep_count
            session.history = session.history[-keep_count:]
            logger.info(f"Auto-trimmed history: removed {removed} old items")


def auto_clear_queue(queue, queue_name: str = "screenshots"):
    """
    Automatically clear queue if it exceeds limits.

    Args:
        queue: ScreenshotQueue object
        queue_name: Name for logging
    """
    if resource_monitor.should_clear_queue(queue_name):
        count = queue.count()
        queue.clear()
        logger.warning(f"Auto-cleared '{queue_name}' queue: removed {count} items")
