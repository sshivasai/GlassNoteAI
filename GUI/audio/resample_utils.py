# ===== File: audio/resample_utils.py =====
"""
audio/resample_utils.py

Pure-NumPy audio resampling — zero scipy dependency.

Linear interpolation is sufficient quality for speech-recognition
pipelines targeting 16 kHz or 24 kHz.  STT models are trained on
≤16 kHz data; OpenAI Realtime uses 24 kHz.  Anti-aliasing above
those frequencies is wasted for our use case.

Windows devices report one of these native rates:
  44 100 Hz  (CD / consumer default)
  48 000 Hz  (WASAPI / professional default)

STT targets                                    # ← UPDATED
-------
  TARGET_SR     = 16 000 Hz  →  Deepgram (nova-2, nova-3, flux-general-multi)
  TARGET_SR_OAI = 24 000 Hz  →  OpenAI Realtime (gpt-4o-transcribe family)

Common conversions
------------------
  44 100 → 16 000  n_new = round(n × 160/441)
  48 000 → 16 000  n_new = round(n / 3)          ← exact integer ratio
  44 100 → 24 000  n_new = round(n × 240/441)
  48 000 → 24 000  n_new = round(n / 2)          ← exact integer ratio  # ← NEW
  22 050 → 16 000  n_new = round(n × 320/441)
"""

import numpy as np

TARGET_SR     = 16_000   # Deepgram and legacy STT backends
TARGET_SR_OAI = 24_000   # OpenAI Realtime API  ← NEW


def resample_numpy(
    audio:     np.ndarray,
    orig_sr:   int,
    target_sr: int = TARGET_SR,
) -> np.ndarray:
    """
    Resample *audio* from *orig_sr* → *target_sr*.

    Fast paths are used for the common integer-ratio cases (e.g.
    48 000→16 000 = 3:1 decimation, 48 000→24 000 = 2:1 decimation).
    Non-integer ratios fall back to linear interpolation.

    Parameters
    ----------
    audio     : int16 or float32/64 PCM samples (1-D)
    orig_sr   : source sample rate  (e.g. 44100, 48000)
    target_sr : target sample rate  (default 16000; pass 24000 for OpenAI)

    Returns
    -------
    int16 numpy array at *target_sr*

    Common conversions
    ------------------
    44 100 → 16 000  : n_new = round(n * 160/441)   ← interpolation
    48 000 → 16 000  : n_new = n / 3                 ← fast decimation
    44 100 → 24 000  : n_new = round(n * 240/441)   ← interpolation
    48 000 → 24 000  : n_new = n / 2                 ← fast decimation
    """
    # Ensure we have a proper int16 array to work with
    pcm_int16 = np.asarray(audio, dtype=np.int16) if np.issubdtype(
        np.asarray(audio).dtype, np.integer
    ) else np.clip(
        np.asarray(audio, dtype=np.float64), -32_768.0, 32_767.0
    ).astype(np.int16)

    # ── No-op: same rate ────────────────────────────────────────────
    if orig_sr == target_sr:
        return np.ascontiguousarray(pcm_int16)

    if len(pcm_int16) == 0:
        return np.zeros(0, dtype=np.int16)

    # ── Fast path: integer-ratio downsampling (decimation) ──────────
    # e.g. 48 000→16 000 (ratio=3), 48 000→24 000 (ratio=2)
    # Valid because the mic hardware / OS audio stack already low-pass
    # filters well below the Nyquist of the target rate.
    ratio, remainder = divmod(orig_sr, target_sr)
    if remainder == 0 and ratio > 1:
        decimated = pcm_int16[::ratio]
        return np.ascontiguousarray(decimated)

    # ── Fast path: integer-ratio upsampling (repeat) ────────────────
    # Less common but handles e.g. 8 000→16 000 (ratio_up=2)
    ratio_up, remainder_up = divmod(target_sr, orig_sr)
    if remainder_up == 0 and ratio_up > 1:
        return np.repeat(pcm_int16, ratio_up)

    # ── Fallback: linear interpolation for non-integer ratios ───────
    # e.g. 44 100→16 000, 44 100→24 000
    audio_f64 = pcm_int16.astype(np.float64)
    n_orig = len(audio_f64)
    n_new = int(round(n_orig * target_sr / orig_sr))
    if n_new == 0:
        return np.zeros(0, dtype=np.int16)

    x_old = np.linspace(0.0, 1.0, n_orig)
    x_new = np.linspace(0.0, 1.0, n_new)

    return np.clip(
        np.interp(x_new, x_old, audio_f64),
        -32_768.0, 32_767.0,
    ).astype(np.int16)


# ── Convenience wrappers ───────────────────────────────────────────────────────
# Saves callers from spelling out the target — avoids magic numbers
# scattered across stt_deepgram.py and stt_openai_realtime.py.

def resample_for_deepgram(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """Resample to 16 000 Hz for Deepgram nova / flux."""           # ← NEW
    return resample_numpy(audio, orig_sr, TARGET_SR)


def resample_for_openai(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """Resample to 24 000 Hz for OpenAI Realtime gpt-4o-transcribe."""  # ← NEW
    return resample_numpy(audio, orig_sr, TARGET_SR_OAI)