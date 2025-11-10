"""Amazon Nova Pro Command Service for UML Diagram Generation.

Processes natural language commands using Amazon Nova Pro model via AWS Bedrock.
Fast, reliable, and cost-effective alternative to o4-mini for command processing.

Pricing:
    - Input: $0.80 per 1M tokens
    - Output: $3.20 per 1M tokens
    - Average cost per command: $0.0005-0.002
    - Response time: 3-8 seconds (vs 20-30s for o4-mini)
"""

import json
import logging
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings

logger = logging.getLogger(__name__)

_nova_command_client = None
_cost_tracking = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "commands_processed": 0
}


def get_nova_command_client():
    """
    Get singleton Nova Pro client instance for command processing.
    
    Uses boto3 AWS SDK configured for Bedrock.
    
    Returns:
        Bedrock runtime client or None if initialization fails
    """
    global _nova_command_client
    
    if _nova_command_client is None:
        try:
            _nova_command_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_DEFAULT_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            logger.info("Nova Pro command client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Nova Pro command client: {e}")
            return None
    
    return _nova_command_client


class AWSBedrockError(Exception):
    """Raised when AWS Bedrock API call fails."""
    pass


class NovaCommandService:
    """
    Amazon Nova Pro command service for UML diagram generation.
    
    Features:
        - Fast processing (3-8 seconds vs 20-30s for o4-mini)
        - Direct JSON output (no reasoning token waste)
        - Cost-effective ($0.0005-0.002 per command)
        - Reliable responses (no timeout issues)
        - AWS-native reliability
    
    Example:
        service = NovaCommandService()
        result = service.process_command("crea clase User con id y nombre")
        print(result['elements'])
    """
    
    MODEL_ID = "amazon.nova-pro-v1:0"
    
    INPUT_COST_PER_1M_TOKENS = 0.80
    OUTPUT_COST_PER_1M_TOKENS = 3.20
    
    def __init__(self):
        """Initialize Nova Pro command service."""
        self.client = get_nova_command_client()
        if not self.client:
            logger.warning("Nova Pro command client not available - check AWS credentials")
        self.logger = logging.getLogger(__name__)
    
    def process_command(
        self,
        command: str,
        diagram_id: Optional[str] = None,
        current_diagram_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process natural language command and generate UML elements.
        
        Args:
            command: Natural language command in Spanish/English/French
            diagram_id: Optional diagram ID for context
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            Dict with action, elements, confidence, interpretation, and metadata
            
        Raises:
            AWSBedrockError: If API call fails
        """
        start_time = time.time()
        
        if not self.client:
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Nova Pro service not configured',
                'error': 'AWS Bedrock service unavailable. Check AWS credentials.',
                'suggestion': 'Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in settings.'
            }
        
        try:
            prompt = self._build_command_prompt(command, current_diagram_data)
            
            logger.info(f"Calling Nova Pro API for command: {command[:100]}")
            
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "temperature": 0.7,
                    "max_new_tokens": 4000
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
            
            processing_time = time.time() - start_time
            
            result = self._parse_response(content)
            
            result['metadata'] = {
                'model': 'nova-pro',
                'model_full_name': self.MODEL_ID,
                'response_time': round(processing_time, 2),
                'cost_estimate': round(cost_info['request_cost_usd'], 6),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.info(f"Nova Pro command processing completed in {processing_time:.2f}s: "
                       f"action={result.get('action')}, "
                       f"elements={len(result.get('elements', []))}, "
                       f"cost=${cost_info['request_cost_usd']:.6f}")
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS Bedrock API error [{error_code}]: {error_message}")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'AWS Bedrock API error',
                'error': f'Bedrock API error: {error_message}',
                'suggestion': 'Please try again. If the problem persists, contact support.'
            }
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'AWS credentials not configured',
                'error': 'AWS credentials missing',
                'suggestion': 'Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.'
            }
            
        except Exception as e:
            logger.error(f"Nova Pro command API error: {e}", exc_info=True)
            processing_time = time.time() - start_time
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Command processing failed: {str(e)}',
                'error': str(e),
                'suggestion': 'Please try rephrasing your command or contact support.',
                'metadata': {
                    'model': 'nova-pro',
                    'response_time': round(processing_time, 2),
                    'error_occurred': True
                }
            }
    
    def _build_command_prompt(self, command: str, current_diagram_data: Optional[Dict] = None) -> str:
        """
        Build comprehensive prompt for command processing.
        
        Args:
            command: Natural language command
            current_diagram_data: Optional existing diagram data
            
        Returns:
            Formatted prompt string
        """
        import time
        timestamp_ms = int(time.time() * 1000)
        
        base_prompt = f"""You are a UML diagram generator that converts natural language to EXACT React Flow JSON.

Your ONLY task is to generate VALID React Flow node/edge JSON structures. NEVER return empty elements arrays.

CRITICAL RULES:
1. ALWAYS generate REAL elements - NEVER return empty arrays
2. Use unique IDs with timestamp: class-{timestamp_ms}, attr-{timestamp_ms}
3. Position new elements intelligently to avoid overlaps
4. Support Spanish, English, French commands
5. ALWAYS populate elements array when command is clear

TYPE MAPPINGS:
- id, codigo, code → Long
- nombre, name, apellido, lastname → String
- edad, age → Integer
- precio, price, costo, cost → Double
- activo, active, enabled → Boolean
- fecha, date, createdAt → Date
- descripcion, description, texto, text → String
- cantidad, quantity, stock → Integer
- email, correo → String
- telefono, phone → String
- direccion, address → String
- sexo, gender → String

EXACT JSON STRUCTURE:
{{
  "action": "create_class",
  "elements": [
    {{
      "type": "node",
      "data": {{
        "id": "class-{timestamp_ms}",
        "data": {{
          "label": "ClassName",
          "attributes": [
            {{"id": "attr-{timestamp_ms}-1", "name": "attributeName", "type": "String", "visibility": "private", "isStatic": false, "isFinal": false}}
          ],
          "methods": [],
          "nodeType": "class",
          "isAbstract": false
        }},
        "type": "class",
        "position": {{"x": 400, "y": 200}},
        "width": 180,
        "height": 140
      }}
    }}
  ],
  "confidence": 0.95,
  "interpretation": "Created ClassName with specified attributes"
}}

POSITIONING STRATEGY:
- First class: {{"x": 400, "y": 200}}
- Second class: {{"x": 700, "y": 200}}
- Third class: {{"x": 400, "y": 450}}
- Fourth class: {{"x": 700, "y": 450}}
- Avoid overlaps with existing nodes

RELATIONSHIP STRUCTURE:
{{
  "type": "edge",
  "data": {{
    "id": "edge-{timestamp_ms}",
    "source": "class-source-id",
    "target": "class-target-id",
    "type": "umlRelationship",
    "data": {{
      "relationshipType": "ASSOCIATION",
      "sourceMultiplicity": "1",
      "targetMultiplicity": "*",
      "label": ""
    }}
  }}
}}

RESPONSE FORMAT:
You MUST respond with PURE JSON ONLY. No explanations, no markdown, no code blocks.
Just the raw JSON object starting with {{ and ending with }}.
"""
        
        if current_diagram_data:
            nodes = current_diagram_data.get('nodes', [])
            
            if nodes:
                node_info = []
                for node in nodes[:5]:
                    node_data = node.get('data', {})
                    label = node_data.get('label', 'Unknown')
                    node_id = node.get('id', '')
                    node_info.append(f"- {label} (ID: {node_id})")
                
                context = f"\n\nEXISTING DIAGRAM CONTEXT:\nClasses: {', '.join([n.get('data', {}).get('label', '') for n in nodes])}\n" + "\n".join(node_info)
                context += f"\n\nPosition new classes to avoid these existing positions. Use x > 100 and y > 100."
                base_prompt += context
        
        base_prompt += f"\n\nUSER COMMAND: {command}\n\nYour JSON response:"
        
        return base_prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Nova Pro response text and extract JSON.
        
        Args:
            response_text: Raw response text from Nova Pro
            
        Returns:
            Parsed dict with action, elements, confidence, interpretation
        """
        import re
        
        logger.info(f"Parsing Nova Pro response ({len(response_text)} chars)")
        
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                if not result.get('elements'):
                    logger.warning("Nova Pro returned empty elements array")
                    result['confidence'] = max(0.3, result.get('confidence', 0.5) * 0.6)
                    result['interpretation'] = result.get('interpretation', '') + ' (Warning: No elements generated)'
                
                logger.info(f"Successfully parsed Nova Pro response: action={result.get('action')}, elements={len(result.get('elements', []))}")
                return result
            else:
                logger.error("No JSON found in Nova Pro response")
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Failed to parse response',
                    'error': 'No valid JSON found in response',
                    'suggestion': 'Please try rephrasing your command.'
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Invalid JSON in response',
                'error': f'JSON parsing failed: {str(e)}',
                'suggestion': 'Please try again or rephrase your command.'
            }
        except Exception as e:
            logger.error(f"Response parsing error: {e}", exc_info=True)
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Parsing error: {str(e)}',
                'error': str(e),
                'suggestion': 'Please try again.'
            }
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        """
        Calculate cost for API call.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict with token counts and cost breakdown
        """
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        total_cost = input_cost + output_cost
        
        global _cost_tracking
        _cost_tracking["total_input_tokens"] += input_tokens
        _cost_tracking["total_output_tokens"] += output_tokens
        _cost_tracking["total_cost_usd"] += total_cost
        _cost_tracking["commands_processed"] += 1
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "request_cost_usd": total_cost,
            "cumulative_cost_usd": _cost_tracking["total_cost_usd"],
            "commands_processed": _cost_tracking["commands_processed"]
        }
    
    def get_cost_stats(self) -> Dict[str, Any]:
        """
        Get cumulative cost statistics.
        
        Returns:
            Dict with total tokens and costs
        """
        return dict(_cost_tracking)
