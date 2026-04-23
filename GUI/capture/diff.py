"""
Image diff detector for auto-capture mode.

Compares two screenshots and returns whether the screen
has changed enough to warrant a new capture + solve.

Uses fast image hashing — no heavy CV dependencies.
"""

import hashlib
import io
import base64
from typing import Optional
from PIL import Image


def compute_hash(b64_image: str) -> str:
    """Compute a perceptual hash of a base64 screenshot."""
    img = _b64_to_pil(b64_image)
    # Resize to tiny thumbnail for fast comparison
    thumb = img.resize((16, 16), Image.LANCZOS).convert("L")
    pixels = list(thumb.getdata())
    avg = sum(pixels) / len(pixels)
    # Binary hash: 1 if pixel > avg, else 0
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return bits


def has_changed(hash_a: str, hash_b: str, threshold: float = 0.10) -> bool:
    """
    Returns True if two hashes differ by more than `threshold` ratio.
    threshold=0.10 means 10% of pixels differ → meaningful change.
    """
    if not hash_a or not hash_b:
        return True
    if len(hash_a) != len(hash_b):
        return True
    diff_bits = sum(a != b for a, b in zip(hash_a, hash_b))
    diff_ratio = diff_bits / len(hash_a)
    return diff_ratio > threshold


def pixel_diff_percent(b64_a: str, b64_b: str) -> float:
    """
    Returns percentage of pixels that changed between two screenshots.
    More accurate than hash but slower — use for debugging.
    """
    img_a = _b64_to_pil(b64_a).resize((320, 180)).convert("RGB")
    img_b = _b64_to_pil(b64_b).resize((320, 180)).convert("RGB")

    pixels_a = list(img_a.getdata())
    pixels_b = list(img_b.getdata())

    changed = sum(
        1 for pa, pb in zip(pixels_a, pixels_b)
        if abs(pa[0]-pb[0]) + abs(pa[1]-pb[1]) + abs(pa[2]-pb[2]) > 30
    )
    return changed / len(pixels_a)


def _b64_to_pil(b64: str) -> Image.Image:
    data = base64.b64decode(b64)
    return Image.open(io.BytesIO(data))