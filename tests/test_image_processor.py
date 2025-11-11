"""
Tests for local OCR image processing pipeline.

Tests image validation, OCR extraction, UML parsing, and React Flow conversion.
"""

import base64
import pytest
from unittest.mock import Mock, patch, MagicMock
from apps.ai_assistant.services import (
    ImageValidator,
    ImageProcessorService,
    OCREngine,
    YOLODetector,
    UMLParser,
)
from apps.ai_assistant.services.image_validator import InvalidImageError


@pytest.fixture
def valid_png_base64():
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def sample_ocr_text():
    return """
User
----
- id : Long
- name : String
+ save() : void
+ delete() : void
"""


class TestImageValidation:
    
    def test_valid_png_image(self, valid_png_base64):
        validator = ImageValidator()
        is_valid, error = validator.validate_image(valid_png_base64)
        
        assert is_valid is True
        assert error == ""
    
    def test_invalid_base64(self):
        validator = ImageValidator()
        is_valid, error = validator.validate_image("not-valid-base64!!!")
        
        assert is_valid is False
        assert "base64" in error.lower() or "validation" in error.lower()
    
    def test_oversized_image(self):
        validator = ImageValidator()
        large_data = "A" * (21 * 1024 * 1024)
        
        is_valid, error = validator.validate_image(large_data)
        
        assert is_valid is False
        assert "20MB" in error or "size" in error.lower()
    
    def test_undersized_image(self):
        validator = ImageValidator()
        tiny_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        is_valid, error = validator.validate_image(tiny_image_base64)
        
        assert is_valid is False
        assert "dimension" in error.lower()


class TestOCRExtraction:
    
    @patch('apps.ai_assistant.services.ocr_engine.pytesseract')
    @patch('apps.ai_assistant.services.ocr_engine.Image')
    def test_tesseract_extraction(self, mock_image, mock_tesseract):
        mock_tesseract.image_to_string.return_value = "User\n- id : Long"
        
        engine = OCREngine()
        engine.tesseract_available = True
        
        mock_img_array = MagicMock()
        text = engine._extract_with_tesseract(mock_img_array)
        
        assert "User" in text
        assert "id" in text
    
    def test_attribute_parsing(self, sample_ocr_text):
        parser = UMLParser()
        
        match = parser.attribute_pattern.search("- id : Long")
        
        assert match is not None
        assert match.group(2) == "id"
        assert match.group(3) == "Long"
    
    def test_method_parsing(self, sample_ocr_text):
        parser = UMLParser()
        
        match = parser.method_pattern.search("+ save() : void")
        
        assert match is not None
        assert match.group(2) == "save"
        assert match.group(4) == "void"


class TestYOLODetection:
    """Test YOLO bounding box detection."""
    
    @patch('apps.ai_assistant.services.yolo_detector.cv2')
    def test_detect_rectangles(self, mock_cv2):
        """Test: Detect UML class boxes."""
        mock_cv2.findContours.return_value = ([], None)
        
        detector = YOLODetector()
        mock_image = MagicMock()
        
        boxes = detector.detect_class_boxes(mock_image)
        
        assert isinstance(boxes, list)
    
    @patch('apps.ai_assistant.services.yolo_detector.cv2')
    def test_detect_lines(self, mock_cv2):
        """Test: Detect relationship lines."""
        mock_cv2.HoughLinesP.return_value = None
        
        detector = YOLODetector()
        mock_image = MagicMock()
        
        lines = detector.detect_relationships(mock_image)
        
        assert isinstance(lines, list)


class TestReactFlowConversion:
    """Test full pipeline and React Flow format."""
    
    @patch.object(ImageProcessorService, '_pil_to_numpy')
    @patch.object(YOLODetector, 'detect_class_boxes')
    @patch.object(OCREngine, 'extract_text')
    @patch.object(OCREngine, 'extract_with_boxes')
    def test_full_pipeline(
        self,
        mock_extract_boxes,
        mock_extract_text,
        mock_detect_boxes,
        mock_pil_to_numpy,
        valid_png_base64
    ):
        """Test: Full image processing pipeline."""
        mock_extract_text.return_value = "User\n- id : Long\n+ save() : void"
        mock_extract_boxes.return_value = [
            {"text": "User", "bbox": [10, 10, 100, 50], "confidence": 0.95}
        ]
        mock_detect_boxes.return_value = [
            {"bbox": [10, 10, 100, 100], "confidence": 0.9, "type": "class"}
        ]
        mock_pil_to_numpy.return_value = MagicMock()
        
        processor = ImageProcessorService()
        
        result = processor.process_image(valid_png_base64, session_id="test")
        
        assert "nodes" in result
        assert "edges" in result
        assert "metadata" in result
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)
    
    def test_node_structure(self):
        """Test: Node structure matches React Flow schema."""
        parser = UMLParser()
        
        class_data = {
            "name": "User",
            "attributes": [{"id": "attr-1", "name": "id", "type": "Long", "visibility": "private", "isStatic": False, "isFinal": False}],
            "methods": [],
            "stereotypes": [],
            "is_abstract": False,
            "is_interface": False,
        }
        
        node = parser._create_node_from_class(class_data)
        
        assert "id" in node
        assert "type" in node
        assert "data" in node
        assert node["data"]["label"] == "User"
        assert len(node["data"]["attributes"]) == 1
    
    def test_edge_relationship_types(self):
        """Test: Edge relationship types are correct."""
        parser = UMLParser()
        
        classes = [
            {"name": "User", "attributes": [{"name": "order", "type": "Order"}], "methods": []},
            {"name": "Order", "attributes": [], "methods": []},
        ]
        
        edges = parser._infer_relationships(classes)
        
        if edges:
            assert "relationshipType" in edges[0]["data"]
            assert edges[0]["data"]["relationshipType"] in ["ASSOCIATION", "AGGREGATION", "COMPOSITION"]


class TestGracefulDegradation:
    """Test fallback behavior when OCR libs not installed."""
    
    def test_no_tesseract_fallback(self):
        """Test: Gracefully handle missing Tesseract."""
        engine = OCREngine()
        engine.tesseract_available = False
        engine.easyocr_available = False
        
        mock_image = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            engine.extract_text(mock_image)
        
        assert "OCR" in str(exc_info.value) or "available" in str(exc_info.value).lower()
    
    def test_error_messages(self, valid_png_base64):
        """Test: Clear error messages returned."""
        validator = ImageValidator()
        
        is_valid, error = validator.validate_image("invalid-data")
        
        assert is_valid is False
        assert len(error) > 0
        assert isinstance(error, str)
