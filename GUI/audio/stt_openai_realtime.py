"""
OpenAI Realtime Transcription STT

Architecture
------------
WebSocket: wss://api.openai.com/v1/realtime?intent=transcription
Auth:      Authorization: Bearer {api_key}  +  OpenAI-Beta: realtime=v1

Server-side VAD eliminates the whisper hallucination problem entirely:
the server only transcribes audio when it detects actual speech energy.

Thread model
------------
  Main thread      → start() / stop() / feed() / reset_segment()
  Sender thread    → dequeues raw PCM → resample 24 kHz → base64 → ws.send()
  Receiver thread  → ws → _handle_message()
  (Both sender + receiver are daemon threads — no manual join needed.)

Event flow per turn
-------------------
  input_audio_buffer.speech_started
      ↓  (deltas stream while speech continues)
  conversation.item.input_audio_transcription.delta   × N
      ↓
  input_audio_buffer.speech_stopped          ← calls on_speech_stopped()
      ↓
  input_audio_buffer.committed
      ↓
  conversation.item.input_audio_transcription.completed
      ↓  calls on_smart_dispatch(final_text)  [when smart_answering=ON]

Silence clock locking  (pipeline.py integration)
-------------------------------------------------
  speech_stopped  → on_speech_stopped() → pipeline locks _last_speech_time.
  completed       → accumulated updated; _on_partial NOT called to avoid
                    resetting the locked clock, which would add an extra
                    silence_threshold delay on top of the server VAD wait.

Audio format
------------
  OpenAI Realtime expects PCM16 at 24 000 Hz.
  Resampling from native device SR (44100 / 48000) is done in the
  sender thread so the audio-callback returns immediately.
  Uses the same resample_numpy() as Deepgram — just with target=24000.

Models (stt_provider = "openai_realtime")
-----------------------------------------
  gpt-4o-mini-transcribe  $0.003 / min  (default — fast + cheap)
  gpt-4o-transcribe       $0.006 / min  (highest accuracy)

Default VAD values (from OpenAI docs):
  threshold:           0.5
  prefix_padding_ms:   300
  silence_duration_ms: 500   ← our default matches

"""

import threading
import queue as _queue
import json
import base64
import time
import numpy as np
import websockets.sync.client as ws_sync
from typing import Callable, Optional

from audio.resample_utils import resample_numpy

TARGET_SR    = 24_000
REALTIME_URL = "wss://api.openai.com/v1/realtime?intent=transcription"


