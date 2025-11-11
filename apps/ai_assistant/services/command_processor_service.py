import json
import logging
import re
from typing import Dict, Optional
from .openai_service import OpenAIService


class UMLCommandProcessorService:
    """
    Simplified natural language processing service for UML diagram generation.
    Uses direct OpenAI API call with comprehensive prompt to generate exact 
    React Flow compatible JSON structures.
    
    Replaces complex pattern matching with single powerful AI call.
    """
    
    def __init__(self):
        try:
            self.openai_service = OpenAIService()
            self.openai_available = True
        except ImportError:
            self.openai_service = None
            self.openai_available = False
            
        self.logger = logging.getLogger(__name__)
    
    def process_command(self, command: str, diagram_id: Optional[str] = None, current_diagram_data: Optional[Dict] = None) -> Dict:
        """
        Process natural language command and generate UML elements using direct OpenAI call.
        """
        try:
            if not self.openai_available:
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'OpenAI service unavailable',
                    'error': 'AI service unavailable. Install OpenAI dependencies.',
                    'suggestion': 'Install openai and tiktoken packages to enable AI command processing.'
                }

            self.logger.info(f"Processing command with o4-mini: {command[:100]}")
            
            response = self.openai_service.call_command_processing_api(
                command=command,
                current_diagram_data=current_diagram_data
            )
            
            self.logger.info(f"Received response from o4-mini ({len(response)} chars)")
            self.logger.debug(f"Response preview: {response[:200]}...")

            result = self._extract_and_parse_json(response)
            
            if result is None:
                self.logger.error(f"Failed to extract JSON from o4-mini response")
                self.logger.error(f"Full response: {response[:1000]}")
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Failed to parse AI response',
                    'error': 'Could not extract valid JSON from o4-mini response',
                    'suggestion': 'Try rephrasing your command more clearly.',
                    'raw_response_preview': response[:500]
                }

            if result.get('action') != 'error' and not result.get('elements'):
                self.logger.warning(f"AI returned empty elements for command: {command[:50]}")
                result['confidence'] = 0.3
                result['interpretation'] = result.get('interpretation', '') + ' (Warning: No elements generated)'
            
            self.logger.info(f"Command processed successfully: {command[:50]}... (confidence: {result.get('confidence', 0)})")
            return result
                    
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Error: {str(e)}',
                'error': f'Error processing command: {str(e)}',
                'suggestion': 'Please try again or contact support if the issue persists.'
            }
    
    def _extract_and_parse_json(self, response_text: str) -> Optional[Dict]:
        """
        Robustly extract and parse JSON from o4-mini response text.
        """
        if not response_text or not response_text.strip():
            self.logger.error("Empty response text received")
            return None
        
        self.logger.info(f"Attempting JSON extraction from response ({len(response_text)} chars)")
        self.logger.debug(f"First 200 chars: {response_text[:200]}")
        
        # STRATEGY 1: Direct JSON parse
        try:
            result = json.loads(response_text)
            self.logger.info("Strategy 1 SUCCESS: Direct JSON parse")
            return result
        except json.JSONDecodeError:
            self.logger.debug("Strategy 1 failed: Not direct JSON")
        
        # STRATEGY 2: Extract from markdown code block
        try:
            # Pattern: ```json ... ``` or ``` ... ```
            markdown_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
            match = re.search(markdown_pattern, response_text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                result = json.loads(json_str)
                self.logger.info("✓ Strategy 2 SUCCESS: Markdown extraction")
                return result
            else:
                self.logger.debug("✗ Strategy 2 failed: No markdown blocks found")
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.debug(f"✗ Strategy 2 failed: {e}")
        
        # STRATEGY 3: Find first { and matching }
        try:
            first_brace = response_text.find('{')
            if first_brace == -1:
                self.logger.debug("✗ Strategy 3 failed: No opening brace found")
            else:
                # Count braces to find matching closing brace
                brace_count = 0
                end_pos = first_brace
                
                for i in range(first_brace, len(response_text)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
                
                if brace_count == 0:
                    json_str = response_text[first_brace:end_pos]
                    result = json.loads(json_str)
                    self.logger.info("✓ Strategy 3 SUCCESS: Brace counting extraction")
                    return result
                else:
                    self.logger.debug("✗ Strategy 3 failed: Unmatched braces")
        except json.JSONDecodeError as e:
            self.logger.debug(f"✗ Strategy 3 failed: {e}")
        
        # STRATEGY 4: Regex pattern for JSON object
        try:
            # Find JSON-like patterns
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.finditer(json_pattern, response_text, re.DOTALL)
            
            for match in matches:
                try:
                    json_str = match.group(0)
                    result = json.loads(json_str)
                    # Validate it looks like our expected structure
                    if 'action' in result or 'elements' in result:
                        self.logger.info("✓ Strategy 4 SUCCESS: Regex pattern extraction")
                        return result
                except json.JSONDecodeError:
                    continue
            
            self.logger.debug("✗ Strategy 4 failed: No valid JSON patterns found")
        except Exception as e:
            self.logger.debug(f"✗ Strategy 4 failed: {e}")
        
        # STRATEGY 5: Clean and retry
        try:
            # Remove everything before first { and after last }
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = response_text[first_brace:last_brace + 1]
                
                # Try to fix common issues
                # Remove trailing commas before } or ]
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                
                result = json.loads(json_str)
                self.logger.info("✓ Strategy 5 SUCCESS: Clean and retry")
                return result
            else:
                self.logger.debug("✗ Strategy 5 failed: No valid brace positions")
        except json.JSONDecodeError as e:
            self.logger.debug(f"✗ Strategy 5 failed: {e}")
        
        # All strategies failed
        self.logger.error("✗ ALL EXTRACTION STRATEGIES FAILED")
        self.logger.error(f"Full response text:\n{response_text}")
        return None
    
    def get_supported_commands(self) -> Dict:
        """
        Return documentation of supported command patterns.
        """
        return {
            "create_class": [
                "Create class User",
                "Crea una clase Producto con nombre, precio, stock", 
                "Nueva entidad Categoria"
            ],
            "add_attribute": [
                "User with attributes email string, age int",
                "con atributos id, nombre, apellido, edad",
                "add attribute status string"
            ],
            "add_method": [
                "add method login",
                "añadir método calcular total",
                "create function save"
            ],
            "create_relationship": [
                "User has many Orders",
                "Producto pertenece a Categoria",
                "Admin extends User"
            ]
        }
