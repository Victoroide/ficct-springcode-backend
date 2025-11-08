"""Image validation service for UML diagram processing.

Validates image format, size, dimensions and content before OCR processing.
"""

import base64
import logging
from io import BytesIO
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_MB = 20
MIN_WIDTH = 100
MIN_HEIGHT = 100
MAX_WIDTH = 4096
MAX_HEIGHT = 4096

ALLOWED_FORMATS = {"PNG", "JPEG", "JPG", "GIF", "BMP", "WEBP"}


class InvalidImageError(Exception):
    """Error when image validation fails."""

    pass


class ImageValidator:
    """
    Validates images for UML diagram OCR processing.

    Features:
    - Format validation (PNG, JPEG, GIF, BMP, WEBP)
    - Size validation (max 20MB)
    - Dimension validation (100x100 to 4096x4096)
    - Base64 decoding
    - Image integrity check

    Example:
        >>> validator = ImageValidator()
        >>> is_valid, error = validator.validate_image(base64_data)
    """

    def validate_image(self, base64_image: str) -> Tuple[bool, str]:
        """
        Validate image for OCR processing.

        Args:
            base64_image: Base64 encoded image data

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> is_valid, error = validator.validate_image(image_data)
            >>> if not is_valid:
            ...     raise InvalidImageError(error)
        """
        try:
            image_data = self._decode_base64(base64_image)

            if not self._validate_size(image_data):
                return False, f"Image size exceeds {MAX_IMAGE_SIZE_MB}MB limit"

            image = self._load_image(image_data)

            if not self._validate_format(image):
                return (
                    False,
                    f"Invalid format. Allowed: {', '.join(ALLOWED_FORMATS)}",
                )

            if not self._validate_dimensions(image):
                return (
                    False,
                    f"Invalid dimensions. Must be {MIN_WIDTH}x{MIN_HEIGHT} to {MAX_WIDTH}x{MAX_HEIGHT}",
                )

            logger.info(
                f"Image validated: {image.format} {image.width}x{image.height}"
            )
            return True, ""

        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False, f"Image validation error: {str(e)}"

    def decode_and_load(self, base64_image: str) -> Image.Image:
        """
        Decode base64 and load PIL Image.

        Args:
            base64_image: Base64 encoded image

        Returns:
            PIL Image object

        Raises:
            InvalidImageError: If decoding fails
        """
        try:
            image_data = self._decode_base64(base64_image)
            return self._load_image(image_data)
        except Exception as e:
            raise InvalidImageError(f"Failed to decode image: {e}")

    def _decode_base64(self, base64_str: str) -> bytes:
        """Decode base64 string to bytes."""
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]

        try:
            return base64.b64decode(base64_str)
        except Exception as e:
            raise InvalidImageError(f"Invalid base64 encoding: {e}")

    def _validate_size(self, image_data: bytes) -> bool:
        """Validate image size in bytes."""
        size_mb = len(image_data) / (1024 * 1024)
        return size_mb <= MAX_IMAGE_SIZE_MB

    def _load_image(self, image_data: bytes) -> Image.Image:
        """Load PIL Image from bytes."""
        try:
            return Image.open(BytesIO(image_data))
        except Exception as e:
            raise InvalidImageError(f"Cannot open image: {e}")

    def _validate_format(self, image: Image.Image) -> bool:
        """Validate image format."""
        if image.format is None:
            return False
        return image.format.upper() in ALLOWED_FORMATS

    def _validate_dimensions(self, image: Image.Image) -> bool:
        """Validate image dimensions."""
        width, height = image.size

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return False

        if width > MAX_WIDTH or height > MAX_HEIGHT:
            return False

        return True
