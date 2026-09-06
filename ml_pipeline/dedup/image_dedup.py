"""
ml_pipeline/dedup/image_dedup.py — Perceptual Image Hashing for Deduplication

Provides perceptual hashing (pHash) and Hamming distance comparison to detect
identical, resized, recompressed, or slightly modified images of structural damage.
Handles missing or corrupt images gracefully without crashing.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Union

import imagehash
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

ImageInput = Union[str, Path, bytes, Image.Image, None]


def compute_image_hash(
    image_input: ImageInput,
    hash_func: str = "phash",
    hash_size: int = 8,
) -> imagehash.ImageHash | None:
    """
    Compute a perceptual hash for an image.

    Supports:
    - File path string or pathlib.Path
    - In-memory raw bytes
    - Pre-opened PIL.Image.Image instance
    - None / empty string (returns None safely)

    Resilience:
    - Missing files (FileNotFoundError) -> returns None
    - Corrupt or unsupported files (UnidentifiedImageError, OSError) -> returns None
    - None / empty input -> returns None
    Never raises an unhandled exception or crashes caller.

    Args:
        image_input: Path, bytes, PIL Image, or None.
        hash_func: Hashing algorithm ('phash', 'dhash', 'ahash'). Default: 'phash'.
        hash_size: Size of the hash grid (default 8 -> 64-bit hash).

    Returns:
        imagehash.ImageHash or None if input is invalid/missing.
    """
    if image_input is None:
        return None

    if isinstance(image_input, str):
        image_input = image_input.strip()
        if not image_input:
            return None
        path = Path(image_input)
        if not path.exists() or not path.is_file():
            logger.debug("Image file does not exist: %s", image_input)
            return None
        try:
            with Image.open(path) as img:
                return _hash_pil_image(img, hash_func=hash_func, hash_size=hash_size)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning("Failed to open image file %s: %s", image_input, exc)
            return None

    elif isinstance(image_input, Path):
        if not image_input.exists() or not image_input.is_file():
            logger.debug("Image path does not exist: %s", image_input)
            return None
        try:
            with Image.open(image_input) as img:
                return _hash_pil_image(img, hash_func=hash_func, hash_size=hash_size)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning("Failed to open image path %s: %s", image_input, exc)
            return None

    elif isinstance(image_input, (bytes, bytearray)):
        if len(image_input) == 0:
            return None
        try:
            with Image.open(io.BytesIO(image_input)) as img:
                return _hash_pil_image(img, hash_func=hash_func, hash_size=hash_size)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning("Failed to parse image from bytes: %s", exc)
            return None

    elif isinstance(image_input, Image.Image):
        try:
            return _hash_pil_image(image_input, hash_func=hash_func, hash_size=hash_size)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to compute hash from PIL Image: %s", exc)
            return None

    else:
        logger.debug("Unsupported image input type: %s", type(image_input))
        return None


def _hash_pil_image(
    img: Image.Image,
    hash_func: str = "phash",
    hash_size: int = 8,
) -> imagehash.ImageHash:
    """Internal helper to compute hash on a PIL Image."""
    # Ensure image is in RGB / L mode for consistent hash calculation
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    func = getattr(imagehash, hash_func, imagehash.phash)
    return func(img, hash_size=hash_size)


def compare_image_hashes(
    hash1: imagehash.ImageHash | None,
    hash2: imagehash.ImageHash | None,
) -> int | None:
    """
    Calculate the Hamming distance (number of bit differences) between two image hashes.

    Returns:
        Integer Hamming distance (0 = identical, 64 = completely inverted),
        or None if either hash is None.
    """
    if hash1 is None or hash2 is None:
        return None
    try:
        return int(hash1 - hash2)
    except Exception as exc:
        logger.debug("Failed to compare image hashes: %s", exc)
        return None


def image_similarity_score(
    hash1: imagehash.ImageHash | None,
    hash2: imagehash.ImageHash | None,
    max_bits: int = 64,
) -> float | None:
    """
    Convert Hamming distance into a normalized similarity score in [0.0, 1.0].

    1.0 = identical perceptual hash
    0.0 = completely different hash (>= max_bits)
    None = one or both images are missing
    """
    dist = compare_image_hashes(hash1, hash2)
    if dist is None:
        return None
    similarity = max(0.0, 1.0 - (dist / float(max_bits)))
    return round(similarity, 4)


def is_duplicate_image(
    hash1: imagehash.ImageHash | None,
    hash2: imagehash.ImageHash | None,
    threshold: int = 10,
) -> bool:
    """
    Determine if two images are duplicate/near-duplicate based on Hamming distance threshold.

    Returns:
        True if Hamming distance <= threshold, else False.
        Returns False if either hash is None.
    """
    dist = compare_image_hashes(hash1, hash2)
    if dist is None:
        return False
    return dist <= threshold
