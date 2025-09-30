import json
import logging
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
        
        Args:
            command: Natural language command
            diagram_id: Optional diagram ID for context (not used in simplified version)
            current_diagram_data: Current diagram state with nodes and edges
            
        Returns:
            Dict with processed elements and metadata
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

            response = self.openai_service.call_command_processing_api(
                command=command,
                current_diagram_data=current_diagram_data
            )

            try:
                result = json.loads(response)

                if result.get('action') != 'error' and not result.get('elements'):
                    self.logger.warning(f"AI returned empty elements for command: {command[:50]}")
                    result['confidence'] = 0.3
                    result['interpretation'] = result.get('interpretation', '') + ' (Warning: No elements generated)'
                
                self.logger.info(f"Command processed successfully: {command[:50]}... (confidence: {result.get('confidence', 0)})")
                return result
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON from OpenAI: {e}")
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'Failed to parse AI response',
                    'error': 'Invalid JSON response from AI',
                    'suggestion': 'Please try rephrasing your command more clearly.'
                }
                    
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
