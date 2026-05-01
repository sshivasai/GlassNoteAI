"""
Audio Pipeline — DUAL STREAM VERSION.

Architecture
------------
Stream A (interview audio)
  system source  → WASAPI loopback → interviewer voice ONLY
  mic source     → microphone      → both voices (fallback)

Stream B (user voice gate)
  ALWAYS microphone, energy-based VAD only — no STT
  Sets gate: is user currently speaking?

Dispatch logic
--------------
  Smart Answering ON  (smart_answering=True in settings):
    STT end-of-turn signal  → _on_smart_dispatch() → immediate dispatch
    OR silence >= threshold → check_silence_and_dispatch() → fallback dispatch
    (whichever fires first — deduplication prevents double dispatch)

  Smart Answering OFF (legacy):
    silence >= threshold only → check_silence_and_dispatch()

STT providers
-------------
  "deepgram"        → DeepgramStreamingSTT  (V1 nova / V2 flux)
                      Smart signal: on_segment_ready
                                    (EndOfTurn / speech_final)
  "openai_realtime" → OpenAIRealtimeSTT     (gpt-4o-transcribe family)
                      Smart signal: on_smart_dispatch
                                    (transcription.completed)
                      Extra:        on_speech_stopped
                                    → locks silence clock

  "whisper" REMOVED — replaced by "openai_realtime" which has
  server-side VAD, no hallucinations on silence, streaming partials.

Silence clock locking  (OpenAI Realtime only)
---------------------------------------------
  Problem: transcription.completed fires ~100 ms AFTER speech_stopped.
           If _on_partial were called from completed, _last_speech_time
           would reset to "now", adding a full silence_threshold delay
           on top of the server VAD wait.

  Fix: _speech_time_locked flag.
    speech_stopped fires → _on_stt_vad_stopped() → _speech_time_locked=True
    completed fires      → _on_partial NOT called from completed event
                        → _last_speech_time stays at last spoken-word time
    Silence timer:         measures correctly from last word ✓

  Deepgram is unaffected — _speech_time_locked stays False.

Optimisations
-------------
1. config.load_config() cached — not called every 100 ms poll.
   Call refresh_config() from settings UI on save.
2. _get_best_segment_text() uses accumulated text first (zero API call).
3. Polling at 100 ms — worst-case dispatch delay 99 ms.
"""

import sys
import os
import time
import numpy as np
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from audio.recorder   import AudioRecorder
from audio.voice_gate import VoiceActivityGate
from settings import config


RECOMMENDED_POLL_MS = 100


