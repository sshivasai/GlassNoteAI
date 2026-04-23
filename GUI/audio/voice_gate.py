# ===== File: audio/voice_gate.py =====
"""
Voice Activity Gate — monitors the microphone for user speech.

When the user is speaking → dispatch is held.
When the user stops      → dispatch is released after hold_time seconds.

Optimisations / improvements in this revision
---------------------------------------------
1. _calibration_samples list is cleared after calibration completes.
   Previously the 88-float list was kept in memory forever — minor leak
   in long sessions.                                                    ← NEW

2. get_is_calibrated() added.
   Pipeline can query whether the noise-floor calibration has finished
   before trusting the gate output.                                     ← NEW

3. get_calibrated_threshold() added.
   Useful for debugging (logged at recording start).                    ← NEW

4. Callbacks called directly from audio thread — no Thread() creation.
   PyQt6 cross-thread signals are queued automatically; the callback
   returns in microseconds.  (Unchanged from previous version.)

Windows note
------------
The voice gate always opens the microphone at native SR (44100 / 48000 Hz).
No resampling — we only measure RMS energy, which is SR-independent.
"""

import threading
import time
import numpy as np
from typing import Callable, Optional


DEFAULT_ENERGY_THRESHOLD = 0.02   # 0.0 – 1.0 normalised RMS


class VoiceActivityGate:
    """
    Lightweight energy-based VAD on the microphone.
    No STT — purely used to gate the silence-dispatch logic.
    """

    def __init__(
        self,
        on_user_started:  Optional[Callable[[], None]] = None,
        on_user_stopped:  Optional[Callable[[], None]] = None,
        speech_threshold: float = DEFAULT_ENERGY_THRESHOLD,
        hold_time:        float = 1.0,
    ):
        self._on_user_started  = on_user_started
        self._on_user_stopped  = on_user_stopped
        self._speech_threshold = speech_threshold
        self._hold_time        = hold_time

        self._user_speaking    = False
        self._last_speech_time = 0.0
        self._stream           = None
        self._running          = False

        # Calibration state
        self._calibrating:           bool        = True
        self._calibration_samples:   list[float] = []
        self._calibration_done:      bool        = False
        self._calibrated_threshold:  float       = speech_threshold

    # ── Public ─────────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Open microphone stream.  Returns True on success.
        No resampling — energy detection is SR-independent.
        """
        try:
            import sounddevice as sd
            info      = sd.query_devices(kind="input")
            native_sr = int(info["default_samplerate"])

            self._running = True
            self._stream  = sd.InputStream(
                samplerate = native_sr,
                channels   = 1,
                dtype      = "int16",
                blocksize  = 1_024,
                callback   = self._audio_callback,
            )
            self._stream.start()
            print(
                f"[voice_gate] Mic monitoring @ {native_sr} Hz "
                f"— calibrating noise floor for ~2 s ..."
            )
            return True

        except Exception as e:
            print(f"[voice_gate] Failed to open mic: {e}")
            return False

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._user_speaking = False
        print("[voice_gate] Stopped")

    def is_user_speaking(self) -> bool:
        """
        True if user is currently speaking.
        Hold-time is enforced in _audio_callback; this is a plain flag
        read — no time arithmetic, no lock needed.
        """
        return self._user_speaking

    def get_user_speech_age(self) -> float:
        """Seconds since user last spoke.  Returns inf if never spoke."""
        if self._last_speech_time == 0.0:
            return float("inf")
        return time.time() - self._last_speech_time

    def get_is_calibrated(self) -> bool:          # ← NEW
        """
        True once the ~2 s noise-floor calibration pass has completed.
        During calibration is_user_speaking() always returns False
        (conservative — allows dispatch while calibrating).
        """
        return self._calibration_done

    def get_calibrated_threshold(self) -> float:  # ← NEW
        """
        Returns the auto-calibrated RMS threshold.
        Useful for debug logging at recording start.
        """
        return self._calibrated_threshold

    def set_threshold(self, threshold: float):
        """Manually override the calibrated threshold."""
        self._speech_threshold    = threshold
        self._calibrated_threshold = threshold

    def recalibrate(self):
        """Trigger a fresh noise-floor calibration pass."""
        self._calibrating          = True
        self._calibration_samples  = []
        self._calibration_done     = False
        print("[voice_gate] Recalibrating noise floor ...")

    # ── Private ────────────────────────────────────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._running:
            return

        audio = indata.flatten().astype(np.float32) / 32_768.0
        rms   = float(np.sqrt(np.mean(audio ** 2)))

        # ── Calibration phase (~2 s) ───────────────────────────────────────────
        if self._calibrating:
            self._calibration_samples.append(rms)

            # blocksize=1024:
            #   @ 44 100 Hz → ~43 callbacks/s → 88 samples ≈ 2.05 s
            #   @ 48 000 Hz → ~47 callbacks/s → 88 samples ≈ 1.87 s
            if len(self._calibration_samples) >= 88:
                noise_floor = float(
                    np.percentile(self._calibration_samples, 80)
                )
                self._calibrated_threshold = max(noise_floor * 4.0, 0.008)
                self._calibrating         = False
                self._calibration_done    = True

                # ← NEW: free the sample list — no longer needed
                self._calibration_samples = []

                print(
                    f"[voice_gate] Calibrated ✓  "
                    f"noise_floor={noise_floor:.4f}  "
                    f"threshold={self._calibrated_threshold:.4f}"
                )
            return   # never gate during calibration

        # ── Speech detection ───────────────────────────────────────────────────
        threshold = self._calibrated_threshold

        if rms > threshold:
            self._last_speech_time = time.time()

            if not self._user_speaking:
                self._user_speaking = True
                # Direct call — no Thread() creation.
                # PyQt6 cross-thread signals are auto-queued and return
                # immediately — safe from the audio callback thread.
                if self._on_user_started:
                    self._on_user_started()

        else:
            if self._user_speaking:
                age = time.time() - self._last_speech_time
                if age > self._hold_time:
                    self._user_speaking = False
                    if self._on_user_stopped:
                        self._on_user_stopped()   # direct call — same as above