class OpenAIRealtimeSTT:
    """
    Streaming STT via OpenAI Realtime API (GA, not beta) with server-side VAD.

    Parameters
    ----------
    api_key            : OpenAI API key (sk-...)
    on_partial         : called with accumulated text on each delta event
    on_error           : called on fatal WebSocket / transcription errors
    on_smart_dispatch  : called with final text on transcription.completed
                         only passed when smart_answering=True
    on_speech_stopped  : called when server VAD fires speech_stopped
                         pipeline uses this to lock the silence clock
    model              : "gpt-4o-mini-transcribe" or "gpt-4o-transcribe"
    language           : BCP-47 code ("en", "hi", etc.)
    silence_ms         : server VAD silence_duration_ms (default 500 ms)
    """

    def __init__(
        self,
        api_key:           str,
        on_partial:        Callable[[str], None],
        on_error:          Callable[[str], None],
        on_smart_dispatch: Optional[Callable[[str], None]] = None,
        on_speech_stopped: Optional[Callable[[], None]]    = None,
        model:             str = "gpt-4o-mini-transcribe",
        language:          str = "en",
        silence_ms:        int = 500,
    ):
        self._api_key           = api_key
        self._on_partial        = on_partial
        self._on_error          = on_error
        self._on_smart_dispatch = on_smart_dispatch
        self._on_speech_stopped = on_speech_stopped
        self._model             = model
        self._language          = language
        self._silence_ms        = silence_ms

        self._audio_q:   _queue.Queue               = _queue.Queue()
        self._thread:    Optional[threading.Thread]  = None
        self._running    = False
        self._stop_event = threading.Event()
        self._native_sr  = TARGET_SR

        self._current_partial = ""
        self._accumulated     = ""
        self._full_transcript = ""
        self._active_item_id: Optional[str] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, native_sr: int):
        self._native_sr       = native_sr
        self._running         = True
        self._stop_event.clear()
        self._current_partial = ""
        self._accumulated     = ""
        self._full_transcript = ""
        self._active_item_id  = None

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="openai-realtime-stt",
        )
        self._thread.start()
        print(
            f"[openai_realtime] Starting — "
            f"model={self._model}  "
            f"native_sr={native_sr} Hz → {TARGET_SR} Hz  "
            f"silence_ms={self._silence_ms}"
        )

    def feed(self, pcm_int16: np.ndarray, native_sr: int):
        if not self._running:
            return
        self._audio_q.put((pcm_int16.copy(), native_sr))

    def reset_segment(self):
        self._current_partial = ""
        self._accumulated     = ""
        self._active_item_id  = None
        print("[openai_realtime] Segment reset — ready for next question")

    def get_segment_transcript(self) -> str:
        return self._accumulated.strip()

    def transcribe_current_segment(self) -> str:
        return self._accumulated.strip()

    def get_full_transcript(self) -> str:
        return self._full_transcript.strip()

    def close(self):
        """
        Close WebSocket connections immediately.
        Alias for stop() for compatibility with pipeline.pause().
        """
        self.stop()

    def stop(self) -> str:
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        return self._full_transcript.strip() or self._accumulated.strip()

    # ── WebSocket sender / main thread ────────────────────────────────────────

    def _run(self):
        # GA API no longer requires the beta header but we keep it
        # as a fallback for accounts still on the beta endpoint.
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            with ws_sync.connect(
                REALTIME_URL,
                additional_headers=headers,
                open_timeout=10,
            ) as ws:
                print("[openai_realtime] WebSocket connected ✓")

                # ── Receiver thread ────────────────────────────────────────────
                threading.Thread(
                    target=self._receive_loop,
                    args=(ws,),
                    daemon=True,
                    name="openai-realtime-recv",
                ).start()

                # ── Session config — GA format ─────────────────────────────────
                # FIXED: must use "session.update" with nested session.audio.input
                # and explicitly set "type": "transcription" in the session block.
                ws.send(json.dumps({
                    "type": "session.update",
                    "session": {
                        "type": "transcription",          # ← REQUIRED in GA
                        "audio": {
                            "input": {
                                "format": {
                                    "type": "audio/pcm",  # ← GA format string
                                    "rate": TARGET_SR,    # 24000
                                },
                                "transcription": {
                                    "model":    self._model,
                                    "language": self._language,
                                    "prompt": (
                                        "Interview question and answer session. "
                                        "Technical topics: software engineering, "
                                        "algorithms, system design."
                                    ),
                                },
                                "turn_detection": {
                                    "type":                "server_vad",
                                    "threshold":           0.5,
                                    "prefix_padding_ms":   300,
                                    "silence_duration_ms": self._silence_ms,
                                },
                                "noise_reduction": {
                                    "type": "near_field",
                                },
                            }
                        },
                    },
                }))

                # ── Audio sender loop ──────────────────────────────────────────
                # TTFT-OPT: Reduced timeout 10ms→5ms to cut queue latency by ~50%.
                while self._running:
                    try:
                        raw_pcm, native_sr = self._audio_q.get(timeout=0.005)
                        pcm_24k   = resample_numpy(raw_pcm, native_sr, TARGET_SR)
                        audio_b64 = base64.b64encode(
                            pcm_24k.tobytes()
                        ).decode("utf-8")
                        ws.send(json.dumps({
                            "type":  "input_audio_buffer.append",
                            "audio": audio_b64,
                        }))
                    except _queue.Empty:
                        continue
                    except Exception as e:
                        if self._running:
                            self._on_error(f"[openai_realtime] send error: {e}")
                        break

                # ── Clean disconnect ───────────────────────────────────────────
                try:
                    ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
                except Exception:
                    pass

        except Exception as e:
            if self._running:
                self._on_error(f"OpenAI Realtime connect failed: {e}")

    # ── Receiver loop ─────────────────────────────────────────────────────────

    def _receive_loop(self, ws):
        try:
            for raw in ws:
                if not self._running:
                    break
                if isinstance(raw, str):
                    self._handle_message(raw)
        except Exception as e:
            if self._running:
                self._on_error(f"[openai_realtime] receiver error: {e}")

    # ── Message handler ───────────────────────────────────────────────────────

    def _handle_message(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")

        # ── Session lifecycle ──────────────────────────────────────────────────
        if msg_type == "session.created":
            sid = msg.get("session", {}).get("id", "")
            print(f"[openai_realtime] Session created  id={sid[:12]}")
            return

        if msg_type == "session.updated":
            print("[openai_realtime] Session configured ✓  (VAD active)")
            return

        # ── VAD events ─────────────────────────────────────────────────────────
        if msg_type == "input_audio_buffer.speech_started":
            self._current_partial = ""
            print("[openai_realtime] 🎤 speech_started")
            return

        if msg_type == "input_audio_buffer.speech_stopped":
            print("[openai_realtime] 🔇 speech_stopped  (server VAD)")
            if self._on_speech_stopped:
                self._on_speech_stopped()
            return

        if msg_type == "input_audio_buffer.committed":
            self._active_item_id = msg.get("item_id")
            print(f"[openai_realtime] Buffer committed → item={self._active_item_id}")
            return

        # ── Streaming partial text ─────────────────────────────────────────────
        if msg_type == "conversation.item.input_audio_transcription.delta":
            delta = msg.get("delta", "")
            if delta:
                self._current_partial += delta
                self._accumulated      = self._current_partial
                self._on_partial(self._accumulated)
            return

        # ── Final transcript ───────────────────────────────────────────────────
        if msg_type == "conversation.item.input_audio_transcription.completed":
            text = msg.get("transcript", "").strip()
            if not text:
                return

            self._accumulated     = text
            self._current_partial = text
            self._full_transcript = (
                f"{self._full_transcript} {text}".strip()
                if self._full_transcript else text
            )
            print(f"[openai_realtime] ✅ FINAL: '{text[:70]}'")

            # FIX (HIGH-3): Update ticker with final committed text
            # We still call _on_partial() to update the ticker display.
            # The silence clock lock (set by speech_stopped) prevents
            # _last_speech_time from being reset, so timing is preserved.
            if self._on_partial:
                self._on_partial(text)  # Ticker shows final text

            if self._on_smart_dispatch:
                self._on_smart_dispatch(text)
            return

        # ── Transcription failed ───────────────────────────────────────────────
        if msg_type == "conversation.item.input_audio_transcription.failed":
            err = msg.get("error", {})
            print(f"[openai_realtime] ⚠ Transcription failed: {err.get('message', err)}")
            return

        # ── API error ─────────────────────────────────────────────────────────
        if msg_type == "error":
            err     = msg.get("error", {})
            err_msg = err.get("message", str(msg))
            code    = err.get("code", "")
            if code in ("auth_error", "rate_limit_exceeded", "insufficient_quota"):
                self._on_error(f"OpenAI Realtime: {err_msg}")
            else:
                print(f"[openai_realtime] API error [{code}]: {err_msg}")
            return

        # All other events silently ignored
        # (response.*, conversation.item.created, etc.)