class AudioPipeline(QThread):
    recording_started     = pyqtSignal()
    recording_stopped     = pyqtSignal()
    partial_transcript    = pyqtSignal(str)
    transcript_ready      = pyqtSignal(str)
    transcribe_error      = pyqtSignal(str)
    level_update          = pyqtSignal(float)
    user_speaking_changed = pyqtSignal(bool)
    stereo_mix_warning    = pyqtSignal()  # FIX: Stereo Mix not enabled warning

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recorder:   Optional[AudioRecorder]     = None
        self._stt                                      = None
        self._voice_gate: Optional[VoiceActivityGate] = None
        self._language     = "en"
        self._stt_provider = "deepgram"
        self._audio_source = "system"

        # Interviewer silence detection
        self._last_speech_time      = 0.0
        self._has_meaningful_speech = False
        self._segment_start_time    = 0.0

        # Dispatch state
        self._processing_question  = False
        self._last_sent_transcript = ""
        self._last_dispatch_time   = 0.0

        # Continuous mode
        self._continuous_mode = False

        # User speaking state (from voice gate)
        self._user_was_speaking = False

        # ── Cached config values ───────────────────────────────────────────────
        # Loaded once at start_recording() and on refresh_config().
        # Eliminates config.load_config() disk reads on every 100 ms poll.
        self._silence_threshold: float = 0.8  # TTFT-OPT: reduced default from 1.5s
        self._smart_answering:   bool  = False
        # Issue 4a: auto_answer=False means no silence-timer dispatch at all.
        # The user must stop interview mode to trigger an LLM call.
        self._auto_answer:       bool  = True

        # ── Silence clock lock (OpenAI Realtime only) ──────────────────────────
        # Set True when server VAD fires speech_stopped.
        # Prevents transcription.completed from resetting _last_speech_time.
        self._speech_time_locked: bool = False

        # ── Dispatch gate ─────────────────────────────────────────────────
        # When False (default), audio chunks are captured and STT is
        # connected, but transcripts are NOT dispatched to the LLM.
        # Calling resume() opens the gate; pause() closes it.
        # This enables zero-latency interview mode toggle (no pipeline rebuild).
        self._gated: bool = True   # starts gated (paused)

        # ── Pending smart dispatch buffer (Fix 1A — race condition) ────────
        # If EndOfTurn fires while _gated=True (race: voice gate closed just
        # before dispatch ran), we buffer the text here and flush on resume().
        self._pending_smart_dispatch: str = ""

        # ── Pre-fetched config (BUG-9 / PERF-2 fix) ───────────────────────────
        # app_controller pre-fetches STT credentials from the backend BEFORE
        # starting the pipeline and injects them here via set_prefetched_config().
        # _create_stt() reads from this dict so it never blocks on HTTP.
        self._prefetched_cfg: Optional[dict] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_prefetched_config(self, cfg: dict) -> None:
        """
        Inject a pre-fetched config dict (with STT credentials already resolved)
        so _create_stt() never blocks on a synchronous HTTP call (BUG-9/PERF-2).

        Called by app_controller BEFORE start_recording() from a background thread.
        Thread-safe: dict assignment is atomic in CPython.
        """
        self._prefetched_cfg = cfg
        print("[pipeline] Pre-fetched config injected (STT credentials ready)")

    def start_recording_with_source(self) -> None:
        """
        Qt slot version of start_recording() using the stored audio source.
        Called via QMetaObject.invokeMethod from the STT pre-fetch thread
        so it executes on the main/pipeline thread (BUG-9/PERF-2).
        """
        cfg    = self._prefetched_cfg or config.load_config()
        source = cfg.get("audio_source", "system")
        self.start_recording(source=source)
        self.pause()  # gate closed — pipeline stays warm but idle
        print(f"[pipeline] Warm start complete — source={source}, gate=closed")

    def start_recording(self, source: str = "system"):
        if self._recorder and self._recorder.is_recording():
            print("[pipeline] Already recording")
            return

        cfg = config.load_config()
        self._stt_provider = cfg.get("stt_provider", "deepgram")
        self._language     = _lang_code(cfg.get("default_language", "English"))
        self._audio_source = source

        # Cache hot-path config values
        self._silence_threshold = float(cfg.get("silence_threshold", 0.8))
        self._smart_answering   = bool(cfg.get("smart_answering", True))    # TTFT-OPT: default True — use EndOfTurn signal, not silence timer
        self._auto_answer       = bool(cfg.get("auto_answer",      True))   # Issue 4a

        self._reset_all_state()
        self._continuous_mode = True

        # ── Start STT backend ──────────────────────────────────────────────────
        self._stt = self._create_stt(cfg)
        if self._stt is None:
            return

        # ── Start interview audio recorder ─────────────────────────────────────
        self._recorder = AudioRecorder(
            source   = source,
            on_level = lambda lvl: self.level_update.emit(lvl),
            on_chunk = self._on_audio_chunk,
            on_stereo_mix_warning = self._on_stereo_mix_warning,
        )

        # ── Start voice gate (ALWAYS on mic) ───────────────────────────────────
        # Bug C fix: hold_time reduced from 1.5 → 0.8 s.
        # 1.5 s was causing the gate to block dispatch for too long after the
        # user stopped speaking (logs showed "user speaking (1.3s ago) →
        # holding dispatch").  0.8 s is enough to avoid false-positive
        # dispatch while the user is still mid-sentence, while releasing
        # quickly enough that the silence timer can fire promptly.
        self._voice_gate = VoiceActivityGate(
            on_user_started = self._on_user_started_speaking,
            on_user_stopped = self._on_user_stopped_speaking,
            hold_time       = 0.8,
        )

        try:
            self._recorder.start()
            native_sr = self._recorder.get_native_sr()

            if hasattr(self._stt, "start"):
                self._stt.start(native_sr)

            gate_ok = self._voice_gate.start()
            if not gate_ok:
                print("[pipeline] Voice gate unavailable — "
                      "using silence-only detection")
                self._voice_gate = None

            self.recording_started.emit()
            print(
                f"[pipeline] Dual-stream recording started  "
                f"source={source}  "
                f"gate={'ON' if gate_ok else 'OFF'}  "
                f"stt={self._stt_provider}  "
                f"silence_threshold={self._silence_threshold}s  "
                f"smart_answering={self._smart_answering}"   # ← NEW
            )

        except Exception as e:
            self.transcribe_error.emit(str(e))
            self._cleanup()
            self._continuous_mode = False

    def stop_recording(self):
        if not self._continuous_mode:
            return
        self._continuous_mode = False
        self._gated = True

        # FIX (HIGH-4): Flush buffered smart dispatch before stopping
        # Prevents question loss when user toggles interview mode off
        # before the gate opens (e.g., user is still speaking when they click stop)
        if self._pending_smart_dispatch:
            pending = self._pending_smart_dispatch
            self._pending_smart_dispatch = ""
            print(f"[pipeline] ⚡ Flushing buffered smart dispatch on stop: '{pending[:50]}'")
            self._last_sent_transcript = pending
            self._processing_question  = True
            self.transcript_ready.emit(pending)

        self._cleanup()
        self.recording_stopped.emit()
        print("[pipeline] Recording stopped")

    def pause(self):
        """
        Gate the dispatch — stop forwarding audio to the LLM.

        The STT WebSocket and audio devices remain open and connected.
        Only the "interview listening" state is suppressed.
        Calling this multiple times is idempotent.
        """
        if self._gated:
            return
        self._gated = True
        self._reset_segment_state()
        self.partial_transcript.emit("")
        print("[pipeline] ⏸ Paused (gate closed — STT still connected)")

    def resume(self):
        """
        Open the gate — immediately begin forwarding audio to the LLM.

        Because the pipeline was already running (no cold start needed),
        this returns effectively instantly (~0 ms).
        """
        if not self._gated:
            return
        self._gated = False
        self._reset_segment_state()
        self._last_dispatch_time = time.time()
        # Flush any EndOfTurn that fired while gate was closed
        if self._pending_smart_dispatch:
            pending = self._pending_smart_dispatch
            self._pending_smart_dispatch = ""
            self._on_smart_dispatch(pending)
        print("[pipeline] ▶ Resumed (gate open — listening for questions)")

    def is_running(self) -> bool:
        """True if the pipeline is started (audio flowing, even if gated)."""
        return self._continuous_mode and bool(
            self._recorder and self._recorder.is_recording()
        )

    def stop_and_transcribe(self):
        """Legacy compat."""
        self.stop_recording()

    def refresh_config(self):
        """
        Call from the settings UI after the user saves new values.
        Re-reads all fields used in the hot poll path.
        """
        cfg = config.load_config()
        self._silence_threshold = float(cfg.get("silence_threshold", 0.8))
        self._smart_answering   = bool(cfg.get("smart_answering", True))    # TTFT-OPT: default True — use EndOfTurn signal, not silence timer
        self._auto_answer       = bool(cfg.get("auto_answer",      True))   # Issue 4a
        print(
            f"[pipeline] Config refreshed — "
            f"silence_threshold={self._silence_threshold}s  "
            f"smart_answering={self._smart_answering}  "
            f"auto_answer={self._auto_answer}"
        )

    def notify_llm_done(self):
        """
        Called when LLM finishes answering.
        Resets segment state so the next question can be detected.
        """
        self._processing_question  = False
        self._last_sent_transcript = ""
        self._last_dispatch_time   = time.time()
        self._reset_segment_state()

        if self._stt and hasattr(self._stt, "reset_segment"):
            self._stt.reset_segment()

        print("[pipeline] LLM done — segment reset, listening for next question")

    def check_silence_and_dispatch(self):
        """
        Call every RECOMMENDED_POLL_MS (100 ms) from a QTimer.

        Smart Answering ON:  this is a fallback — if STT's end-of-turn
                             signal already fired, _processing_question=True
                             and Guard 3 exits immediately (< 1 µs).

        Smart Answering OFF: this is the sole dispatch trigger.

        Decision tree — every guard must pass:
          1. Continuous mode active?
          2. Recorder running?
          3. LLM currently processing?       → skip
          4. User currently speaking?        → skip  (gate guard)
          5. Meaningful interviewer speech?
          6. Silence >= threshold?           (cached — no disk read)
          7. Segment >= 0.8 s?
          8. Text differs from last dispatch?
          → emit transcript_ready
        """
        if not self._continuous_mode:
            return
        if not self._recorder or not self._recorder.is_recording():
            return

        # Guard 0 — dispatch gate (interview mode toggle)
        if self._gated:
            return

        # TTFT-OPT: smart_answering bypasses silence timer
        # When smart_answering=True, _on_smart_dispatch() fires immediately on
        # STT EndOfTurn. The silence timer is redundant — skip it entirely to
        # avoid any additional latency on the hot path.
        if self._smart_answering:
            return

        # Guard 0b — auto_answer disabled: silence timer never dispatches.
        # The user must stop interview mode to get an answer (dispatch-on-stop
        # in app_controller._stop_continuous_recording handles that case).
        if not self._auto_answer:
            return

        # Guard 3
        if self._processing_question:
            return

        # Guard 4
        if self._voice_gate and self._voice_gate.is_user_speaking():
            if int(time.time()) % 5 == 0:
                age = self._voice_gate.get_user_speech_age()
                print(f"[pipeline] Gate: user speaking "
                      f"({age:.1f}s ago) → holding dispatch")
            return

        # Guard 5
        if not self._has_meaningful_speech:
            return

        # Guard 6 — cached, no disk read
        silence = self._get_silence_age()
        if silence < self._silence_threshold:
            return

        # Guard 7
        segment_dur = (
            time.time() - self._segment_start_time
            if self._segment_start_time > 0 else 0.0
        )
        if segment_dur < 0.8:  # TTFT-OPT: reduced from 1.5s
            return

        # Guard 8
        text = self._get_best_segment_text()
        if not text.strip():
            return
        if text == self._last_sent_transcript:
            return

        # All guards passed → dispatch
        print(
            f"[pipeline] ✓ Silence dispatch  "
            f"silence={silence:.1f}s  segment={segment_dur:.1f}s  "
            f"→ '{text[:60]}'"
        )
        self._last_sent_transcript = text
        self._processing_question  = True
        self.transcript_ready.emit(text.strip())

    # ── Smart dispatch (STT end-of-turn signal) ────────────────────────────────

    def _on_smart_dispatch(self, text: str):          # ← NEW METHOD
        """
        Called directly by the STT backend when it detects end-of-turn:
          • Deepgram flux    → EndOfTurn event
          • Deepgram nova    → speech_final=True
          • OpenAI Realtime  → transcription.completed

        Bypasses the silence timer — dispatches immediately.
        The silence timer still runs as a fallback (Guard 3 will exit
        early because _processing_question=True after this fires).

        Guards (lighter than silence path — STT signal is already reliable):
          0. Dispatch gate open (interview mode active)
          0b. Smart answering enabled (Bug B fix)
          1. Continuous mode active
          2. Not already processing
          3. Minimum 2 words (filters noise / single-word STT artifacts)
          4. Not a duplicate of last dispatch

        FIX (HIGH-4): Pending smart dispatch is now flushed on stop_recording()
        to prevent question loss when user toggles interview mode off before
        the gate opens.
        """
        # Bug B fix: guard against firing when gate is closed (pipeline paused)
        # or when smart_answering is disabled — in that case the silence timer
        # is the sole dispatch trigger and this callback must be a no-op.
        #
        # IMPORTANT: When auto_answer=False, ignore the gate — smart dispatch
        # should fire immediately regardless of user speech (manual mode).
        # Gate only matters when auto_answer=True (auto-resume on user stop).
        if not self._smart_answering:
            return
        if self._gated and self._auto_answer:
            # Buffer for dispatch when gate opens (race condition fix)
            # Only applies in auto_answer mode
            self._pending_smart_dispatch = text.strip()
            print(f"[pipeline] ⚠️ Smart dispatch buffered (gate closed): '{text[:50]}'")
            return
        if not self._continuous_mode:
            return
        if self._processing_question:
            return

        text = text.strip()
        if not text:
            return
        if len(text.split()) < 2:
            return
        if text == self._last_sent_transcript:
            return

        print(
            f"[pipeline] ⚡ Smart dispatch  "
            f"STT end-of-turn → '{text[:60]}'"
        )

        self._last_sent_transcript = text
        self._processing_question  = True
        self.transcript_ready.emit(text)

    def _on_stt_vad_stopped(self):                    # ← NEW METHOD
        """
        Called when the OpenAI Realtime server VAD fires speech_stopped.

        Locks _last_speech_time so subsequent _on_partial calls
        (triggered by the transcription.completed event ~100 ms later)
        do NOT reset the silence clock.

        Without this lock the timeline would be:
          last word T=4.0 → speech_stopped T=4.6 → completed T=4.7
          → _on_partial resets clock to T=4.7
          → silence timer waits ANOTHER 1.5 s → dispatches at T=6.2
          → total silence from last word = 2.2 s  (700 ms too long)

        With this lock:
          last word T=4.0 → clock stays at T=4.0
          → silence timer dispatches at T=5.5  (exactly 1.5 s) ✓
        """
        self._speech_time_locked = True
        # Safety: ensure _last_speech_time is set even if no deltas arrived
        # (very short utterance where completed fires before any partial)
        if self._last_speech_time == 0.0:
            self._last_speech_time = time.time()
        print("[pipeline] 🔒 Silence clock locked  (server VAD speech_stopped)")

    # ── Voice gate callbacks ───────────────────────────────────────────────────

    def _on_user_started_speaking(self):
        self._user_was_speaking = True
        print("[pipeline] 🎤 User started speaking — dispatch gated")
        self.user_speaking_changed.emit(True)

    def _on_user_stopped_speaking(self):
        self._user_was_speaking = False
        print("[pipeline] 🔇 User stopped speaking — gate releasing")
        self.user_speaking_changed.emit(False)

    # ── State queries ──────────────────────────────────────────────────────────

    def get_last_transcript_age(self) -> float:
        if self._last_speech_time == 0 or not self._has_meaningful_speech:
            return 0.0
        return time.time() - self._last_speech_time

    def get_accumulated_transcript(self) -> str:
        if self._stt and hasattr(self._stt, "get_segment_transcript"):
            return self._stt.get_segment_transcript()
        return ""

    def has_meaningful_speech(self) -> bool:
        return self._has_meaningful_speech

    def is_user_speaking(self) -> bool:
        if self._voice_gate:
            return self._voice_gate.is_user_speaking()
        return False

    def is_recording(self) -> bool:
        return self._recorder is not None and self._recorder.is_recording()

    def is_continuous(self) -> bool:
        return self._continuous_mode

    def is_processing(self) -> bool:
        return self._processing_question

    def get_duration(self) -> float:
        if self._recorder:
            return self._recorder.get_duration_seconds()
        return 0.0

    def cancel(self):
        self._continuous_mode = False
        self._cleanup()
        if self.isRunning():
            self.quit()
            self.wait(2_000)   # 2s timeout so app can always exit

    def run(self):
        return

    # ── Internal ───────────────────────────────────────────────────────────────

    def _cleanup(self):
        """
        Tear down all resources in dependency order:
          voice_gate → STT → recorder

        STT may hold an open WebSocket (Deepgram / OpenAI Realtime).
        We explicitly call close() if available before stop() to ensure
        the WS handshake teardown completes and no zombie threads linger.
        """
        for obj in (self._voice_gate, self._stt, self._recorder):
            if obj is None:
                continue
            try:
                # Close WebSocket / network resources first (STT backends)
                if hasattr(obj, "close"):
                    obj.close()
            except Exception as e:
                print(f"[pipeline] close() warning: {e}")
            try:
                obj.stop()
            except Exception as e:
                print(f"[pipeline] stop() warning: {e}")
        self._voice_gate = None
        self._stt        = None
        self._recorder   = None
        print("[pipeline] All resources released")

    def _on_audio_chunk(self, pcm_bytes: bytes, native_sr: int):
        """
        Receives raw int16 bytes at device native SR.
        Converts to ndarray and passes to STT — STT resamples internally.
        """
        if self._gated:
            return
        if self._stt is None:
            return
        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        self._stt.feed(pcm, native_sr)

    def _on_partial(self, text: str):
        """
        Called by STT on every partial/interim result.

        Updates:
          • _has_meaningful_speech flag (3+ words = real speech)
          • _last_speech_time  ← ONLY when silence clock is NOT locked
          • partial_transcript signal  → pill ticker

        The lock guard is the key change for OpenAI Realtime correctness:
        speech_stopped locks the clock; completed calls _on_partial but
        the clock is already locked so it is not reset.
        """
        word_count = len(text.strip().split())
        if word_count >= 3:
            was_silent = not self._has_meaningful_speech
            self._has_meaningful_speech = True

            # ← CHANGED: only update clock when not locked
            if not self._speech_time_locked:
                self._last_speech_time = time.time()

            if was_silent:
                self._segment_start_time = time.time()
                print(f"[pipeline] Interviewer speech started: '{text[:40]}'")

        self.partial_transcript.emit(text)

    def _on_stt_error(self, message: str):
        self.transcribe_error.emit(message)

    def _on_stereo_mix_warning(self):
        """Called when system audio capture fails because Stereo Mix is not enabled."""
        self.stereo_mix_warning.emit()

    def _get_silence_age(self) -> float:
        if self._last_speech_time == 0:
            return 0.0
        return time.time() - self._last_speech_time

    def _get_best_segment_text(self) -> str:
        """
        Returns best available transcript for current segment.

        Priority (fastest → most accurate):
          1. get_segment_transcript()      — accumulated partials, zero latency
          2. transcribe_current_segment()  — API call only if (1) empty

        Deepgram / OpenAI Realtime: both always return accumulated WS text.
        """
        if self._stt is None:
            return ""

        if hasattr(self._stt, "get_segment_transcript"):
            cached = self._stt.get_segment_transcript()
            if cached.strip():
                return cached

        if hasattr(self._stt, "transcribe_current_segment"):
            result = self._stt.transcribe_current_segment()
            if result:
                return result

        return ""

    def _reset_segment_state(self):
        self._last_speech_time      = 0.0
        self._has_meaningful_speech = False
        self._segment_start_time    = 0.0
        self._speech_time_locked    = False   # ← NEW: unlock for next segment

    def _reset_all_state(self):
        self._reset_segment_state()
        self._last_dispatch_time   = 0.0
        self._processing_question  = False
        self._last_sent_transcript = ""
        self._user_was_speaking    = False

    # ── STT factory ───────────────────────────────────────────────────────────

    def _create_stt(self, cfg: dict):
        """
        Instantiates the configured STT backend.

        Key resolution (in order):
          1. BYOK plan  → use locally configured API key (must be set in Settings)
          2. SaaS plan  → fetch key from backend /v1/proxy/stt-credentials
                          (held in memory only, never written to disk)
          3. No key     → emit error
        """
        provider = cfg.get("stt_provider", "deepgram")
        smart    = self._smart_answering

        # ── Resolve STT keys ───────────────────────────────────────────────────
        # BUG-9 / PERF-2 fix: use pre-fetched config if available.
        # app_controller._on_session_started() pre-fetches STT credentials from
        # the backend in a background thread and injects them via
        # set_prefetched_config() BEFORE calling start_recording().
        # This means we never block the pipeline thread on a synchronous HTTP call.
        effective_cfg = self._prefetched_cfg if self._prefetched_cfg is not None else cfg

        # Check if BYOK is enabled (account setting, not plan-based)
        byok_enabled = effective_cfg.get("glassnote_byok_enabled", False)

        deepgram_key = effective_cfg.get("deepgram_api_key", "").strip()
        openai_key   = effective_cfg.get("openai_api_key",   "").strip()

        if not byok_enabled and not deepgram_key and not openai_key:
            # Pre-fetch didn't run or failed — fall back to synchronous fetch
            # as a last resort (keeps backward compatibility).
            try:
                import httpx as _httpx
                from api.auth_client import _keyring_load
                token   = _keyring_load() or cfg.get("glassnote_api_token", "")
                api_url = cfg.get("glassnote_api_url", "http://localhost:8000").rstrip("/")
                r = _httpx.get(
                    f"{api_url}/v1/proxy/stt-credentials",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=8.0,
                )
                if r.status_code == 200:
                    data         = r.json()
                    deepgram_key = data.get("deepgram_key", "") or deepgram_key
                    openai_key   = data.get("openai_key",   "") or openai_key
                    print(f"[pipeline] STT keys fetched from backend (fallback, byok={byok_enabled})")
                else:
                    print(f"[pipeline] STT credentials fetch failed ({r.status_code}) — using local keys")
            except Exception as e:
                print(f"[pipeline] STT credentials fetch error: {e} — using local keys")
        else:
            if deepgram_key or openai_key:
                print(f"[pipeline] STT keys from pre-fetched config (byok={byok_enabled})")

        # ── Deepgram ───────────────────────────────────────────────────────────
        if provider == "deepgram":
            if not deepgram_key:
                self.transcribe_error.emit(
                    "No Deepgram API key available.\n"
                    "Contact support or add your own key in Settings → API Keys."
                )
                return None
            try:
                from audio.stt_deepgram import DeepgramStreamingSTT
                dg_model = cfg.get("deepgram_model", "nova-3")
                return DeepgramStreamingSTT(
                    api_key          = deepgram_key,
                    on_partial       = self._on_partial,
                    on_error         = self._on_stt_error,
                    on_segment_ready = (self._on_smart_dispatch if smart else None),
                    language         = self._language,
                    model            = dg_model,
                )
            except Exception as e:
                self.transcribe_error.emit(f"Deepgram init failed: {e}")
                return None

        # ── OpenAI Realtime ────────────────────────────────────────────────────
        elif provider == "openai_realtime":
            if not openai_key:
                self.transcribe_error.emit(
                    "No OpenAI API key available.\n"
                    "Contact support or add your own key in Settings → API Keys."
                )
                return None
            try:
                from audio.stt_openai_realtime import OpenAIRealtimeSTT
                model = cfg.get("openai_stt_model", "gpt-4o-mini-transcribe")
                return OpenAIRealtimeSTT(
                    api_key           = openai_key,
                    on_partial        = self._on_partial,
                    on_error          = self._on_stt_error,
                    on_smart_dispatch = (self._on_smart_dispatch if smart else None),
                    on_speech_stopped = self._on_stt_vad_stopped,
                    model             = model,
                    language          = self._language,
                    silence_ms        = 500,
                )
            except Exception as e:
                self.transcribe_error.emit(f"OpenAI Realtime STT init failed: {e}")
                return None

        # ── Unknown / legacy provider ──────────────────────────────────────────
        else:
            msg = (
                f"STT provider '{provider}' is no longer supported.\n\n"
                "Please open Settings → Audio and select:\n"
                "  • Deepgram  (recommended)\n"
                "  • OpenAI Realtime  (gpt-4o-mini-transcribe)"
            ) if provider == "whisper" else (
                f"Unknown STT provider: '{provider}'.\n"
                "Open Settings → Audio to select a valid provider."
            )
            self.transcribe_error.emit(msg)
            return None


# ── Language code helper ───────────────────────────────────────────────────────

def _lang_code(language: str) -> str:
    mapping = {
        "english":  "en", "hindi":    "hi",
        "spanish":  "es", "french":   "fr",
        "german":   "de", "mandarin": "zh",
        "arabic":   "ar",
    }
    return mapping.get(language.lower(), "en")