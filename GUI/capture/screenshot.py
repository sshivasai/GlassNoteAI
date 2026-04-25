"""
Screenshot capture module — OPTIMIZED VERSION.

Changes:
  - capture_fullscreen() checks for saved region first
  - _pil_to_base64 targets 768px — fits single OpenAI vision tile
  - Smart format: PNG for text, JPEG for diagrams
  - capture_with_region() for region-based capture
  - Cached mss instance avoids ~5-20ms per-call overhead
  - PNG optimize=False saves ~10-30ms (LLM client skips re-optimization)
"""

import base64
import io
import time
from typing import Optional, Tuple
from PIL import Image

from settings import config

# ---------------------------------------------------------------------------
# Lazy-singleton for the mss screen-capture context.
# Re-creating mss.mss() on every call costs ~5-20 ms; caching it removes
# that overhead.  If the instance becomes stale (e.g. display topology
# change), the grab() call will raise and we transparently recreate it.
# ---------------------------------------------------------------------------
_mss_instance = None


def _get_mss():
    """Return a cached mss instance, creating one on first call."""
    global _mss_instance
    if _mss_instance is None:
        import mss
        _mss_instance = mss.mss()
    return _mss_instance


def _reset_mss():
    """Discard the cached mss instance so the next call creates a fresh one."""
    global _mss_instance
    try:
        if _mss_instance is not None:
            _mss_instance.close()
    except Exception:
        pass
    _mss_instance = None


def capture_fullscreen(monitor_index: int = 1) -> str:
    """
    Capture screen. Uses saved region if configured, else full screen.
    Returns base64-encoded PNG/JPEG string.
    """
    # Check if user has set a capture region.
    # config.load_config() is cheap — it's mtime-cached and only re-reads
    # the file when it has actually changed on disk.
    cfg = config.load_config()
    region = cfg.get("capture_region", None)

    if region and isinstance(region, dict):
        try:
            return capture_region(
                region["x"], region["y"],
                region["width"], region["height"]
            )
        except Exception as e:
            print(f"[screenshot] Region capture failed, using fullscreen: {e}")

    return _capture_full(monitor_index)


def _capture_full(monitor_index: int = 1) -> str:
    try:
        sct = _get_mss()
        monitor = sct.monitors[monitor_index]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return _pil_to_base64(img)
    except ImportError:
        raise ImportError("mss not installed. Run: pip install mss")
    except Exception as e:
        # mss instance may be stale after display changes — recreate & retry
        _reset_mss()
        try:
            sct = _get_mss()
            monitor = sct.monitors[monitor_index]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return _pil_to_base64(img)
        except Exception:
            raise e  # raise the original error if retry also fails


def capture_region(x: int, y: int, width: int, height: int) -> str:
    """
    Capture a specific region of the screen.
    Returns base64-encoded string.
    """
    try:
        sct = _get_mss()
        region = {"top": y, "left": x, "width": width, "height": height}
        raw = sct.grab(region)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return _pil_to_base64(img)
    except ImportError:
        raise ImportError("mss not installed. Run: pip install mss")
    except Exception as e:
        # mss instance may be stale after display changes — recreate & retry
        _reset_mss()
        try:
            sct = _get_mss()
            region = {"top": y, "left": x, "width": width, "height": height}
            raw = sct.grab(region)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return _pil_to_base64(img)
        except Exception:
            raise e  # raise the original error if retry also fails


def _is_text_heavy(img: Image.Image) -> bool:
    """
    Detect if a screenshot is mostly text (code editors, documents, etc.)
    or a photo/diagram.

    Downsamples to 64×64 grayscale and checks if >40% of pixels are
    near-white or near-black — characteristic of text on a background.

    Args:
        img (Image.Image): The screenshot to analyze.

    Returns:
        bool: True if text-heavy (save as PNG), False if photo (save as JPEG).
    """
    try:
        small  = img.resize((64, 64)).convert("L")
        pixels = list(small.getdata())
        n      = len(pixels)
        if n == 0:
            return True
        white = sum(1 for p in pixels if p > 240)
        black = sum(1 for p in pixels if p < 15)
        return (white + black) / n > 0.40
    except Exception:
        return True  # default to PNG on error


def _pil_to_base64(img: Image.Image, max_width: int = 768) -> str:
    """
    Convert PIL image to base64 string with smart format selection.

    - Max 768px wide (single OpenAI vision tile ≈2s faster TTFT)
    - Text-heavy screenshots → PNG (lossless, sharp text)
    - Photo/diagram screenshots → JPEG quality=85 (~40% smaller)

    Args:
        img (Image.Image): The captured screenshot.
        max_width (int): Maximum width in pixels. Images wider than this
            are downscaled proportionally.

    Returns:
        str: Base64-encoded image string.
    """
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()

    if _is_text_heavy(img):
        # optimize=False: saves ~10-30ms; the LLM client skips
        # re-optimization for capture-pipeline images anyway.
        img.save(buffer, format="PNG")
    else:
        # JPEG for photos/diagrams — ~40% smaller base64 payload
        img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=85, optimize=True)

    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def base64_to_pil(b64: str) -> Image.Image:
    data = base64.b64decode(b64)
    return Image.open(io.BytesIO(data))


def save_region(x: int, y: int, width: int, height: int):
    """Save capture region to config."""
    config.set("capture_region", {
        "x": x, "y": y, "width": width, "height": height
    })
    print(f"[screenshot] Region saved: {width}×{height} at ({x},{y})")


def clear_region():
    """Remove saved region — revert to fullscreen."""
    config.set("capture_region", None)
    print("[screenshot] Region cleared — using fullscreen")


def get_saved_region() -> Optional[dict]:
    """Get saved capture region or None."""
    return config.get("capture_region", None)