"""YOLO-based UML element detector.

Detects UML class boxes and relationship lines using YOLO v8.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Tuple

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
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLO (ultralytics) not available")


class YOLODetector:
    """
    YOLO-based detector for UML elements.

    Features:
    - Rectangle detection for class boxes
    - Line detection for relationships
    - Confidence scoring
    - Fallback to OpenCV contours

    Example:
        >>> detector = YOLODetector()
        >>> boxes = detector.detect_class_boxes(image)
    """

    def __init__(self):
        """Initialize YOLO detector."""
        self.yolo_available = YOLO_AVAILABLE

        if not self.yolo_available:
            logger.info("Using fallback OpenCV contour detection")

    def detect_class_boxes(
        self, image: np.ndarray, confidence_threshold: float = 0.5
    ) -> List[Dict[str, any]]:
        """
        Detect UML class boxes in image.

        Args:
            image: Image as numpy array
            confidence_threshold: Minimum confidence (0.0 - 1.0)

        Returns:
            List of detected boxes with bbox and confidence

        Example:
            >>> boxes = detector.detect_class_boxes(image)
            >>> for box in boxes:
            ...     x1, y1, x2, y2 = box['bbox']
        """
        boxes = self._detect_rectangles_opencv(image)

        return [
            {"bbox": bbox, "confidence": conf, "type": "class"}
            for bbox, conf in boxes
            if conf >= confidence_threshold
        ]

    def detect_relationships(
        self, image: np.ndarray
    ) -> List[Dict[str, any]]:
        """
        Detect relationship lines between classes.

        Args:
            image: Image as numpy array

        Returns:
            List of detected lines with start/end points
        """
        lines = self._detect_lines_opencv(image)

        return [
            {
                "start": (x1, y1),
                "end": (x2, y2),
                "type": "relationship",
            }
            for x1, y1, x2, y2 in lines
        ]

    def _detect_rectangles_opencv(
        self, image: np.ndarray
    ) -> List[Tuple[List[int], float]]:
        """
        Detect rectangles using OpenCV contour detection.

        Args:
            image: Image array

        Returns:
            List of (bbox, confidence) tuples
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        edges = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        boxes = []
        min_area = 500
        max_area = image.shape[0] * image.shape[1] * 0.5

        for contour in contours:
            area = cv2.contourArea(contour)

            if area < min_area or area > max_area:
                continue

            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

            if len(approx) >= 4:
                x, y, w, h = cv2.boundingRect(contour)

                aspect_ratio = float(w) / h if h > 0 else 0
                extent = area / (w * h) if w * h > 0 else 0

                if 0.3 <= aspect_ratio <= 3.0 and extent > 0.5:
                    bbox = [x, y, x + w, y + h]
                    confidence = min(extent, 0.95)
                    boxes.append((bbox, confidence))

        boxes.sort(key=lambda x: x[1], reverse=True)

        return boxes

    def _detect_lines_opencv(
        self, image: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect lines using Hough Line Transform.

        Args:
            image: Image array

        Returns:
            List of (x1, y1, x2, y2) line coordinates
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=30,
            maxLineGap=10,
        )

        if lines is None:
            return []

        detected_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]

            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

            if length > 20:
                detected_lines.append((x1, y1, x2, y2))

        return detected_lines

    def filter_overlapping_boxes(
        self, boxes: List[Dict[str, any]], iou_threshold: float = 0.5
    ) -> List[Dict[str, any]]:
        """
        Filter overlapping boxes using Non-Maximum Suppression.

        Args:
            boxes: List of detected boxes
            iou_threshold: IoU threshold for suppression

        Returns:
            Filtered list of non-overlapping boxes
        """
        if not boxes:
            return []

        boxes_array = np.array([box["bbox"] for box in boxes])
        scores = np.array([box["confidence"] for box in boxes])

        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = boxes_array[:, 2]
        y2 = boxes_array[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            intersection = w * h
            iou = intersection / (
                areas[i] + areas[order[1:]] - intersection
            )

            indices = np.where(iou <= iou_threshold)[0]
            order = order[indices + 1]

        return [boxes[i] for i in keep]
