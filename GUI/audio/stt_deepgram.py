"""
Deepgram Streaming STT — optimised for low latency.

Optimisations applied
---------------------
1. feed() queues raw (ndarray, native_sr) — no resampling in the
   audio-callback thread.  Resampling happens in the WebSocket sender
   thread, keeping the callback non-blocking.
2. Queue timeout reduced 50 ms → 10 ms for tighter audio send loop.
3. Pure-NumPy resampling — scipy removed entirely.
4. Windows native rates (44 100 / 48 000 Hz) handled transparently.

Deepgram defaults (for reference):
  endpointing:         10 ms   (speech_final trigger)
  utterance_end_ms:    not set by default (must be explicit)
  Flux eot_timeout_ms: 5000 ms (forced EndOfTurn fallback)

Two API modes
-------------
V1  nova-3, nova-2  — standard streaming, interim_results + endpointing
V2  flux-general-multi  — TurnInfo events, lower latency for live speech

Auto-reconnect (Bug-R fix)
--------------------------
WebSocket code 1005 ("no status received") is an abnormal closure that
Deepgram sends when it drops the connection internally (e.g. transient
server-side error, network blip).  Previously this killed the sender
thread permanently — the STT object stayed alive but silent, so no
transcription happened until the user toggled interview mode off/on.

Fix: both _run_nova and _run_flux now loop with exponential back-off
(1 s → 2 s → 4 s → 8 s, capped at 8 s) and reconnect automatically
as long as self._running is True.  The audio queue is drained on each
reconnect so stale audio is not replayed.
"""

import threading
import queue as _queue
import json
import time as _time
import numpy as np
import websockets.sync.client as ws_sync
from typing import Callable, Optional

from audio.resample_utils import resample_numpy

TARGET_SR = 16_000

# Reconnect back-off schedule (seconds): 1, 2, 4, 8, 8, 8, …
_BACKOFF = [1, 2, 4, 8]

V1_URL_BASE = (
    "wss://api.deepgram.com/v1/listen"
    "?model={model}"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&language={language}"
    "&interim_results=true"
    "&endpointing=300"
    "&smart_format=true"
    "&punctuate=true"
)

# Appended to V1_URL_BASE only when smart_answering=True (on_segment_ready wired).
# VAD events are not needed when auto_answer=False — omitting them saves bandwidth
# and avoids spurious SpeechStarted/UtteranceEnd messages.
V1_VAD_PARAM = "&vad_events=true"

V2_URL_BASE = (
    "wss://api.deepgram.com/v2/listen"
    "?model={model}"
    "&encoding=linear16"
    "&sample_rate=16000"
)


