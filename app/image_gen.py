"""Image generation and processing (MVP: existing images only)."""

import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class ImageError(Exception):
    """Custom exception for image processing errors."""
    pass


def validate_image(image_path: Path) -> bool:
    """Validate image file (size, format, etc.)."""
    if not image_path.exists():
        return False

    # Check file size (max 5MB for MVP)
    max_size = 5 * 1024 * 1024  # 5MB
    if image_path.stat().st_size > max_size:
        logger.warning(f"Image {image_path.name} exceeds 5MB")
        return False

    # Check format
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if image_path.suffix.lower() not in allowed_extensions:
        logger.warning(f"Image {image_path.name} has unsupported format")
        return False

    return True


def get_images_from_work_dir(work_dir: Path) -> list[Path]:
    """Get all valid image files from work directory."""
    images_dir = work_dir / "images"
    if not images_dir.exists():
        return []

    valid_images = []
    for image_path in images_dir.iterdir():
        if image_path.is_file() and validate_image(image_path):
            valid_images.append(image_path)

    logger.info(f"Found {len(valid_images)} valid images in {work_dir.name}")
    return valid_images


def generate_image(prompt: str, style: str) -> Optional[Path]:
    """Generate image from prompt (MVP: not implemented)."""
    if settings.images_provider == "none":
        logger.debug("Image generation disabled (MVP mode)")
        return None

    # TODO: Implement for P3
    raise NotImplementedError("Image generation not implemented in MVP")
