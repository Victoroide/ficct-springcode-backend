"""Amazon Nova Pro Vision Service for UML Diagram Processing.

Processes UML diagram images using Amazon Nova Pro model via AWS Bedrock.
Cost-effective and reliable AWS-native solution.

Pricing:
    - Input: $0.80 per 1M tokens
    - Output: $3.20 per 1M tokens
    - Average cost per image: $0.001-0.003
"""

import base64
import io
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)

_nova_client = None
_cost_tracking = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "images_processed": 0
}


def get_nova_client():
    """
    Get singleton Nova Pro client instance.
    
    Uses boto3 AWS SDK configured for Bedrock.
    
    Returns:
        Bedrock runtime client or None if initialization fails
    """
    global _nova_client
    
    if _nova_client is None:
        try:
            _nova_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_DEFAULT_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            logger.info("Nova Pro client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Nova Pro client: {e}")
            return None
    
    return _nova_client


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


class AWSBedrockError(Exception):
    """Raised when AWS Bedrock API call fails."""
    pass


class NovaVisionService:
    """
    Amazon Nova Pro vision service for UML diagram processing.
    
    Features:
        - Fast processing (3-8 seconds per image)
        - No model downloads or heavy dependencies
        - Cost-effective ($0.001-0.003 per image)
        - High accuracy for UML diagrams
        - AWS-native reliability
    
    Example:
        service = NovaVisionService()
        result = service.process_uml_diagram(base64_image, session_id)
        print(result['nodes'])
    """
    
    MODEL_ID = "amazon.nova-pro-v1:0"
    
    MAX_FILE_SIZE = 20 * 1024 * 1024
    MIN_DIMENSION = 100
    MAX_DIMENSION = 4096
    ALLOWED_FORMATS = {'PNG', 'JPEG', 'JPG'}
    
    INPUT_COST_PER_1M_TOKENS = 0.80
    OUTPUT_COST_PER_1M_TOKENS = 3.20
    
    def __init__(self):
        """Initialize Nova Pro vision service."""
        self.client = get_nova_client()
        if not self.client:
            logger.warning("Nova Pro client not available - check AWS credentials")
    
    def validate_image(self, base64_image: str) -> Tuple[bytes, str]:
        """
        Validate image format, size, and dimensions.
        
        Args:
            base64_image: Base64 encoded image string
            
        Returns:
            Tuple of (image_bytes, format)
            
        Raises:
            ImageValidationError: If validation fails
        """
        try:
            if ',' in base64_image:
                base64_image = base64_image.split(',', 1)[1]
            
            image_data = base64.b64decode(base64_image)
            
            if len(image_data) > self.MAX_FILE_SIZE:
                raise ImageValidationError(
                    f"Image size {len(image_data)} bytes exceeds maximum {self.MAX_FILE_SIZE} bytes"
                )
            
            image = Image.open(io.BytesIO(image_data))
            
            if image.format not in self.ALLOWED_FORMATS:
                raise ImageValidationError(
                    f"Unsupported image format: {image.format}. Allowed: {', '.join(self.ALLOWED_FORMATS)}"
                )
            
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
            
            return image_data, image.format.lower()
            
        except Exception as e:
            if isinstance(e, ImageValidationError):
                raise
            raise ImageValidationError(f"Image validation failed: {str(e)}")
    
    def process_uml_diagram(
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
            Dict with nodes, edges, metadata, and cost_info
            
        Raises:
            ImageValidationError: If image validation fails
            AWSBedrockError: If API call fails
        """
        start_time = time.time()
        
        image_bytes, image_format = self.validate_image(base64_image)
        
        if not self.client:
            return self._empty_result("Nova Pro service not configured - missing AWS credentials")
        
        try:
            prompt = self._build_uml_extraction_prompt()
            
            logger.info(f"Calling Nova Pro API for session {session_id}")
            
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": image_format,
                                    "source": {
                                        "bytes": image_base64
                                    }
                                }
                            },
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "temperature": 0.2,
                    "max_new_tokens": 3000
                }
            }
            
            response = self.client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            
            content = response_body['output']['message']['content'][0]['text']
            
            usage = response_body.get('usage', {})
            input_tokens = usage.get('inputTokens', 0)
            output_tokens = usage.get('outputTokens', 0)
            
            cost_info = self._calculate_cost(input_tokens, output_tokens)
            
            result = self._parse_response(content)
            
            processing_time = time.time() - start_time
            
            result['metadata'] = {
                'processing_time_ms': int(processing_time * 1000),
                'model': self.MODEL_ID,
                'session_id': session_id,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'node_count': len(result.get('nodes', [])),
                'edge_count': len(result.get('edges', []))
            }
            
            result['cost_info'] = cost_info
            
            logger.info(f"Nova Pro processing completed in {processing_time:.2f}s: "
                       f"{result['metadata']['node_count']} nodes, "
                       f"{result['metadata']['edge_count']} edges, "
                       f"cost: ${cost_info['request_cost_usd']:.6f}")
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS Bedrock API error [{error_code}]: {error_message}")
            raise AWSBedrockError(f"Bedrock API error: {error_message}")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise AWSBedrockError("AWS credentials not configured")
            
        except Exception as e:
            logger.error(f"Nova Pro API error: {e}", exc_info=True)
            return self._empty_result(f"Image processing failed: {str(e)}")
    
    def _build_uml_extraction_prompt(self) -> str:
        """Build detailed prompt for UML diagram extraction."""
        return """Analyze this UML class diagram image and extract all elements in JSON format.

Extract the following information:

1. Classes: All class names visible in the diagram
2. Attributes: For each class, extract attributes with:
   - Name
   - Type (if visible, otherwise use 'String' as default)
   - Visibility: + (public), - (private), # (protected), ~ (package)
3. Methods: For each class, extract methods with:
   - Name
   - Parameters (if visible)
   - Return type (if visible, otherwise use 'void')
   - Visibility: + (public), - (private), # (protected), ~ (package)
4. Relationships: Extract all relationships between classes:
   - Association (simple line)
   - Aggregation (hollow diamond)
   - Composition (filled diamond)
   - Dependency (dashed arrow)
   - Inheritance (hollow arrow)
   - Implementation (dashed hollow arrow)
5. Multiplicities: Extract multiplicity labels (1, 0..1, 1..*, *, etc.)

Output Format (strict JSON):
```json
{
  "nodes": [
    {
      "id": "class-1",
      "type": "classNode",
      "position": {"x": 100, "y": 100},
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
      "id": "edge-1",
      "source": "class-1",
      "target": "class-2",
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

Important:
- Use descriptive unique IDs
- Position nodes in grid layout (x: multiples of 300, y: multiples of 200)
- Return ONLY valid JSON, no markdown code blocks
- If no classes found, return empty nodes and edges arrays"""
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse Nova Pro response into React Flow format.
        
        Args:
            content: API response content
            
        Returns:
            Dict with nodes and edges
        """
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            data = json.loads(content)
            
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])
            
            return {
                'nodes': nodes if isinstance(nodes, list) else [],
                'edges': edges if isinstance(edges, list) else []
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Nova Pro response: {e}", exc_info=True)
            logger.debug(f"Raw content: {content}")
            return self._empty_result("Failed to parse API response")
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        """
        Calculate cost for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict with cost breakdown
        """
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        total_cost = input_cost + output_cost
        
        global _cost_tracking
        _cost_tracking['total_input_tokens'] += input_tokens
        _cost_tracking['total_output_tokens'] += output_tokens
        _cost_tracking['total_cost_usd'] += total_cost
        _cost_tracking['images_processed'] += 1
        
        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_cost_usd': input_cost,
            'output_cost_usd': output_cost,
            'request_cost_usd': total_cost
        }
    
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
            },
            'cost_info': {
                'input_tokens': 0,
                'output_tokens': 0,
                'input_cost_usd': 0.0,
                'output_cost_usd': 0.0,
                'request_cost_usd': 0.0
            }
        }
    
    @staticmethod
    def get_cost_summary() -> Dict[str, Any]:
        """
        Get cumulative cost tracking summary.
        
        Returns:
            Dict with total costs and usage statistics
        """
        return {
            'total_input_tokens': _cost_tracking['total_input_tokens'],
            'total_output_tokens': _cost_tracking['total_output_tokens'],
            'total_tokens': _cost_tracking['total_input_tokens'] + _cost_tracking['total_output_tokens'],
            'total_cost_usd': _cost_tracking['total_cost_usd'],
            'images_processed': _cost_tracking['images_processed'],
            'average_cost_per_image': (
                _cost_tracking['total_cost_usd'] / _cost_tracking['images_processed']
                if _cost_tracking['images_processed'] > 0 else 0.0
            )
        }


_service_instance = None


def get_nova_vision_service() -> NovaVisionService:
    """
    Get singleton instance of NovaVisionService.
    
    Returns:
        Singleton NovaVisionService instance
    """
    global _service_instance
    if _service_instance is None:
        logger.info("Initializing NovaVisionService singleton...")
        _service_instance = NovaVisionService()
        logger.info("NovaVisionService singleton initialized successfully")
    return _service_instance
