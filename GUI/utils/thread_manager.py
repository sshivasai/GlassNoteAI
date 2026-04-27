"""
utils/thread_manager.py — Thread lifecycle management and graceful shutdown.

Tracks all background threads and ensures clean shutdown.

Usage:
    from utils.thread_manager import thread_manager, managed_thread

    # Register a thread
    thread = threading.Thread(target=worker, daemon=True)
    thread_manager.register(thread, name="worker-1")
    thread.start()

    # Or use decorator
    @managed_thread(name="background-worker")
    def background_task():
        while not thread_manager.should_stop():
            do_work()

    # Shutdown all threads
    thread_manager.shutdown_all(timeout=5.0)
"""

import threading
import time
import atexit
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ThreadInfo:
    """Information about a managed thread."""
    thread: threading.Thread
    name: str
    started_at: float
    stop_event: threading.Event


class ThreadManager:
    """
    Manages background thread lifecycle.

    Provides:
      - Thread registration and tracking
      - Graceful shutdown with timeout
      - Stop signals for cooperative threads
      - Automatic cleanup on program exit
    """

    def __init__(self):
        self._threads: Dict[int, ThreadInfo] = {}
        self._lock = threading.Lock()
        self._global_stop = threading.Event()
        self._shutdown_in_progress = False

        # Register cleanup on exit
        atexit.register(self._atexit_cleanup)

    def register(
        self,
        thread: threading.Thread,
        name: Optional[str] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> threading.Event:
        """
        Register a thread for managed shutdown.

        Args:
            thread: The thread to register
            name: Optional name for logging
            stop_event: Optional stop event for this thread

        Returns:
            threading.Event: Stop event for the thread
        """
        if stop_event is None:
            stop_event = threading.Event()

        thread_id = id(thread)
        thread_name = name or thread.name or f"thread-{thread_id}"

        with self._lock:
            self._threads[thread_id] = ThreadInfo(
                thread=thread,
                name=thread_name,
                started_at=time.time(),
                stop_event=stop_event,
            )

        logger.debug(f"Registered thread: {thread_name}")
        return stop_event

    def unregister(self, thread: threading.Thread) -> None:
        """
        Unregister a thread (call when thread completes).

        Args:
            thread: The thread to unregister
        """
        thread_id = id(thread)
        with self._lock:
            if thread_id in self._threads:
                info = self._threads.pop(thread_id)
                logger.debug(f"Unregistered thread: {info.name}")

    def should_stop(self, thread: Optional[threading.Thread] = None) -> bool:
        """
        Check if a thread should stop.

        Args:
            thread: Optional thread to check. If None, checks global stop.

        Returns:
            bool: True if thread should stop
        """
        if self._global_stop.is_set():
            return True

        if thread:
            thread_id = id(thread)
            with self._lock:
                if thread_id in self._threads:
                    return self._threads[thread_id].stop_event.is_set()

        return False

    def stop_thread(self, thread: threading.Thread, timeout: float = 5.0) -> bool:
        """
        Signal a specific thread to stop and wait for it.

        Args:
            thread: Thread to stop
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if thread stopped cleanly
        """
        thread_id = id(thread)

        with self._lock:
            if thread_id not in self._threads:
                return True  # Already stopped

            info = self._threads[thread_id]
            info.stop_event.set()

        logger.debug(f"Stopping thread: {info.name}")

        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.warning(f"Thread {info.name} did not stop within {timeout}s")
            return False

        self.unregister(thread)
        logger.debug(f"Thread stopped: {info.name}")
        return True

    def shutdown_all(self, timeout: float = 10.0) -> None:
        """
        Gracefully shutdown all managed threads.

        Args:
            timeout: Maximum time to wait for all threads in seconds
        """
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress")
            return

        self._shutdown_in_progress = True
        self._global_stop.set()

        with self._lock:
            thread_list = list(self._threads.values())

        if not thread_list:
            logger.info("No threads to shut down")
            return

        logger.info(f"Shutting down {len(thread_list)} threads...")

        # Signal all threads to stop
        for info in thread_list:
            info.stop_event.set()

        # Wait for all threads with timeout
        start_time = time.time()
        for info in thread_list:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                logger.warning(f"Timeout reached, {info.name} may still be running")
                continue

            info.thread.join(timeout=remaining)

            if info.thread.is_alive():
                logger.warning(f"Thread {info.name} did not stop within timeout")
            else:
                logger.debug(f"Thread {info.name} stopped cleanly")

        # Clear registry
        with self._lock:
            alive_count = sum(1 for info in self._threads.values() if info.thread.is_alive())
            self._threads.clear()

        if alive_count > 0:
            logger.warning(f"{alive_count} threads did not stop cleanly")
        else:
            logger.info("All threads stopped cleanly")

        self._shutdown_in_progress = False

    def get_active_threads(self) -> List[ThreadInfo]:
        """
        Get list of currently active threads.

        Returns:
            List[ThreadInfo]: Active thread information
        """
        with self._lock:
            return [info for info in self._threads.values() if info.thread.is_alive()]

    def print_status(self) -> None:
        """Print status of all managed threads."""
        active = self.get_active_threads()

        if not active:
            logger.info("No active managed threads")
            return

        logger.info(f"Active threads: {len(active)}")
        for info in active:
            runtime = time.time() - info.started_at
            logger.info(f"  - {info.name}: running for {runtime:.1f}s")

    def _atexit_cleanup(self) -> None:
        """Cleanup handler called on program exit."""
        if self._threads:
            logger.info("Program exit detected, cleaning up threads...")
            self.shutdown_all(timeout=3.0)


# Singleton instance
thread_manager = ThreadManager()


# ── Decorator for Managed Threads ──────────────────────────────────────────────

def managed_thread(name: Optional[str] = None, daemon: bool = True):
    """
    Decorator to create and register a managed thread.

    Usage:
        @managed_thread(name="worker", daemon=True)
        def background_task():
            while not thread_manager.should_stop():
                do_work()

        background_task()  # Starts thread automatically
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            stop_event = threading.Event()

            def target():
                try:
                    # Pass stop_event as kwarg if function accepts it
                    import inspect
                    sig = inspect.signature(func)
                    if 'stop_event' in sig.parameters:
                        func(*args, stop_event=stop_event, **kwargs)
                    else:
                        func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Managed thread {name or func.__name__} error: {e}", exc_info=True)
                finally:
                    # Auto-unregister on completion
                    thread_manager.unregister(threading.current_thread())

            thread = threading.Thread(
                target=target,
                daemon=daemon,
                name=name or func.__name__
            )

            thread_manager.register(thread, name=name or func.__name__, stop_event=stop_event)
            thread.start()

            return thread

        return wrapper
    return decorator


# ── Cooperative Thread Base Class ──────────────────────────────────────────────

class ManagedThread(threading.Thread):
    """
    Base class for cooperative threads.

    Override run() and check self.should_stop() regularly.

    Example:
        class Worker(ManagedThread):
            def run(self):
                while not self.should_stop():
                    do_work()
                    time.sleep(1)

        worker = Worker(name="my-worker")
        worker.start()
        # Later...
        worker.stop(timeout=5.0)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        thread_manager.register(self, name=self.name, stop_event=self._stop_event)

    def should_stop(self) -> bool:
        """Check if thread should stop."""
        return self._stop_event.is_set() or thread_manager.should_stop()

    def stop(self, timeout: float = 5.0) -> bool:
        """
        Stop this thread gracefully.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if stopped cleanly
        """
        return thread_manager.stop_thread(self, timeout=timeout)

    def run(self):
        """
        Override this method in subclasses.

        Make sure to check self.should_stop() regularly.
        """
        raise NotImplementedError("Subclasses must implement run()")
