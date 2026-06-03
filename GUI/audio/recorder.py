"""
Audio recorder — captures system audio (WASAPI loopback) or microphone.

Windows reality
---------------
Devices always open at their *native* sample rate — typically 44 100 Hz
or 48 000 Hz.  Asking sounddevice for 16 000 Hz on a WASAPI loopback
device usually fails or introduces Windows-side SRC artefacts.

This recorder therefore:
  1. Opens the device at its reported native SR.
  2. Sends raw native-SR chunks downstream via on_chunk(bytes, native_sr).
  3. Each STT module is responsible for resampling to its required SR:
       Deepgram       → 16 000 Hz  (resample_for_deepgram)
       OpenAI Realtime→ 24 000 Hz  (resample_for_openai)
  4. stop() resamples accumulated frames to 16 000 Hz for WAV export.

Optimisations applied
---------------------
- collections.deque(maxlen=…) replaces list + manual pop(0).           ← NEW
  pop(0) on a list is O(n); deque append with maxlen is O(1).
  At 48 kHz / 1024 frames the cap is ~168 750 chunks; the old code
  would shift all ~168 750 pointers on every overflow — now it's free.

- indata.flatten() replaces indata.copy().flatten().                    ← NEW
  np.ndarray.flatten() always returns a copy, so the extra .copy()
  was allocating and then immediately discarding a second array on
  every audio callback (~47 times per second at 48 kHz).

- astype(np.int16, copy=False) in _to_wav().                           ← NEW
  When the array is already int16 (the normal path), copy=False avoids
  an unnecessary allocation before the final .tobytes() call.

- O(1) duration counter (_total_samples running int).
- Frame buffer capped at _MAX_FRAME_CHUNKS to bound memory.
"""

import sys
import threading
import io
import wave
from collections import deque                         # ← NEW import
from typing import Optional, Callable

import numpy as np

from audio.resample_utils import resample_numpy, TARGET_SR

CHANNELS     = 1
CHUNK_FRAMES = 1_024
DTYPE        = "int16"

# Cap: ~60 min of audio at 48 kHz / 1024 frames per chunk ≈ 168 750 chunks.
# Used as deque maxlen — oldest chunks are silently dropped on overflow.
# Continuous-mode users never call stop() for WAV export anyway.
_MAX_FRAME_CHUNKS: int = int(48_000 * 60 * 60 / CHUNK_FRAMES)   # ≈ 168 750


