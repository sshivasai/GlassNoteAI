"""
llm/streamer.py

Changes in this revision
------------------------
- cancel(): logs a warning if the worker does not stop within 300 ms
  instead of silently discarding it.
- solve(): stores cancel_event on self for optional external cancellation.
- is_running(): RuntimeError guard tightened — C++ object deletion race
  on rapid session restart.
"""

import sys
import os
import threading
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.client import client as llm_client


class StreamWorker(QThread):
    token_received = pyqtSignal(str)
    stream_done    = pyqtSignal(str)
    stream_error   = pyqtSignal(str)

    def __init__(
        self,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]] = None,
        use_cache:     bool = True,
        mode:          str  = "solve",
        parent         = None,
    ):
        super().__init__(parent)
        self._system_prompt = system_prompt
        self._messages      = messages
        self._images        = images or []
        self._use_cache     = use_cache
        self._mode          = mode
        self._cancel_event  = threading.Event()

    def request_cancel(self):
        self._cancel_event.set()

    def run(self):
        llm_client.stream(
            system_prompt = self._system_prompt,
            messages      = self._messages,
            images        = self._images,
            on_token      = self.token_received.emit,
            on_done       = self.stream_done.emit,
            on_error      = self.stream_error.emit,
            use_cache     = self._use_cache,
            mode          = self._mode,
            cancel_event  = self._cancel_event,
        )


class LLMStreamer:
    def __init__(self):
        self._worker:        Optional[StreamWorker] = None
        self._worker_ref:    Optional[StreamWorker] = None
        self._cancel_event:  Optional[threading.Event] = None  # ← NEW

    def solve(
        self,
        system_prompt: str,
        messages:      List[dict],
        images:        Optional[List[str]],
        on_token:      callable,
        on_done:       callable,
        on_error:      callable,
        use_cache:     bool = True,
        mode:          str  = "solve",
    ):
        self.cancel()

        worker = StreamWorker(
            system_prompt = system_prompt,
            messages      = messages,
            images        = images,
            use_cache     = use_cache,
            mode          = mode,
        )
        worker.token_received.connect(on_token)
        worker.stream_done.connect(on_done)
        worker.stream_error.connect(on_error)
        worker.finished.connect(self._on_worker_finished)

        self._worker       = worker
        self._worker_ref   = worker
        self._cancel_event = worker._cancel_event   # ← NEW (expose for callers)
        worker.start()

    def _on_worker_finished(self):
        self._worker     = None
        self._worker_ref = None

    def cancel(self):
        worker = self._worker
        if worker is None:
            return
        try:
            if worker.isRunning():
                worker.request_cancel()
                stopped = worker.wait(300)
                if not stopped:                              # ← NEW (log warning)
                    print(
                        "[llm] StreamWorker did not stop within 300 ms "
                        "— detaching (it will finish in background)"
                    )
        except RuntimeError:
            # Qt C++ object already deleted — safe to ignore
            pass
        self._worker     = None
        self._worker_ref = None

    def is_running(self) -> bool:
        if self._worker is None:
            return False
        try:
            return self._worker.isRunning()
        except RuntimeError:
            self._worker = None          # ← NEW: clean up stale ref
            return False


streamer = LLMStreamer()