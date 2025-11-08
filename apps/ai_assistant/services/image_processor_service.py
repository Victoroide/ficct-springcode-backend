"""Image processor service using local OCR.

Processes UML diagram images to extract classes, attributes, methods and relationships
using local OCR (Tesseract + EasyOCR + YOLO) instead of OpenAI Vision API.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from PIL import Image

from .cache_service import CacheService
from .image_validator import ImageValidator, InvalidImageError
from .ocr_engine import OCREngine, OCRFailedError
from .position_calculator import PositionCalculator
from .rate_limiter import RateLimiter
from .uml_parser import NoUMLDetectedError, UMLParser
from .yolo_detector import YOLODetector

logger = logging.getLogger(__name__)

CACHE_TTL_IMAGES = 3600
RATE_LIMIT_IMAGES = 10
RATE_LIMIT_WINDOW = 3600


class OCRLibrariesUnavailableError(Exception):
    """Raised when required OCR libraries are not installed."""
    pass


class ImageProcessorService:
    """
    Process UML diagram images using local OCR.

    Processing Pipeline:
    1. Validate image (format, size, dimensions)
    2. Detect UML boxes with YOLO/OpenCV
    3. Preprocess image for OCR
    4. Extract text with Tesseract + EasyOCR
    5. Parse UML elements (classes, attributes, methods)
    6. Calculate positions for React Flow
    7. Convert to React Flow format

    Example:
        >>> processor = ImageProcessorService()
        >>> result = processor.process_image(base64_image, session_id="abc123")
    """

    def __init__(self):
        """Initialize image processor with local OCR components."""
        self.validator = ImageValidator()
        self.ocr_engine = OCREngine()
        self.yolo_detector = YOLODetector()
        self.uml_parser = UMLParser()
        self.position_calculator = PositionCalculator()

        logger.info("Image Processor Service initialized (local OCR mode)")

    def process_image(
        self,
        base64_image: str,
        session_id: Optional[str] = None,
        use_cache: bool = True,
        merge_with_existing: bool = False,
        existing_diagram: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process UML diagram image and return React Flow format.

        Args:
            base64_image: Base64 encoded image
            session_id: Session ID for rate limiting
            use_cache: Whether to use cache
            merge_with_existing: Merge with existing diagram
            existing_diagram: Existing diagram data if merging

        Returns:
            Dictionary with nodes, edges, and metadata

        Raises:
            OCRLibrariesUnavailableError: If required OCR libraries not installed
            InvalidImageError: If image validation fails
            OCRFailedError: If OCR processing fails
            NoUMLDetectedError: If no UML elements detected
            ValueError: If rate limit exceeded
        """
        # Check if required OCR libraries are available
        if not CV2_AVAILABLE:
            logger.error("Image processing attempted but OpenCV (cv2) not available")
            raise OCRLibrariesUnavailableError(
                "Image processing is temporarily unavailable. "
                "Required system libraries (OpenCV, Tesseract) are not installed. "
                "Please contact the system administrator or try again later."
            )
        
        start_time = time.time()

        is_valid, error = self.validator.validate_image(base64_image)
        if not is_valid:
            raise InvalidImageError(error)

        cache_key = {
            "method": "process_image",
            "image_hash": hashlib.md5(base64_image.encode()).hexdigest(),
        }

        if use_cache:
            cached_result = CacheService.get(cache_key)
            if cached_result:
                logger.info("Returning cached image processing result")
                return cached_result

        if session_id:
            allowed, retry_after = RateLimiter.check_rate_limit(
                session_id,
                "process_image",
                RATE_LIMIT_IMAGES,
                RATE_LIMIT_WINDOW,
            )
            if not allowed:
                raise ValueError(
                    f"Image processing rate limit exceeded. Retry after {retry_after}s"
                )

        pil_image = self.validator.decode_and_load(base64_image)
        image_array = self._pil_to_numpy(pil_image)

        detected_boxes = self.yolo_detector.detect_class_boxes(image_array)
        logger.info(f"Detected {len(detected_boxes)} potential class boxes")

        preprocessed = self.ocr_engine.preprocess_image(image_array)

        text = self.ocr_engine.extract_text(preprocessed)
        logger.info(f"Extracted {len(text)} characters of text")

        text_boxes = self.ocr_engine.extract_with_boxes(preprocessed)

        elements = self.uml_parser.parse_text_to_elements(text, text_boxes)

        nodes = self.position_calculator.calculate_positions(
            elements["nodes"], detected_boxes
        )

        nodes = self.position_calculator.prevent_overlaps(nodes)

        edges = elements["edges"]

        processing_time_ms = int((time.time() - start_time) * 1000)

        result = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "classes_extracted": len(nodes),
                "relationships_extracted": len(edges),
                "processing_time_ms": processing_time_ms,
                "confidence": self._calculate_confidence(
                    text_boxes, detected_boxes
                ),
                "method": "local_ocr",
                "ocr_engines": self._get_available_engines(),
            },
        }

        if merge_with_existing and existing_diagram:
            result = self._merge_with_existing(result, existing_diagram)

        if use_cache:
            CacheService.set(cache_key, result, ttl=CACHE_TTL_IMAGES)

        logger.info(
            f"Image processed: {len(nodes)} classes, {len(edges)} relationships, {processing_time_ms}ms"
        )

        return result

    def _pil_to_numpy(self, pil_image: Image.Image):
        """Convert PIL Image to numpy array for OpenCV."""
        if not CV2_AVAILABLE:
            raise OCRFailedError("OpenCV (cv2) not available")

        rgb_image = pil_image.convert("RGB")
        numpy_image = np.array(rgb_image)
        bgr_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        return bgr_image

    def _calculate_confidence(
        self, text_boxes: list, detected_boxes: list
    ) -> float:
        """
        Calculate overall confidence score.

        Args:
            text_boxes: OCR text boxes with confidence
            detected_boxes: YOLO detected boxes with confidence

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not text_boxes and not detected_boxes:
            return 0.0

        text_confidence = (
            sum(box.get("confidence", 0) for box in text_boxes)
            / len(text_boxes)
            if text_boxes
            else 0.0
        )

        detection_confidence = (
            sum(box.get("confidence", 0) for box in detected_boxes)
            / len(detected_boxes)
            if detected_boxes
            else 0.0
        )

        overall = (text_confidence + detection_confidence) / 2

        return round(overall, 2)

    def _get_available_engines(self) -> list:
        """Get list of available OCR engines."""
        engines = []
        if self.ocr_engine.tesseract_available:
            engines.append("tesseract")
        if self.ocr_engine.easyocr_available:
            engines.append("easyocr")
        if self.yolo_detector.yolo_available:
            engines.append("yolo")
        else:
            engines.append("opencv_contours")
        return engines

    def _merge_with_existing(
        self, new_data: Dict[str, Any], existing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge new diagram data with existing diagram.

        Args:
            new_data: Newly processed diagram
            existing_data: Existing diagram data

        Returns:
            Merged diagram data
        """
        existing_nodes = existing_data.get("nodes", [])
        existing_edges = existing_data.get("edges", [])

        new_nodes = new_data["nodes"]
        new_edges = new_data["edges"]

        existing_labels = {
            node.get("data", {}).get("label") for node in existing_nodes
        }

        merged_nodes = existing_nodes.copy()
        for node in new_nodes:
            label = node.get("data", {}).get("label")
            if label not in existing_labels:
                merged_nodes.append(node)
                logger.info(f"Added new class: {label}")

        merged_edges = existing_edges + new_edges

        return {
            "nodes": merged_nodes,
            "edges": merged_edges,
            "metadata": {
                **new_data["metadata"],
                "merged": True,
                "original_classes": len(existing_nodes),
                "new_classes": len(new_nodes),
                "total_classes": len(merged_nodes),
            },
        }
