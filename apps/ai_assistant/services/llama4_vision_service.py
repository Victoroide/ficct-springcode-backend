"""Llama 4 Maverick Vision Service for UML Diagram Processing.

Processes UML diagram images using Llama 4 Maverick 17B via AWS Bedrock.
70% cheaper than Nova Pro with excellent multimodal understanding.

Pricing:
    - Input: $0.24 per 1M tokens
    - Output: $0.97 per 1M tokens
    - Average cost per image: $0.003-0.004 (70% cheaper than Nova Pro)
"""

import base64
import io
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)

_llama4_vision_client = None
_cost_tracking = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "images_processed": 0
}


def get_llama4_vision_client():
    """
    Get singleton Llama 4 Maverick vision client instance.
    
    Uses boto3 AWS SDK configured for Bedrock.
    
    Returns:
        Bedrock runtime client or None if initialization fails
    """
    global _llama4_vision_client
    
    if _llama4_vision_client is None:
        try:
            _llama4_vision_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_DEFAULT_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            logger.info("Llama 4 Maverick vision client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Llama 4 vision client: {e}")
            return None
    
    return _llama4_vision_client


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


class AWSBedrockError(Exception):
    """Raised when AWS Bedrock API call fails."""
    pass


class Llama4VisionService:
    """
    Llama 4 Maverick multimodal vision service for UML diagram processing.
    
    Features:
        - 70% cheaper than Nova Pro
        - 1M token context window
        - Early fusion multimodal architecture
        - Excellent diagram understanding
        - Cost-effective at scale
    
    Example:
        service = Llama4VisionService()
        result = service.process_uml_diagram(base64_image, session_id)
        print(result['nodes'])
    """
    
    MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"
    
    MAX_FILE_SIZE = 20 * 1024 * 1024
    MIN_DIMENSION = 100
    MAX_DIMENSION = 4096
    ALLOWED_FORMATS = {'PNG', 'JPEG', 'JPG'}
    
    INPUT_COST_PER_1M_TOKENS = 0.24
    OUTPUT_COST_PER_1M_TOKENS = 0.97
    
    def __init__(self):
        """Initialize Llama 4 Maverick vision service."""
        self.client = get_llama4_vision_client()
        if not self.client:
            logger.warning("Llama 4 vision client not available - check AWS credentials")
    
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
        session_id: Optional[str] = None,
        existing_diagram: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process UML diagram image and extract elements using Llama 4 Maverick.
        
        Args:
            base64_image: Base64 encoded image
            session_id: Optional session identifier
            existing_diagram: Optional existing diagram context for merging
            
        Returns:
            Dict with nodes, edges, metadata, and cost_info
            
        Raises:
            ImageValidationError: If image validation fails
            AWSBedrockError: If API call fails
        """
        start_time = time.time()
        
        image_bytes, image_format = self.validate_image(base64_image)
        
        if not self.client:
            return self._empty_result("Llama 4 vision service not configured - missing AWS credentials")
        
        try:
            text_prompt = self._build_uml_extraction_prompt(existing_diagram)
            
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            formatted_prompt = self._format_multimodal_prompt(text_prompt, image_base64)
            
            logger.info(f"Calling Llama 4 Maverick vision API for session {session_id}")
            
            request_body = {
                "prompt": formatted_prompt,
                "max_gen_len": 4096,
                "temperature": 0.2,
                "top_p": 0.9
            }
            
            response = self.client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            
            generation = response_body.get('generation', '')
            prompt_tokens = response_body.get('prompt_token_count', 0)
            completion_tokens = response_body.get('generation_token_count', 0)
            stop_reason = response_body.get('stop_reason', 'unknown')
            
            cost_info = self._calculate_cost(prompt_tokens, completion_tokens)
            
            result = self._parse_response(generation)
            
            processing_time = time.time() - start_time
            
            result['metadata'] = {
                'processing_time_ms': int(processing_time * 1000),
                'model': 'llama4-maverick',
                'session_id': session_id,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'node_count': len(result.get('nodes', [])),
                'edge_count': len(result.get('edges', [])),
                'input_tokens': prompt_tokens,
                'output_tokens': completion_tokens,
                'stop_reason': stop_reason
            }
            
            result['cost_info'] = cost_info
            
            logger.info(f"Llama 4 vision processing completed in {processing_time:.2f}s: "
                       f"{result['metadata']['node_count']} nodes, "
                       f"{result['metadata']['edge_count']} edges, "
                       f"cost: ${cost_info['request_cost_usd']:.6f}")
            
            global _cost_tracking
            _cost_tracking['total_input_tokens'] += prompt_tokens
            _cost_tracking['total_output_tokens'] += completion_tokens
            _cost_tracking['total_cost_usd'] += cost_info['request_cost_usd']
            _cost_tracking['images_processed'] += 1
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"Llama 4 vision API error: {error_code} - {error_message}", exc_info=True)
            
            raise AWSBedrockError(f"Llama 4 vision processing failed: {error_code} - {error_message}")
            
        except Exception as e:
            logger.error(f"Unexpected error in Llama 4 vision processing: {e}", exc_info=True)
            raise AWSBedrockError(f"Llama 4 vision processing failed: {str(e)}")
    
    def _format_multimodal_prompt(self, text_prompt: str, image_base64: str) -> str:
        """
        Format prompt in Llama 4 Maverick multimodal format.
        
        Llama 4 requires special structure for image + text:
        - <|begin_of_text|> at start
        - <image>base64</image> for image data
        - User header tags
        - Text prompt after image
        - End of turn marker
        
        Args:
            text_prompt: The text instructions
            image_base64: Base64 encoded image
            
        Returns:
            Formatted multimodal prompt
        """
        formatted = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
        formatted += f"<image>{image_base64}</image>\n\n"
        formatted += text_prompt
        formatted += "\n<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n"
        
        return formatted
    
    def _build_uml_extraction_prompt(self, existing_diagram: Optional[Dict] = None) -> str:
        """
        Build comprehensive UML extraction prompt.
        
        Args:
            existing_diagram: Optional existing diagram for context
            
        Returns:
            Formatted prompt string
        """
        prompt = """You are a UML diagram analyzer. Extract ALL information from this class diagram image.

