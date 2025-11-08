"""OCR engine wrapper using Tesseract and EasyOCR.

Provides text extraction from images using dual OCR approach for better accuracy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV (cv2) not available")

try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract OCR not available")

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not available")


class OCRFailedError(Exception):
    """Error when OCR processing fails."""

    pass


class OCREngine:
    """
    Dual OCR engine using Tesseract and EasyOCR.

    Features:
    - Tesseract for fast text extraction
    - EasyOCR for multilingual support
    - Confidence scoring
    - Preprocessing for better accuracy

    Example:
        >>> engine = OCREngine()
        >>> text = engine.extract_text(image_array)
        >>> boxes = engine.extract_with_boxes(image_array)
    """

    def __init__(self):
        """Initialize OCR engines."""
        self.tesseract_available = TESSERACT_AVAILABLE
        self.easyocr_available = EASYOCR_AVAILABLE

        if not self.tesseract_available and not self.easyocr_available:
            logger.error("No OCR engines available")

        if self.easyocr_available:
            try:
                self.easyocr_reader = easyocr.Reader(["en"], gpu=False)
                logger.info("EasyOCR initialized")
            except Exception as e:
                logger.warning(f"EasyOCR initialization failed: {e}")
                self.easyocr_available = False

    def extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from image using available OCR engines.
        
        Falls back through Tesseract -> EasyOCR -> empty string.
        Never raises exception to allow graceful degradation.

        Args:
            image: Image as numpy array (BGR format from OpenCV)

        Returns:
            Extracted text (empty string if all engines fail)
        """
        # Try Tesseract first (faster)
        if self.tesseract_available:
            try:
                result = self._extract_with_tesseract(image)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Tesseract extraction failed: {e}", exc_info=True)

        # Try EasyOCR second (more accurate but slower)
        if self.easyocr_available:
            try:
                result = self._extract_with_easyocr(image)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"EasyOCR extraction failed: {e}", exc_info=True)

        # Graceful degradation - return empty instead of crashing
        logger.error("All OCR engines failed - returning empty text")
        return ""

    def extract_with_boxes(
        self, image: np.ndarray
    ) -> List[Dict[str, any]]:
        """
        Extract text with bounding box coordinates.

        Args:
            image: Image as numpy array

        Returns:
            List of dicts with text, bbox, and confidence

        Example:
            >>> boxes = engine.extract_with_boxes(image)
            >>> for box in boxes:
            ...     print(box['text'], box['confidence'])
        """
        if self.easyocr_available:
            try:
                return self._extract_boxes_easyocr(image)
            except Exception as e:
                logger.warning(f"EasyOCR box extraction failed: {e}")

        if self.tesseract_available:
            try:
                return self._extract_boxes_tesseract(image)
            except Exception as e:
                logger.warning(f"Tesseract box extraction failed: {e}")

        return []

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Handles various image formats gracefully. If preprocessing fails,
        returns original image to allow OCR to attempt extraction anyway.

        Args:
            image: Original image

        Returns:
            Preprocessed image (or original if preprocessing fails)

        Steps:
            1. Convert to grayscale
            2. Apply denoising
            3. Apply adaptive thresholding
            4. Apply morphological operations
        """
        try:
            # Check if image is already grayscale or needs conversion
            if len(image.shape) == 2:
                # Already grayscale (1 channel)
                gray = image
            elif len(image.shape) == 3:
                channels = image.shape[2]
                if channels == 1:
                    # Grayscale with explicit channel dimension
                    gray = image.squeeze()
                elif channels == 3:
                    # BGR image, convert to grayscale
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                elif channels == 4:
                    # BGRA image, convert to grayscale
                    gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
                else:
                    logger.warning(f"Unexpected number of channels: {channels}, using original")
                    return image
            else:
                logger.warning(f"Unexpected image shape: {image.shape}, using original")
                return image

            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

            thresh = cv2.adaptiveThreshold(
                denoised,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2,
            )

            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            return processed
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}, using original image", exc_info=True)
            return image

    def _extract_with_tesseract(self, image: np.ndarray) -> str:
        """Extract text using Tesseract."""
        preprocessed = self.preprocess_image(image)

        pil_image = Image.fromarray(preprocessed)

        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(pil_image, config=custom_config)

        return text.strip()

    def _extract_with_easyocr(self, image: np.ndarray) -> str:
        """Extract text using EasyOCR."""
        results = self.easyocr_reader.readtext(image)

        text_parts = [result[1] for result in results]
        return "\n".join(text_parts)

    def _extract_boxes_tesseract(
        self, image: np.ndarray
    ) -> List[Dict[str, any]]:
        """Extract text boxes using Tesseract."""
        preprocessed = self.preprocess_image(image)
        pil_image = Image.fromarray(preprocessed)

        data = pytesseract.image_to_data(
            pil_image, output_type=pytesseract.Output.DICT
        )

        boxes = []
        for i in range(len(data["text"])):
            if int(data["conf"][i]) > 0:
                boxes.append(
                    {
                        "text": data["text"][i],
                        "bbox": [
                            data["left"][i],
                            data["top"][i],
                            data["left"][i] + data["width"][i],
                            data["top"][i] + data["height"][i],
                        ],
                        "confidence": float(data["conf"][i]) / 100,
                    }
                )

        return boxes

    def _extract_boxes_easyocr(
        self, image: np.ndarray
    ) -> List[Dict[str, any]]:
        """Extract text boxes using EasyOCR."""
        results = self.easyocr_reader.readtext(image)

        boxes = []
        for bbox, text, confidence in results:
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]

            boxes.append(
                {
                    "text": text,
                    "bbox": [
                        min(x_coords),
                        min(y_coords),
                        max(x_coords),
                        max(y_coords),
                    ],
                    "confidence": float(confidence),
                }
            )

        return boxes
