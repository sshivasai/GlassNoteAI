"""
utils/async_image.py — Async image processing for parallel optimization.

Processes multiple images concurrently using asyncio.

Usage:
    from utils.async_image import process_images_async

    optimized = await process_images_async(images)
"""

import asyncio
import base64
import io
from typing import List
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from utils.logger import get_logger

logger = get_logger(__name__)


async def optimize_image_async(
    b64: str,
    max_width: int = 1280,
    quality: int = 85,
) -> str:
    """
    Async image optimization.

    Args:
        b64: Base64 image data
        max_width: Maximum width
        quality: JPEG quality

    Returns:
        str: Optimized base64 image
    """
    loop = asyncio.get_event_loop()

    def _optimize():
        try:
            data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(data)).convert("RGB")

            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Detect if text-heavy
            is_text = _is_text_heavy(img)

            buf = io.BytesIO()
            if is_text:
                img.save(buf, format="PNG", optimize=True)
            else:
                img.save(buf, format="JPEG", quality=quality, optimize=True)

            return base64.b64encode(buf.getvalue()).decode("utf-8")

        except Exception as e:
            logger.error(f"Image optimization failed: {e}", exc_info=True)
            return b64  # Return original on error

    # Run in thread pool to avoid blocking event loop
    return await loop.run_in_executor(None, _optimize)


def _is_text_heavy(img: Image.Image) -> bool:
    """Check if image is text-heavy (code, documents)."""
    try:
        small = img.resize((64, 64)).convert("L")
        pixels = list(small.getdata())
        n = len(pixels)

        if n == 0:
            return True

        white = sum(1 for p in pixels if p > 240)
        black = sum(1 for p in pixels if p < 15)

        return (white + black) / n > 0.40

    except Exception:
        return True


async def process_images_async(
    images: List[str],
    max_width: int = 1280,
    quality: int = 85,
    max_concurrent: int = 4,
) -> List[str]:
    """
    Process multiple images concurrently.

    Args:
        images: List of base64 images
        max_width: Maximum width
        quality: JPEG quality
        max_concurrent: Max concurrent operations

    Returns:
        List[str]: Optimized images
    """
    if not images:
        return []

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process_with_limit(img):
        async with semaphore:
            return await optimize_image_async(img, max_width, quality)

    # Process all images concurrently
    tasks = [_process_with_limit(img) for img in images]
    return await asyncio.gather(*tasks)


# ── Sync Wrapper ───────────────────────────────────────────────────────────────

def process_images_parallel(
    images: List[str],
    max_width: int = 1280,
    quality: int = 85,
    max_workers: int = 4,
) -> List[str]:
    """
    Synchronous parallel image processing.

    Uses ThreadPoolExecutor for parallel optimization without asyncio.

    Args:
        images: List of base64 images
        max_width: Maximum width
        quality: JPEG quality
        max_workers: Max worker threads

    Returns:
        List[str]: Optimized images
    """
    if not images:
        return []

    def _optimize(img):
        try:
            data = base64.b64decode(img)
            pil_img = Image.open(io.BytesIO(data)).convert("RGB")

            if pil_img.width > max_width:
                ratio = max_width / pil_img.width
                new_size = (max_width, int(pil_img.height * ratio))
                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)

            is_text = _is_text_heavy(pil_img)

            buf = io.BytesIO()
            if is_text:
                pil_img.save(buf, format="PNG", optimize=True)
            else:
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)

            return base64.b64encode(buf.getvalue()).decode("utf-8")

        except Exception as e:
            logger.error(f"Image optimization failed: {e}", exc_info=True)
            return img

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_optimize, images))

    return results