EXTRACTION REQUIREMENTS:

1. CLASSES:
   - Class name (exact spelling)
   - All attributes with: name, type, visibility (+/-/# for public/private/protected)
   - All methods with: name, parameters, return type, visibility
   - Stereotypes (<<interface>>, <<abstract>>, etc.)
   - Abstract/Interface markers

2. RELATIONSHIPS:
   - Type: ASSOCIATION, AGGREGATION, COMPOSITION, INHERITANCE, REALIZATION, DEPENDENCY
   - Source and target class names (exact)
   - Multiplicities on both ends (1, *, 0..1, 1..*, etc.)
   - Relationship labels if present

3. POSITIONS:
   - Approximate x, y coordinates for layout
   - Preserve relative positioning

4. SPECIAL ELEMENTS:
   - Enums with values
   - Interfaces (marked <<interface>>)
   - Abstract classes
   - Notes/comments

OUTPUT FORMAT (CRITICAL):

Return ONLY valid JSON in this EXACT structure:

{
  "nodes": [
    {
      "id": "class-unique-id",
      "data": {
        "label": "ClassName",
        "nodeType": "class",
        "isAbstract": false,
        "attributes": [
          {
            "name": "attributeName",
            "type": "String",
            "visibility": "private",
            "isStatic": false,
            "isFinal": false
          }
        ],
        "methods": [
          {
            "name": "methodName",
            "returnType": "void",
            "visibility": "public",
            "parameters": [],
            "isStatic": false,
            "isAbstract": false
          }
        ]
      },
      "position": {"x": 100, "y": 100},
      "type": "class"
    }
  ],
  "edges": [
    {
      "id": "edge-unique-id",
      "source": "source-class-id",
      "target": "target-class-id",
      "type": "umlRelationship",
      "data": {
        "relationshipType": "ASSOCIATION",
        "sourceMultiplicity": "1",
        "targetMultiplicity": "*",
        "label": ""
      }
    }
  ],
  "success": true,
  "message": "Extracted X classes and Y relationships"
}

VISIBILITY MAPPING:
- + (public) → "public"
- - (private) → "private"
- # (protected) → "protected"
- ~ (package) → "package"

RELATIONSHIP TYPE DETECTION:
- Solid line with arrow → INHERITANCE
- Dashed line with arrow → REALIZATION
- Solid line → ASSOCIATION
- Diamond (filled) → COMPOSITION
- Diamond (empty) → AGGREGATION
- Dashed line → DEPENDENCY

CRITICAL RULES:
1. Return ONLY the JSON object
2. No markdown, no code blocks, no explanations
3. Use exact class names from diagram
4. Generate unique IDs for all elements
5. If diagram is unclear, do your best and set success: true"""

        if existing_diagram:
            nodes = existing_diagram.get('nodes', [])
            if nodes:
                prompt += "\n\nEXISTING DIAGRAM CONTEXT:\n"
                prompt += "The following classes already exist. Merge intelligently:\n"
                for node in nodes:
                    label = node.get('data', {}).get('label', 'Unknown')
                    node_id = node.get('id', '')
                    prompt += f"- {label} (ID: {node_id})\n"
                prompt += "\nFor classes that exist, preserve their IDs. For new classes, generate new IDs.\n"
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Llama 4 vision response and extract JSON.
        
        Uses multiple extraction strategies to handle various formats.
        
        Args:
            response_text: Raw response text from Llama 4
            
        Returns:
            Parsed result with nodes and edges
        """
        if not response_text or not response_text.strip():
            return self._empty_result("Empty response from Llama 4")
        
        strategies = [
            self._try_direct_parse,
            self._try_markdown_extraction,
            self._try_brace_counting,
            self._try_json_block_extraction
        ]
        
        for strategy in strategies:
            try:
                result = strategy(response_text)
                if result and 'nodes' in result:
                    return result
            except Exception as e:
                logger.debug(f"Strategy {strategy.__name__} failed: {e}")
                continue
        
        logger.error(f"All parsing strategies failed for response: {response_text[:500]}")
        return self._empty_result("Could not parse Llama 4 response")
    
    def _try_direct_parse(self, text: str) -> Optional[Dict]:
        """Try parsing text directly as JSON."""
        return json.loads(text.strip())
    
    def _try_markdown_extraction(self, text: str) -> Optional[Dict]:
        """Extract JSON from markdown code blocks."""
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return None
    
    def _try_brace_counting(self, text: str) -> Optional[Dict]:
        """Extract JSON by finding balanced braces."""
        first_brace = text.find('{')
        if first_brace == -1:
            return None
        
        brace_count = 0
        for i in range(first_brace, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[first_brace:i+1]
                    return json.loads(json_str)
        
        return None
    
    def _try_json_block_extraction(self, text: str) -> Optional[Dict]:
        """Look for JSON block patterns with nodes/edges."""
        patterns = [
            r'\{[^{}]*"nodes"[^{}]*"edges"[^{}]*\}',
            r'\{.*?"nodes".*?\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    continue
        
        return None
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
        """
        Calculate cost for Llama 4 vision API usage.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Dict with cost breakdown
        """
        input_cost = (prompt_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        total_cost = input_cost + output_cost
        
        return {
            'input_tokens': prompt_tokens,
            'output_tokens': completion_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'request_cost_usd': round(total_cost, 6),
            'model': 'llama4-maverick'
        }
    
    def _empty_result(self, message: str) -> Dict[str, Any]:
        """
        Return empty result with error message.
        
        Args:
            message: Error message
            
        Returns:
            Empty result dictionary
        """
        return {
            'nodes': [],
            'edges': [],
            'success': False,
            'message': message,
            'metadata': {
                'node_count': 0,
                'edge_count': 0
            },
            'cost_info': {
                'request_cost_usd': 0.0
            }
        }
    
    @staticmethod
    def get_cost_tracking() -> Dict[str, Any]:
        """
        Get cumulative cost tracking statistics.
        
        Returns:
            Dict with total tokens, cost, and images processed
        """
        return _cost_tracking.copy()


def get_nova_vision_service():
    """
    Get NovaVisionService instance for compatibility.
    
    This function maintains API compatibility with existing code.
    
    Returns:
        Llama4VisionService instance
    """
    return Llama4VisionService()
