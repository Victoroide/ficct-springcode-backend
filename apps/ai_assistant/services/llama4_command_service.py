"""Llama 4 Maverick Command Service for UML Diagram Generation.

Processes natural language commands using Llama 4 Maverick 17B via AWS Bedrock.
70% cheaper than Nova Pro with excellent reasoning and 1M token context window.

Pricing:
    - Input: $0.24 per 1M tokens
    - Output: $0.97 per 1M tokens
    - Average cost per command: $0.001-0.002
    - Response time: 8-12 seconds
    - Context window: 1M tokens (vs 300K Nova Pro)
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings

logger = logging.getLogger(__name__)

_llama4_command_client = None
_cost_tracking = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "commands_processed": 0
}


def get_llama4_command_client():
    """
    Get singleton Llama 4 Maverick client instance for command processing.
    
    Uses boto3 AWS SDK configured for Bedrock with inference profile.
    
    Returns:
        Bedrock runtime client or None if initialization fails
    """
    global _llama4_command_client
    
    if _llama4_command_client is None:
        try:
            _llama4_command_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_DEFAULT_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            logger.info("Llama 4 Maverick Bedrock client initialized successfully")
        except (NoCredentialsError, Exception) as e:
            logger.error(f"Failed to initialize Llama 4 Bedrock client: {e}")
            _llama4_command_client = None
    
    return _llama4_command_client


class Llama4CommandService:
    """
    Service for processing UML commands using Llama 4 Maverick 17B via AWS Bedrock.
    
    Features:
        - 70% cheaper than Nova Pro
        - 1M token context window
        - Excellent reasoning capabilities
        - No streaming support (synchronous only)
        - Uses inference profile for cross-region routing
    """
    
    MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"
    
    INPUT_COST_PER_1M_TOKENS = 0.24
    OUTPUT_COST_PER_1M_TOKENS = 0.97
    
    def __init__(self):
        """Initialize Llama 4 Maverick command service."""
        self.client = get_llama4_command_client()
        self.logger = logging.getLogger(__name__)
    
    def process_command(
        self,
        command: str,
        diagram_id: Optional[str] = None,
        current_diagram_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process natural language command using Llama 4 Maverick.
        
        Args:
            command: Natural language command in Spanish/English/French
            diagram_id: Optional diagram ID for context
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            Dict with action, elements, confidence, interpretation, metadata
            
        Raises:
            AWSBedrockError: If API call fails
        """
        start_time = time.time()
        
        if not self.client:
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Llama 4 Maverick service not configured',
                'error': 'AWS Bedrock service unavailable. Check AWS credentials.',
                'suggestion': 'Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in settings.'
            }
        
        try:
            base_prompt = self._build_command_prompt(command, current_diagram_data)
            formatted_prompt = self._format_llama_prompt(base_prompt)
            
            logger.info(f"Calling Llama 4 Maverick API for command: {command[:100]}")
            
            request_body = {
                "prompt": formatted_prompt,
                "max_gen_len": 4096,
                "temperature": 0.3,
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
            
            logger.info(f"Llama 4 response body keys: {response_body.keys()}")
            logger.info(f"Generation field length: {len(generation)} chars")
            logger.info(f"Generation preview: {generation[:300]}")
            
            if not generation:
                logger.error(f"Empty generation field! Full response body: {response_body}")
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Llama 4 returned empty generation',
                    'error': 'Empty response from model',
                    'metadata': {
                        'model': 'llama4-maverick',
                        'response_time': round(time.time() - start_time, 2),
                        'error_occurred': True
                    }
                }
            
            cost_info = self._calculate_cost(prompt_tokens, completion_tokens)
            
            processing_time = time.time() - start_time
            
            result = self._parse_response(generation)
            
            result['metadata'] = {
                'model': 'llama4-maverick',
                'response_time': round(processing_time, 2),
                'input_tokens': prompt_tokens,
                'output_tokens': completion_tokens,
                'cost_usd': cost_info['total_cost'],
                'stop_reason': stop_reason
            }
            
            self.logger.info(
                f"Llama 4 Maverick processed command in {processing_time:.2f}s. "
                f"Tokens: {prompt_tokens} in + {completion_tokens} out. "
                f"Cost: ${cost_info['total_cost']:.6f}"
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(
                f"Llama 4 Maverick API error: {error_code} - {error_message}",
                exc_info=True
            )
            
            processing_time = time.time() - start_time
            
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Llama 4 Maverick API error: {error_code}',
                'error': 'Failed to process command with Llama 4 Maverick.',
                'suggestion': 'The system will automatically try Nova Pro as fallback.',
                'metadata': {
                    'model': 'llama4-maverick',
                    'response_time': round(processing_time, 2),
                    'error_occurred': True,
                    'error_code': error_code
                }
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in Llama 4 Maverick processing: {e}", exc_info=True)
            
            processing_time = time.time() - start_time
            
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Unexpected error during command processing',
                'error': str(e),
                'suggestion': 'Please try rephrasing your command or contact support.',
                'metadata': {
                    'model': 'llama4-maverick',
                    'response_time': round(processing_time, 2),
                    'error_occurred': True
                }
            }
    
    def _build_command_prompt(self, command: str, current_diagram_data: Optional[Dict] = None) -> str:
        """
        Build comprehensive prompt for command processing with full context awareness.
        
        Uses same context building logic as Nova Pro for consistency.
        
        Args:
            command: Natural language command
            current_diagram_data: Optional existing diagram data
            
        Returns:
            Formatted prompt string with complete diagram context
        """
        import time
        timestamp_ms = int(time.time() * 1000)
        
        base_prompt = f"""You are a UML diagram generator that converts natural language to EXACT React Flow JSON.

SUPPORTED ACTIONS:
1. create_class - Create NEW class (only if doesn't exist)
2. update_class - MODIFY existing class (preserve ID, update content)
3. create_relationship - Add edge between existing classes

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

CRITICAL MODIFICATION RULES:

When modifying existing classes:
1. Action MUST be "update_class"
2. Include SAME class ID from context
3. Include ALL attributes (existing + new/modified)
4. Preserve class position
5. Do NOT create duplicates

When creating new classes:
1. Action is "create_class"
2. Generate new ID with timestamp: class-{timestamp_ms}
3. Verify class name doesn't exist in context
4. Choose position to avoid overlaps

When creating relationships:
1. Use EXISTING class IDs from context
2. Action is "create_relationship"
3. Verify both source and target exist

RESPONSE FORMAT:
You MUST respond with PURE JSON ONLY. No explanations, no markdown, no code blocks.
Just the raw JSON object starting with {{ and ending with }}.
"""
        
        if current_diagram_data:
            nodes = current_diagram_data.get('nodes', [])
            edges = current_diagram_data.get('edges', [])
            
            if nodes:
                context = "\n\n" + "="*70 + "\n"
                context += "EXISTING DIAGRAM CONTEXT\n"
                context += "="*70 + "\n\n"
                context += f"Total Classes: {len(nodes)}\n"
                context += f"Total Relationships: {len(edges)}\n\n"
                context += "CLASSES DETAIL:\n\n"
                
                for idx, node in enumerate(nodes, 1):
                    node_id = node.get('id', 'unknown')
                    data = node.get('data', {})
                    label = data.get('label', 'Unknown')
                    position = node.get('position', {'x': 0, 'y': 0})
                    attributes = data.get('attributes', [])
                    methods = data.get('methods', [])
                    node_type = data.get('nodeType', 'class')
                    is_abstract = data.get('isAbstract', False)
                    
                    context += f"{idx}. {label} (ID: {node_id})\n"
                    if is_abstract:
                        context += "   Type: Abstract Class\n"
                    context += f"   Position: x={position['x']}, y={position['y']}\n"
                    
                    if attributes:
                        context += "   Attributes:\n"
                        for attr in attributes:
                            attr_name = attr.get('name', 'unknown')
                            attr_type = attr.get('type', 'String')
                            visibility = attr.get('visibility', 'private')
                            is_static = attr.get('isStatic', False)
                            is_final = attr.get('isFinal', False)
                            modifiers = []
                            if is_static:
                                modifiers.append('static')
                            if is_final:
                                modifiers.append('final')
                            mod_str = ' '.join(modifiers)
                            context += f"   - {attr_name}: {attr_type} ({visibility})"
                            if mod_str:
                                context += f" [{mod_str}]"
                            context += "\n"
                    else:
                        context += "   Attributes: (none)\n"
                    
                    if methods:
                        context += "   Methods:\n"
                        for method in methods:
                            method_name = method.get('name', 'unknown')
                            return_type = method.get('returnType', 'void')
                            visibility = method.get('visibility', 'public')
                            parameters = method.get('parameters', [])
                            if parameters:
                                param_str = ', '.join([f"{p.get('name', 'param')}: {p.get('type', 'String')}" for p in parameters])
                                context += f"   - {method_name}({param_str}): {return_type} ({visibility})\n"
                            else:
                                context += f"   - {method_name}(): {return_type} ({visibility})\n"
                    else:
                        context += "   Methods: (none)\n"
                    
                    context += "\n"
                
                if edges:
                    context += "RELATIONSHIPS:\n\n"
                    for idx, edge in enumerate(edges, 1):
                        source_id = edge.get('source', '')
                        target_id = edge.get('target', '')
                        edge_data = edge.get('data', {})
                        rel_type = edge_data.get('relationshipType', 'ASSOCIATION')
                        source_mult = edge_data.get('sourceMultiplicity', '1')
                        target_mult = edge_data.get('targetMultiplicity', '1')
                        label = edge_data.get('label', '')
                        
                        source_name = next((n['data']['label'] for n in nodes if n['id'] == source_id), source_id)
                        target_name = next((n['data']['label'] for n in nodes if n['id'] == target_id), target_id)
                        
                        context += f"{idx}. {source_name} → {target_name} ({rel_type})\n"
                        context += f"   Source ID: {source_id}\n"
                        context += f"   Target ID: {target_id}\n"
                        context += f"   Source Multiplicity: {source_mult}\n"
                        context += f"   Target Multiplicity: {target_mult}\n"
                        if label:
                            context += f"   Label: {label}\n"
                        context += "\n"
                else:
                    context += "RELATIONSHIPS: (none)\n\n"
                
                context += "="*70 + "\n"
                context += "CRITICAL INSTRUCTIONS FOR THIS COMMAND\n"
                context += "="*70 + "\n\n"
                
                context += "1. IDENTIFY THE TARGET:\n"
                context += "   - Find class by exact name match from context above\n"
                context += "   - Use the class ID from context (NEVER create new ID for existing class)\n"
                context += "   - Do NOT create duplicate classes\n\n"
                
                context += "2. MODIFICATION OPERATIONS:\n"
                context += "   - ADD ATTRIBUTE: Use action 'update_class', include ALL existing attributes + new one\n"
                context += "   - REMOVE ATTRIBUTE: Use action 'update_class', include all EXCEPT removed attribute\n"
                context += "   - MODIFY ATTRIBUTE: Use action 'update_class', update the specific attribute\n"
                context += "   - ADD METHOD: Use action 'update_class', include ALL existing methods + new one\n"
                context += "   - REMOVE METHOD: Use action 'update_class', include all EXCEPT removed method\n\n"
                
                context += "3. RELATIONSHIP OPERATIONS:\n"
                context += "   - Use action 'create_relationship'\n"
                context += "   - Use EXISTING class IDs from context for source and target\n"
                context += "   - Never create classes just to make relationships\n\n"
                
                context += "4. PRESERVATION RULES:\n"
                context += "   - When updating a class, include ALL its current attributes\n"
                context += "   - Keep class position exactly as shown in context\n"
                context += "   - Keep same class ID\n"
                context += "   - Only change what the command explicitly requests\n\n"
                
                context += "5. JSON FORMAT FOR UPDATE:\n"
                context += '{{\n'
                context += '  "action": "update_class",\n'
                context += '  "elements": [{{\n'
                context += '    "type": "node",\n'
                context += '    "data": {{\n'
                context += '      "id": "class-xxx",\n'
                context += '      "data": {{\n'
                context += '        "label": "ClassName",\n'
                context += '        "attributes": [],\n'
                context += '        "methods": [],\n'
                context += '        "nodeType": "class"\n'
                context += '      }},\n'
                context += '      "position": {{"x": same, "y": same}}\n'
                context += '    }}\n'
                context += '  }}],\n'
                context += '  "confidence": 0.95,\n'
                context += '  "interpretation": "Updated ClassName..."\n'
                context += '}}\n\n'
                
                base_prompt += context
        else:
            base_prompt += "\n\nNo existing diagram context. Creating new diagram from scratch.\n\n"
        
        base_prompt += f"USER COMMAND: {command}\n\n"
        base_prompt += "Return ONLY valid JSON with no markdown formatting or code blocks."
        
        return base_prompt
    
    def _format_llama_prompt(self, base_prompt: str) -> str:
        """
        Format prompt in Llama 4 Maverick specific format.
        
        Llama 4 requires special tokens for proper processing:
        - <|begin_of_text|> at start
        - <|start_header_id|>user<|end_header_id|> for user role
        - <|eot_id|> for end of turn
        - <|start_header_id|>assistant<|end_header_id|> for assistant role
        
        Args:
            base_prompt: The base prompt content
            
        Returns:
            Formatted prompt with Llama 4 tokens
        """
        formatted = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
        formatted += base_prompt
        formatted += "\n<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n"
        
        return formatted
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Llama 4 Maverick response text and extract JSON.
        
        Uses multiple extraction strategies to handle various response formats.
        Ensures all required fields are present with proper defaults.
        
        Args:
            response_text: Raw response text from Llama 4 Maverick
            
        Returns:
            Parsed JSON as dictionary with all required fields
        """
        logger.info(f"[PARSING] Starting parse of {len(response_text)} char response")
        logger.info(f"[PARSING] Response preview (first 400 chars): {response_text[:400]}")
        logger.info(f"[PARSING] Response preview (last 200 chars): {response_text[-200:]}")
        
        if not response_text or not response_text.strip():
            logger.error("[PARSING] Empty response text")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Empty response from Llama 4 Maverick',
                'error': 'No output generated'
            }
        
        strategies = [
            self._try_direct_parse,
            self._try_markdown_extraction,
            self._try_brace_counting,
            self._try_json_block_extraction,
            self._try_last_valid_json
        ]
        
        for i, strategy in enumerate(strategies, 1):
            try:
                logger.info(f"[PARSING] Trying strategy {i}/{len(strategies)}: {strategy.__name__}")
                result = strategy(response_text)
                if result:
                    logger.info(f"[PARSING] Strategy {strategy.__name__} SUCCESS")
                    logger.info(f"[PARSING] Extracted keys: {result.keys()}")
                    logger.info(f"[PARSING] Action: {result.get('action')}")
                    logger.info(f"[PARSING] Elements count: {len(result.get('elements', []))}")
                    
                    validated_result = self._validate_and_normalize_result(result)
                    logger.info(f"[PARSING] After validation - Action: {validated_result.get('action')}, Elements: {len(validated_result.get('elements', []))}")
                    return validated_result
                else:
                    logger.warning(f"[PARSING] Strategy {strategy.__name__} returned None")
            except Exception as e:
                logger.warning(f"[PARSING] Strategy {strategy.__name__} failed with error: {e}")
                continue
        
        logger.error(f"[PARSING] ALL {len(strategies)} STRATEGIES FAILED")
        logger.error(f"[PARSING] Full response text:\n{response_text}")
        
        return {
            'action': 'error',
            'elements': [],
            'confidence': 0.0,
            'interpretation': 'Could not parse Llama 4 Maverick response',
            'error': 'Failed to extract valid JSON from all strategies',
            'raw_response_preview': response_text[:500]
        }
    
    def _validate_and_normalize_result(self, result: Dict) -> Dict[str, Any]:
        """
        Validate and normalize parsed result to ensure all required fields exist.
        
        Args:
            result: Raw parsed result from extraction strategy
            
        Returns:
            Normalized result with all required fields and proper defaults
        """
        if not isinstance(result, dict):
            logger.error(f"[VALIDATION] Result is not a dict: {type(result)}")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': 'Invalid result type',
                'error': 'Parsed result is not a dictionary'
            }
        
        normalized = {
            'action': result.get('action', 'create_class'),
            'elements': result.get('elements', []),
            'confidence': result.get('confidence', 0.85),
            'interpretation': result.get('interpretation', 'Generated by Llama 4 Maverick')
        }
        
        if not normalized['action']:
            logger.warning("[VALIDATION] Missing action, defaulting to 'create_class'")
            normalized['action'] = 'create_class'
        
        if not isinstance(normalized['elements'], list):
            logger.warning(f"[VALIDATION] Elements not a list: {type(normalized['elements'])}, defaulting to []")
            normalized['elements'] = []
        
        if not isinstance(normalized['confidence'], (int, float)):
            logger.warning(f"[VALIDATION] Confidence not numeric: {type(normalized['confidence'])}, defaulting to 0.85")
            normalized['confidence'] = 0.85
        
        if not isinstance(normalized['interpretation'], str):
            logger.warning(f"[VALIDATION] Interpretation not string: {type(normalized['interpretation'])}, defaulting")
            normalized['interpretation'] = 'Generated by Llama 4 Maverick'
        
        logger.info(f"[VALIDATION] Normalized result: action={normalized['action']}, elements={len(normalized['elements'])}, confidence={normalized['confidence']}")
        
        return normalized
    
    def _try_direct_parse(self, text: str) -> Optional[Dict]:
        """Try parsing text directly as JSON."""
        parsed = json.loads(text.strip())
        logger.debug(f"[DIRECT_PARSE] Success: {parsed.keys() if isinstance(parsed, dict) else type(parsed)}")
        return parsed
    
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
        """Look for JSON block patterns."""
        patterns = [
            r'\{[^{}]*"action"[^{}]*"elements"[^{}]*\}',
            r'\{.*?"action".*?\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    continue
        
        return None
    
    def _try_last_valid_json(self, text: str) -> Optional[Dict]:
        """Find last occurrence of valid JSON object."""
        all_braces = [(m.start(), '{') for m in re.finditer(r'\{', text)]
        all_braces.extend([(m.start(), '}') for m in re.finditer(r'\}', text)])
        all_braces.sort(reverse=True)
        
        for start_pos, char in all_braces:
            if char == '}':
                for other_pos, other_char in all_braces:
                    if other_char == '{' and other_pos < start_pos:
                        try:
                            candidate = text[other_pos:start_pos+1]
                            return json.loads(candidate)
                        except:
                            continue
        
        return None
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
        """
        Calculate cost for Llama 4 Maverick API usage.
        
        Pricing:
            - Input: $0.24 per 1M tokens
            - Output: $0.97 per 1M tokens
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Dict with input_cost, output_cost, total_cost
        """
        input_cost = (prompt_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        total_cost = input_cost + output_cost
        
        global _cost_tracking
        _cost_tracking["total_input_tokens"] += prompt_tokens
        _cost_tracking["total_output_tokens"] += completion_tokens
        _cost_tracking["total_cost_usd"] += total_cost
        _cost_tracking["commands_processed"] += 1
        
        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6)
        }
    
    @staticmethod
    def get_cost_tracking() -> Dict[str, Any]:
        """
        Get cumulative cost tracking statistics.
        
        Returns:
            Dict with total tokens, cost, and commands processed
        """
        return _cost_tracking.copy()
