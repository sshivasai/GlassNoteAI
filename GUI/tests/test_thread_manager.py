"""
Tests for thread manager.
"""

import pytest
import threading
import time
from utils.thread_manager import thread_manager, managed_thread


def test_register_thread():
    """Test thread registration."""
    def worker():
        time.sleep(0.1)

    thread = threading.Thread(target=worker, daemon=True)
    stop_event = thread_manager.register(thread, name="test-worker")

    assert isinstance(stop_event, threading.Event)

    thread.start()
    thread.join(timeout=1.0)

    assert not thread.is_alive()


def test_stop_thread():
    """Test thread stopping."""
    stop_event = threading.Event()

    def worker():
        while not stop_event.is_set():
            time.sleep(0.01)

    thread = threading.Thread(target=worker, daemon=True)
    thread_manager.register(thread, name="test-stop", stop_event=stop_event)

    thread.start()
    time.sleep(0.05)  # Let it run briefly

    success = thread_manager.stop_thread(thread, timeout=1.0)

    assert success
    assert not thread.is_alive()


def test_managed_thread_decorator():
    """Test managed thread decorator."""
    executed = threading.Event()

    @managed_thread(name="test-decorated")
    def background_task():
        executed.set()

    thread = background_task()

    executed.wait(timeout=1.0)
    assert executed.is_set()


def test_shutdown_all():
    """Test shutdown all threads."""
    events = []

    for i in range(3):
        stop_event = threading.Event()
        events.append(stop_event)

        def worker(e=stop_event):
            while not e.is_set():
                time.sleep(0.01)

        thread = threading.Thread(target=worker, daemon=True)
        thread_manager.register(thread, name=f"test-{i}", stop_event=stop_event)
        thread.start()

    time.sleep(0.05)

    # Shutdown all
    thread_manager.shutdown_all(timeout=2.0)

    # All should be stopped
    active = thread_manager.get_active_threads()
    assert len(active) == 0
