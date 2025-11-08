"""Qwen3-VL Vision Service for UML Diagram Processing.

Processes UML diagram images using Alibaba Cloud's Qwen3-VL model via DashScope API.
Cost-effective alternative to local OCR with better accuracy and performance.

Pricing:
- Input: $0.05 per 1M tokens
- Output: $0.40 per 1M tokens
- Average cost per image: ~$0.0014 (0.14 cents)
"""

import base64
import io
import json
import logging
import time
from typing import Any, Dict, Optional

from openai import OpenAI
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)

# Singleton client instance
_qwen_client = None


def get_qwen_client() -> Optional[OpenAI]:
    """
    Get singleton Qwen3-VL client instance.
    
    Uses OpenAI SDK configured for DashScope endpoint.
    """
    global _qwen_client
    
    if _qwen_client is None:
        api_key = settings.DASHSCOPE_API_KEY
        if not api_key:
            logger.error("DASHSCOPE_API_KEY not configured")
            return None
            
        try:
            _qwen_client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            logger.info("Qwen3-VL client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qwen3-VL client: {e}")
            return None
    
    return _qwen_client


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


class QwenVisionService:
    """
    Qwen3-VL Vision service for UML diagram processing.
    
    Features:
    - Fast processing (2-5 seconds per image)
    - No model downloads or heavy dependencies
    - Cost-effective ($0.0014 per image)
    - High accuracy for UML diagrams
    
    Example:
        >>> service = QwenVisionService()
        >>> result = service.process_uml_diagram_image(base64_image, session_id)
        >>> print(result['nodes'])  # React Flow nodes
    """
    
    # Image validation constraints
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    MIN_DIMENSION = 100
    MAX_DIMENSION = 4096
    ALLOWED_FORMATS = {'PNG', 'JPEG', 'JPG', 'GIF', 'BMP', 'WEBP'}
    
    def __init__(self):
        """Initialize Qwen3-VL vision service."""
        self.client = get_qwen_client()
        if not self.client:
            logger.warning("Qwen3-VL client not available - check DASHSCOPE_API_KEY")
    
    def validate_image(self, base64_image: str) -> None:
        """
        Validate image format, size, and dimensions.
        
        Args:
            base64_image: Base64 encoded image string
            
        Raises:
            ImageValidationError: If validation fails
        """
        try:
            # Remove data URL prefix if present
            if ',' in base64_image:
                base64_image = base64_image.split(',', 1)[1]
            
            # Decode base64
            image_data = base64.b64decode(base64_image)
            
            # Check file size
            if len(image_data) > self.MAX_FILE_SIZE:
                raise ImageValidationError(
                    f"Image size ({len(image_data)} bytes) exceeds maximum ({self.MAX_FILE_SIZE} bytes)"
                )
            
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Check format
            if image.format not in self.ALLOWED_FORMATS:
                raise ImageValidationError(
                    f"Unsupported image format: {image.format}. Allowed: {', '.join(self.ALLOWED_FORMATS)}"
                )
            
            # Check dimensions
            width, height = image.size
            if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION:
                raise ImageValidationError(
                    f"Image too small ({width}x{height}). Minimum: {self.MIN_DIMENSION}x{self.MIN_DIMENSION}"
                )
            
            if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                raise ImageValidationError(
                    f"Image too large ({width}x{height}). Maximum: {self.MAX_DIMENSION}x{self.MAX_DIMENSION}"
                )
            
            logger.info(f"Image validation passed: {image.format} {width}x{height} ({len(image_data)} bytes)")
            
        except Exception as e:
            if isinstance(e, ImageValidationError):
                raise
            raise ImageValidationError(f"Image validation failed: {str(e)}")
    
    def process_uml_diagram_image(
        self,
        base64_image: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process UML diagram image and extract elements.
        
        Args:
            base64_image: Base64 encoded image
            session_id: Optional session identifier
            
        Returns:
            Dict with nodes, edges, and metadata in React Flow format
            
        Raises:
            ImageValidationError: If image validation fails
            Exception: If API call fails
        """
        start_time = time.time()
        
        # Validate image first
        self.validate_image(base64_image)
        
        # Check client availability
        if not self.client:
            return self._empty_result("Qwen3-VL service not configured - missing DASHSCOPE_API_KEY")
        
        try:
            # Prepare image for API
            if ',' in base64_image:
                base64_image = base64_image.split(',', 1)[1]
            
            # Build prompt
            prompt = self._build_uml_extraction_prompt()
            
            # Call Qwen3-VL API
            logger.info(f"Calling Qwen3-VL API for session {session_id}")
            
            response = self.client.chat.completions.create(
                model="qwen-vl-max",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                temperature=0.2,  # Low for accuracy
                max_tokens=8000,
                timeout=30.0
            )
            
            # Extract response
            content = response.choices[0].message.content
            
            # Parse JSON response
            result = self._parse_response(content)
            
            processing_time = time.time() - start_time
            
            # Add metadata
            result['metadata'] = {
                'processing_time_ms': int(processing_time * 1000),
                'model': 'qwen-vl-max',
                'session_id': session_id,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'node_count': len(result.get('nodes', [])),
                'edge_count': len(result.get('edges', []))
            }
            
            logger.info(f"Qwen3-VL processing completed in {processing_time:.2f}s: "
                       f"{result['metadata']['node_count']} nodes, "
                       f"{result['metadata']['edge_count']} edges")
            
            return result
            
        except Exception as e:
            logger.error(f"Qwen3-VL API error: {e}", exc_info=True)
            return self._empty_result(f"Image processing failed: {str(e)}")
    
    def _build_uml_extraction_prompt(self) -> str:
        """Build detailed prompt for UML diagram extraction."""
        return """Analyze this UML class diagram image and extract all elements in JSON format.

Extract the following information:
1. **Classes**: All class names visible in the diagram
2. **Attributes**: For each class, extract attributes with:
   - Name
   - Type (if visible)
   - Visibility: + (public), - (private), # (protected), ~ (package)
3. **Methods**: For each class, extract methods with:
   - Name
   - Parameters (if visible)
   - Return type (if visible)
   - Visibility: + (public), - (private), # (protected), ~ (package)
4. **Relationships**: Extract all relationships between classes:
   - Association (simple line)
   - Aggregation (hollow diamond)
   - Composition (filled diamond)
   - Dependency (dashed arrow)
   - Inheritance/Generalization (hollow arrow)
   - Implementation (dashed hollow arrow)
5. **Multiplicities**: Extract multiplicity labels (1, 0..1, 1..*, *, etc.)

**Output Format** (strict JSON):
```json
{
  "nodes": [
    {
      "id": "unique-id",
      "type": "classNode",
      "position": {"x": 0, "y": 0},
      "data": {
        "label": "ClassName",
        "attributes": [
          {"name": "attributeName", "type": "String", "visibility": "private"}
        ],
        "methods": [
          {"name": "methodName", "parameters": "param: Type", "returnType": "void", "visibility": "public"}
        ]
      }
    }
  ],
  "edges": [
    {
      "id": "edge-id",
      "source": "source-node-id",
      "target": "target-node-id",
      "type": "association",
      "data": {
        "relationshipType": "Association",
        "sourceMultiplicity": "1",
        "targetMultiplicity": "*"
      }
    }
  ]
}
```

**Important**:
- Use descriptive unique IDs for nodes and edges
- Position nodes in a grid layout (increment x by 300, y by 200)
- If information is unclear, use reasonable defaults
- Return ONLY valid JSON, no markdown code blocks
- If no classes found, return empty nodes and edges arrays"""
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse Qwen3-VL response into React Flow format.
        
        Args:
            content: API response content
            
        Returns:
            Dict with nodes and edges
        """
        try:
            # Try to extract JSON from markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            # Parse JSON
            data = json.loads(content)
            
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])
            
            # Ensure proper structure
            return {
                'nodes': nodes if isinstance(nodes, list) else [],
                'edges': edges if isinstance(edges, list) else []
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Qwen3-VL response: {e}", exc_info=True)
            logger.debug(f"Raw content: {content}")
            return self._empty_result("Failed to parse API response")
    
    def _empty_result(self, error_message: str) -> Dict[str, Any]:
        """Return empty result with error message."""
        return {
            'nodes': [],
            'edges': [],
            'metadata': {
                'error': error_message,
                'processing_time_ms': 0,
                'node_count': 0,
                'edge_count': 0
            }
        }