class AudioRecorder:
    def __init__(
        self,
        source:   str = "system",
        on_level: Optional[Callable[[float], None]] = None,
        on_chunk: Optional[Callable[[bytes, int], None]] = None,
        on_stereo_mix_warning: Optional[Callable[[], None]] = None,
        # on_chunk(raw_pcm_bytes_at_native_sr, native_sr)
        # on_stereo_mix_warning() called when Stereo Mix is not enabled
    ):
        self._source    = source
        self._on_level  = on_level
        self._on_chunk  = on_chunk
        self._on_stereo_mix_warning = on_stereo_mix_warning
        self._recording = False
        self._lock      = threading.Lock()
        self._stream    = None
        self._mic_stream = None
        self._native_sr = TARGET_SR   # updated when device opens

        # ── Frame buffer — deque with automatic O(1) maxlen cap ───────────────
        # Previously a plain list; pop(0) on a list is O(n).
        # deque.append() with maxlen drops the leftmost item in O(1).    ← NEW
        self._frames: deque[np.ndarray] = deque(maxlen=_MAX_FRAME_CHUNKS)

        # Running sample count — written only from the audio-callback thread.
        # GIL-atomic for machine-word int values; no lock needed.
        self._total_samples: int = 0

    # ── Public ─────────────────────────────────────────────────────────────────

    def start(self):
        if self._recording:
            return
        self._recording     = True
        self._frames        = deque(maxlen=_MAX_FRAME_CHUNKS)   # ← NEW (was list)
        self._total_samples = 0

        try:
            import sounddevice as sd
            opened_loopback = False

            if self._source in ("system", "both") and sys.platform == "win32":
                opened_loopback = self._start_loopback(sd)

            if self._source in ("microphone", "both") or not opened_loopback:
                self._start_microphone(sd)

        except ImportError:
            raise ImportError(
                "sounddevice not installed.  Run: pip install sounddevice"
            )
        except Exception as e:
            self._recording = False
            raise RuntimeError(f"Audio capture failed: {e}")

    def stop(self) -> bytes:
        """
        Stop recording.  Returns WAV bytes resampled to 16 000 Hz.
        Resampling happens ONCE here — not on every chunk.
        """
        self._recording = False

        for stream in (self._stream, self._mic_stream):
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception as e:
                    # FIX (LOW-1): Log errors instead of silent pass
                    print(f"[recorder] Stream cleanup error: {e}")
        self._stream = self._mic_stream = None

        with self._lock:
            # deque → list so np.concatenate can iterate it         ← NOTE
            frames = list(self._frames)
            self._frames.clear()

        if not frames:
            return b""

        audio     = np.concatenate(frames)
        audio_16k = resample_numpy(audio, self._native_sr, TARGET_SR)
        return self._to_wav(audio_16k)

    def is_recording(self) -> bool:
        return self._recording

    def get_native_sr(self) -> int:
        return self._native_sr

    def get_duration_seconds(self) -> float:
        """O(1) — uses running sample counter, no buffer scan."""
        return self._total_samples / max(self._native_sr, 1)

    # ── Private ────────────────────────────────────────────────────────────────

    def _start_loopback(self, sd) -> bool:
        try:
            device_idx = self._find_loopback_device(sd)
            if device_idx is None:
                # FIX: Emit warning to user about Stereo Mix not being enabled
                print("[recorder] ⚠️  STEREO MIX NOT ENABLED — falling back to mic")
                self._emit_stereo_mix_warning()
                return False

            info      = sd.query_devices(device_idx)
            native_sr = int(info["default_samplerate"])
            native_ch = min(int(info["max_input_channels"]), 2)  # Cap at 2 to avoid weird multichannel
            self._native_sr = native_sr
            self._loopback_channels = native_ch
            print(
                f"[recorder] Loopback : [{device_idx}] {info['name']} "
                f"@ {native_sr} Hz ({native_ch} ch) → STT resamples internally"
            )

            self._stream = sd.InputStream(
                device    = device_idx,
                samplerate= native_sr,
                channels  = native_ch,
                dtype     = DTYPE,
                blocksize = CHUNK_FRAMES,
                callback  = self._audio_callback,
            )
            self._stream.start()
            return True

        except Exception as e:
            print(f"[recorder] Loopback failed: {e}")
            self._stream = None
            return False

    def _start_microphone(self, sd):
        try:
            info      = sd.query_devices(kind="input")
            native_sr = int(info["default_samplerate"])
            self._native_sr = native_sr
            print(
                f"[recorder] Microphone: {info['name']} "
                f"@ {native_sr} Hz → STT resamples internally"
            )

            self._mic_stream = sd.InputStream(
                samplerate= native_sr,
                channels  = CHANNELS,
                dtype     = DTYPE,
                blocksize = CHUNK_FRAMES,
                callback  = self._audio_callback,
            )
            self._mic_stream.start()
        except Exception as e:
            print(f"[recorder] Microphone failed: {e}")
            self._mic_stream = None

    def _find_loopback_device(self, sd) -> Optional[int]:
        keywords = [
            "stereo mix", "what u hear", "loopback",
            "wave out",   "monitor",     "mix",
            "wasapi",     "virtual",     "voicemeeter",
        ]
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                if any(kw in dev["name"].lower() for kw in keywords):
                    return i
        return None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[recorder] ⚠ {status}")

        # ── Stereo downmix if needed ──────────────────────────────────────────────
        if indata.shape[1] > 1:
            chunk = indata.mean(axis=1).astype(indata.dtype).flatten()
        else:
            chunk = indata.flatten()

        with self._lock:
            # deque with maxlen automatically drops oldest — no manual pop  ← CHANGED
            self._frames.append(chunk)
            self._total_samples += len(chunk)

        # VU meter — energy only, SR-independent
        if self._on_level:
            level = float(np.abs(chunk).mean()) / 32_768.0
            self._on_level(min(1.0, level * 10))

        # Stream raw native-SR bytes downstream.
        # STT modules resample to their required SR in their own threads.
        if self._on_chunk:
            self._on_chunk(chunk.tobytes(), self._native_sr)

    def _emit_stereo_mix_warning(self):
        """Emit warning callback when Stereo Mix is not enabled."""
        if self._on_stereo_mix_warning:
            try:
                self._on_stereo_mix_warning()
            except Exception as e:
                print(f"[recorder] Warning callback failed: {e}")

    def _to_wav(self, audio: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_SR)
            # copy=False: avoids redundant allocation when dtype is already  ← CHANGED
            # int16 (the normal path from resample_numpy)
            wf.writeframes(audio.astype(np.int16, copy=False).tobytes())
        buf.seek(0)
        return buf.read()