class DeepgramStreamingSTT:
    def __init__(
        self,
        api_key:          str,
        on_partial:       Callable[[str], None],
        on_error:         Callable[[str], None],
        on_segment_ready: Optional[Callable[[str], None]] = None,
        language:         str = "en",
        model:            str = "nova-3",
    ):
        self._api_key          = api_key
        self._on_partial       = on_partial
        self._on_error         = on_error
        self._on_segment_ready = on_segment_ready
        self._language         = language
        self._model            = model

        # Queue holds (np.ndarray at native_sr, native_sr) tuples.
        # Resampling is done in the sender thread — not in the audio callback.
        # FIX: Add maxsize to prevent memory bloat during network lag
        self._audio_q: _queue.Queue = _queue.Queue(maxsize=100)  # ~2.3s @ 44100Hz
        self._thread:  Optional[threading.Thread] = None
        self._running  = False
        self._stop_event = threading.Event()

        self._current_partial = ""
        self._committed_text  = ""
        self._accumulated     = ""
        self._full_transcript = ""

        # FIX: Track last logged transcript to deduplicate Flux Update spam
        self._last_logged_transcript = ""

    # ── Public API ─────────────────────────────────────────────

    def _is_flux(self) -> bool:
        return "flux" in self._model.lower()

    def start(self, native_sr: int):
        self._native_sr       = native_sr
        self._running         = True
        self._stop_event.clear()
        self._current_partial = ""
        self._committed_text  = ""
        self._accumulated     = ""
        self._full_transcript = ""
        self._thread = threading.Thread(
            target=self._run_flux if self._is_flux() else self._run_nova,
            daemon=True,
        )
        self._thread.start()
        print(
            f"[deepgram] Started — model={self._model} "
            f"native_sr={native_sr} Hz → target={TARGET_SR} Hz"
        )

    def feed(self, pcm_int16: np.ndarray, native_sr: int):
        """
        Called from the audio-callback thread.
        Queues raw audio — resampling happens in the sender thread
        so the callback returns immediately.
        """
        if not self._running:
            return
        self._audio_q.put((pcm_int16.copy(), native_sr))

    def reset_segment(self):
        self._current_partial = ""
        self._committed_text  = ""
        self._accumulated     = ""

    def get_segment_transcript(self) -> str:
        return self._accumulated.strip()

    def transcribe_current_segment(self) -> str:
        """Alias — returns accumulated text (no API call)."""
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

    # ── V1 — nova-2 / nova-3 ───────────────────────────────────

    def _run_nova(self):
        # Issue 3 fix: only include vad_events when smart_answering=True
        # (i.e. when on_segment_ready callback is wired).  Omitting it when
        # auto_answer=False saves bandwidth and avoids spurious VAD messages.
        vad_param = V1_VAD_PARAM if self._on_segment_ready else ""
        url = (V1_URL_BASE + vad_param).format(model=self._model, language=self._language)
        headers = {"Authorization": f"Token {self._api_key}"}

        attempt = 0
        while self._running:
            backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
            if attempt > 0:
                print(f"[deepgram] nova reconnecting (attempt {attempt}) in {backoff}s …")
                _time.sleep(backoff)
                if not self._running:
                    break
                self._drain_audio_queue()

            attempt += 1
            print(
                f"[deepgram] Connecting nova → {self._model}  "
                f"vad_events={'yes' if vad_param else 'no'}"
            )
            try:
                with ws_sync.connect(url, additional_headers=headers) as ws:
                    print("[deepgram] nova connected ✓")
                    attempt = 0  # reset back-off on successful connect

                    threading.Thread(
                        target=self._receive_loop,
                        args=(ws, self._handle_nova_message),
                        daemon=True,
                    ).start()

                    # Bug D fix: keepalive thread — sends KeepAlive every 8 s so
                    # the Deepgram WebSocket does not drop after 60 s of silence
                    # (e.g. when the pipeline is paused / gated).
                    threading.Thread(
                        target=self._keepalive_loop,
                        args=(ws, False),
                        daemon=True,
                    ).start()

                    # ── Sender loop ────────────────────────────────
                    # Resampling happens HERE — not in the audio callback.
                    # Loop exits on send error → outer while reconnects.
                    # TTFT-OPT: Reduced timeout 10ms→5ms to cut queue latency by ~50%.
                    while self._running:
                        try:
                            raw_pcm, native_sr = self._audio_q.get(timeout=0.005)
                            pcm_bytes = resample_numpy(
                                raw_pcm, native_sr, TARGET_SR
                            ).tobytes()
                            ws.send(pcm_bytes)
                        except _queue.Empty:
                            continue
                        except Exception as e:
                            print(f"[deepgram] nova send error (will reconnect): {e}")
                            break  # break inner → outer while reconnects

                    self._send_close(ws)

            except Exception as e:
                if not self._running:
                    break
                print(f"[deepgram] nova connect failed (will retry): {e}")
                # outer while loop will sleep + retry

    def _handle_nova_message(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "Metadata":
            print(f"[deepgram] session {msg.get('request_id', '')[:8]}")
            return
        if msg_type in ("SpeechStarted", "UtteranceEnd"):
            return
        if msg_type != "Results":
            return

        try:
            transcript = msg["channel"]["alternatives"][0]["transcript"].strip()
        except (KeyError, IndexError):
            return

        if not transcript:
            return

        is_final     = msg.get("is_final",     False)
        speech_final = msg.get("speech_final", False)

        if speech_final:
            self._committed_text  = self._append(self._committed_text, transcript)
            self._full_transcript = self._append(self._full_transcript, transcript)
            self._current_partial = ""
            self._accumulated     = self._committed_text
            print(f"[deepgram] ✅ FINAL: '{transcript[:60]}'")
            if self._on_segment_ready:
                self._on_segment_ready(self._accumulated)

        elif is_final:
            self._committed_text  = self._append(self._committed_text, transcript)
            self._full_transcript = self._append(self._full_transcript, transcript)
            self._current_partial = ""
            self._accumulated     = self._committed_text
            print(f"[deepgram] 📝 is_final: '{transcript[:60]}'")

        else:
            self._current_partial = transcript
            self._accumulated = (
                f"{self._committed_text} {transcript}".strip()
                if self._committed_text else transcript
            )

        self._on_partial(self._accumulated)

    # ── V2 — flux-general-en / flux-general-multi ──────────────

    def _run_flux(self):
        url     = V2_URL_BASE.format(model=self._model)
        headers = {"Authorization": f"Token {self._api_key}"}

        attempt = 0
        while self._running:
            backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
            if attempt > 0:
                print(f"[deepgram] flux reconnecting (attempt {attempt}) in {backoff}s …")
                _time.sleep(backoff)
                if not self._running:
                    break
                self._drain_audio_queue()

            attempt += 1
            print(f"[deepgram] Connecting flux → {self._model}")
            try:
                with ws_sync.connect(url, additional_headers=headers) as ws:
                    print("[deepgram] flux connected ✓")
                    attempt = 0  # reset back-off on successful connect

                    threading.Thread(
                        target=self._receive_loop,
                        args=(ws, self._handle_flux_message),
                        daemon=True,
                    ).start()

                    # Issue 2 fix (revised): flux endpoint does NOT support
                    # KeepAlive — only CloseStream and Configure are valid.
                    # Sending KeepAlive to flux causes a server deserialization
                    # error and a 1005 disconnect/reconnect loop.
                    # We pass is_flux=True so _keepalive_loop exits immediately.
                    threading.Thread(
                        target=self._keepalive_loop,
                        args=(ws, True),
                        daemon=True,
                    ).start()

                    # Sender loop — exits on send error → outer while reconnects.
                    # TTFT-OPT: Reduced timeout 10ms→5ms to cut queue latency by ~50%.
                    while self._running:
                        try:
                            raw_pcm, native_sr = self._audio_q.get(timeout=0.005)
                            pcm_bytes = resample_numpy(
                                raw_pcm, native_sr, TARGET_SR
                            ).tobytes()
                            ws.send(pcm_bytes)
                        except _queue.Empty:
                            continue
                        except Exception as e:
                            print(f"[deepgram] flux send error (will reconnect): {e}")
                            break  # break inner → outer while reconnects

                    self._send_close(ws)

            except Exception as e:
                if not self._running:
                    break
                print(f"[deepgram] flux connect failed (will retry): {e}")
                # outer while loop will sleep + retry

    def _handle_flux_message(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "Connected":
            print(f"[deepgram] flux session {msg.get('request_id', '')[:8]}")
            return
        if msg_type in ("ConfigureSuccess",):
            return
        if msg_type == "Error":
            # Server-side error — log it but do NOT surface to UI.
            # The outer reconnect loop in _run_flux will re-establish the
            # WebSocket automatically; calling _on_error here would kill
            # the interview mode UI for a transient server hiccup.
            desc = msg.get("description", str(msg))
            print(f"[deepgram] flux server error (will reconnect): {desc}")
            return
        if msg_type != "TurnInfo":
            return

        event      = msg.get("event")
        transcript = msg.get("transcript", "").strip()
        if not transcript:
            return

        # FIX: Only log when transcript actually changes (deduplicate Update spam)
        # Flux sends many Update events as transcript stabilizes — logging every
        # one creates 80+ duplicate lines. Only log when text changes.
        if transcript != self._last_logged_transcript:
            print(f"[deepgram] flux [{event}]: '{transcript[:60]}'")
            self._last_logged_transcript = transcript

        if event in ("Update", "StartOfTurn", "TurnResumed", "EagerEndOfTurn"):
            self._current_partial = transcript
            self._accumulated     = transcript
            self._on_partial(self._accumulated)

        elif event == "EndOfTurn":
            self._committed_text  = transcript
            self._full_transcript = self._append(self._full_transcript, transcript)
            self._current_partial = ""
            self._accumulated     = self._committed_text
            # Always log EndOfTurn (even if duplicate) for visibility
            print(f"[deepgram] ✅ EndOfTurn: '{transcript[:60]}'")
            self._last_logged_transcript = ""  # Reset for next turn
            if self._on_segment_ready:
                self._on_segment_ready(self._accumulated)
            self._on_partial(self._accumulated)

    # ── Shared helpers ─────────────────────────────────────────

    def _drain_audio_queue(self):
        """Discard stale audio accumulated while the WebSocket was down."""
        drained = 0
        while True:
            try:
                self._audio_q.get_nowait()
                drained += 1
            except _queue.Empty:
                break
        if drained:
            print(f"[deepgram] Drained {drained} stale audio chunks before reconnect")

    def _keepalive_loop(self, ws, is_flux: bool = False):
        """
        Bug D fix — sends a Deepgram KeepAlive message every 8 seconds
        for V1 (nova) connections only.

        Deepgram closes the WebSocket if no data (audio or ping) is received
        for 60 seconds.  When the pipeline is paused / gated (Interview Mode
        toggled off, or user is speaking), no audio chunks are sent.  Without
        this keepalive the connection drops with:
          "The client did not receive a websocket Ping message in the last 60 s"

        The KeepAlive message is documented in the Deepgram Streaming API:
          {"type": "KeepAlive"}
        It is valid for V1 (nova) endpoints ONLY.

        V2 (flux) endpoints do NOT support KeepAlive — only CloseStream and
        Configure are valid.  Sending KeepAlive to flux causes:
          "unknown variant `KeepAlive`, expected `CloseStream` or `Configure`"
        followed by a 1005 disconnect.  For flux we use WebSocket protocol-level
        ping frames (RFC 6455 opcode 0x9) instead — these are transport-level
        and not interpreted by the Deepgram application layer.

        Interval: 8 s for nova, 30 s for flux (well within the 60 s server timeout).
        """
        if is_flux:
            # Flux does not accept Deepgram JSON KeepAlive, but DOES accept
            # WebSocket protocol-level ping frames (RFC 6455 opcode 0x9).
            # Send a ping every 30s to prevent the 60s server-side timeout.
            # TTFT-OPT: keepalive prevents reconnect overhead
            while self._running:
                _time.sleep(30)
                if not self._running:
                    break
                try:
                    ws.ping()
                except Exception as e:
                    # FIX (HIGH-2): Ping failed → close WS to trigger immediate reconnect
                    # Without this, sender continues queuing audio for 30s+ until timeout
                    print(f"[deepgram] Flux ping failed (triggering reconnect): {e}")
                    try:
                        ws.close(1000, "keepalive ping failed")
                    except Exception:
                        pass
                    break
            return
        keepalive_msg = json.dumps({"type": "KeepAlive"})
        while self._running:
            _time.sleep(8)
            if not self._running:
                break
            try:
                ws.send(keepalive_msg)
            except Exception:
                # WebSocket already closed — exit silently.
                break

    def _receive_loop(self, ws, handler: Callable):
        """
        Dedicated receiver thread — keeps sender loop unblocked.

        Exceptions here mean the WebSocket closed (abnormally or normally).
        We do NOT call _on_error — the outer reconnect loop in _run_nova /
        _run_flux will detect the broken sender and reconnect transparently.
        Surfacing a receiver error to the UI would show a spurious toast on
        every transient disconnect (e.g. the 1005 no-status-received drop).
        """
        try:
            for raw in ws:
                if not self._running:
                    break
                if isinstance(raw, str):
                    handler(raw)
        except Exception as e:
            # Log for diagnostics but do NOT emit to UI — reconnect handles it.
            if self._running:
                print(f"[deepgram] receiver closed ({e}) — reconnect loop will retry")

    @staticmethod
    def _send_close(ws):
        try:
            ws.send(json.dumps({"type": "CloseStream"}))
        except Exception:
            pass

    @staticmethod
    def _append(existing: str, new: str) -> str:
        """Append *new* to *existing* with a single space, strip edges."""
        return f"{existing} {new}".strip() if existing else new