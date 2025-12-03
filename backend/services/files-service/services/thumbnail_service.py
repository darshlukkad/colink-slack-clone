"""Thumbnail generation service for images."""

import logging
from io import BytesIO
from typing import Optional

from PIL import Image

from ..config import settings

logger = logging.getLogger(__name__)


class ThumbnailService:
    """Service for generating image thumbnails."""

    def __init__(self):
        """Initialize thumbnail service."""
        self.thumbnail_size = (settings.thumbnail_size, settings.thumbnail_size)
        self.thumbnail_format = "JPEG"
        self.thumbnail_quality = 85

    def generate_thumbnail(self, image_data: bytes, original_format: str = "JPEG") -> Optional[bytes]:
        """Generate thumbnail from image data.

        Args:
            image_data: Original image as bytes
            original_format: Original image format

        Returns:
            Thumbnail image as bytes, or None if generation fails
        """
        try:
            # Open image from bytes
            image = Image.open(BytesIO(image_data))

            # Convert RGBA to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
                image = background

            # Generate thumbnail (maintains aspect ratio)
            image.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

            # Save to bytes
            thumb_bytes = BytesIO()
            image.save(thumb_bytes, format=self.thumbnail_format, quality=self.thumbnail_quality, optimize=True)
            thumb_bytes.seek(0)

            logger.info(f"Generated thumbnail: {image.size} -> {self.thumbnail_size}")
            return thumb_bytes.read()

        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return None

    def is_image(self, content_type: str) -> bool:
        """Check if content type is an image.

        Args:
            content_type: MIME type

        Returns:
            True if image type
        """
        return content_type.startswith("image/")

    def is_supported_image(self, filename: str) -> bool:
        """Check if image format is supported for thumbnail generation.

        Args:
            filename: Name of the file

        Returns:
            True if supported
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in settings.image_extensions


# Global thumbnail service instance
thumbnail_service = ThumbnailService()
