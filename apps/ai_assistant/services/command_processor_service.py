import json
import uuid
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .openai_service import OpenAIService
from apps.uml_diagrams.models import UMLDiagram


class UMLCommandProcessorService:
    """
    Advanced natural language processing service for UML diagram generation.
    Converts natural language commands into React Flow compatible JSON structures.
    """
    
    def __init__(self):
        try:
            self.openai_service = OpenAIService()
            self.openai_available = True
        except ImportError:
            self.openai_service = None
            self.openai_available = False
            
        self.logger = logging.getLogger(__name__)
        
        # Command patterns for different languages
        self.command_patterns = {
            'create_class': [
                r'(?:create|crear|créer|erstellen)\s+(?:class|classe|klasse)?\s+([A-Z][a-zA-Z0-9_]*)',
                r'(?:new|nueva|nouveau|neu)\s+(?:entity|entidad|entité|entität)\s+([A-Z][a-zA-Z0-9_]*)',
                r'(?:add|añadir|ajouter|hinzufügen)\s+(?:class|clase|classe|klasse)\s+([A-Z][a-zA-Z0-9_]*)'
            ],
            'add_attribute': [
                r'(?:with|con|avec|mit)\s+(?:attributes?|atributos?|attributs?)\s+(.+)',
                r'(?:add|añadir|ajouter|hinzufügen)\s+(?:attribute|atributo|attribut)\s+(.+)',
                r'(?:has|tiene|a|hat)\s+(?:attribute|atributo|attribut)\s+(.+)'
            ],
            'add_method': [
                r'(?:add|añadir|ajouter|hinzufügen)\s+(?:method|método|méthode|methode)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'(?:with|con|avec|mit)\s+(?:method|método|méthode|methode)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'(?:create|crear|créer|erstellen)\s+(?:function|función|fonction|funktion)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ],
            'create_relationship': [
                r'([A-Z][a-zA-Z0-9_]*)\s+(?:has|tiene|a|hat)\s+(?:many|muchos|plusieurs|viele)\s+([A-Z][a-zA-Z0-9_]*)',
                r'([A-Z][a-zA-Z0-9_]*)\s+(?:belongs to|pertenece a|appartient à|gehört zu)\s+([A-Z][a-zA-Z0-9_]*)',
                r'([A-Z][a-zA-Z0-9_]*)\s+(?:inherits from|hereda de|hérite de|erbt von)\s+([A-Z][a-zA-Z0-9_]*)',
                r'([A-Z][a-zA-Z0-9_]*)\s+(?:extends|extiende|étend|erweitert)\s+([A-Z][a-zA-Z0-9_]*)'
            ]
        }
        
        # Data type mappings
        self.type_mappings = {
            'string': 'String', 'str': 'String', 'text': 'String', 'texto': 'String',
            'int': 'Integer', 'integer': 'Integer', 'número': 'Integer', 'nombre': 'Integer',
            'bool': 'Boolean', 'boolean': 'Boolean', 'booleano': 'Boolean',
            'date': 'Date', 'fecha': 'Date', 'datetime': 'Date',
            'float': 'Float', 'double': 'Double', 'decimal': 'Decimal'
        }
        
        # Visibility mappings
        self.visibility_mappings = {
            'private': 'private', 'privado': 'private', 'privé': 'private',
            'public': 'public', 'público': 'public', 'publique': 'public',
            'protected': 'protected', 'protegido': 'protected', 'protégé': 'protected'
        }
    
    def process_command(self, command: str, diagram_id: Optional[str] = None) -> Dict:
        """
        Process natural language command and generate UML elements.
        
        Args:
            command: Natural language command
            diagram_id: Optional diagram ID for context
            
        Returns:
            Dict with processed elements and metadata
        """
        try:
            # Get diagram context if provided
            diagram_context = None
            if diagram_id:
                diagram_context = self._get_diagram_context(diagram_id)
            
            # First try pattern-based processing for common commands
            pattern_result = self._process_with_patterns(command, diagram_context)
            if pattern_result and pattern_result.get('confidence', 0) > 0.7:
                self.logger.info(f"Pattern-based processing successful for: {command[:50]}...")
                return pattern_result
            
            # Fall back to AI processing for complex commands
            if self.openai_available:
                ai_result = self._process_with_ai(command, diagram_context)
                self.logger.info(f"AI processing completed for: {command[:50]}...")
                return ai_result
            else:
                # Return pattern result or error if AI unavailable
                if pattern_result:
                    return pattern_result
                else:
                    return {
                        'error': 'AI service unavailable and command not recognized by patterns',
                        'suggestion': 'Try using simpler command patterns like "Create class User" or "Add method login"'
                    }
                    
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return {
                'error': f'Error processing command: {str(e)}',
                'suggestion': 'Please try rephrasing your command or contact support'
            }
    
    def _get_diagram_context(self, diagram_id: str) -> Optional[str]:
        """Get current diagram context for AI processing."""
        try:
            diagram = UMLDiagram.objects.get(id=diagram_id)
            classes = diagram.get_classes()
            relationships = diagram.get_relationships()
            
            context_parts = []
            context_parts.append(f"DIAGRAMA EXISTENTE: {diagram.title}")
            
            if classes:
                class_names = [cls.get('data', {}).get('label', 'Unknown') for cls in classes]
                context_parts.append(f"CLASES EXISTENTES: {', '.join(class_names)}")
                
                for cls in classes[:5]:  # Limit to avoid token overflow
                    cls_data = cls.get('data', {})
                    class_name = cls_data.get('label', 'Unknown')
                    attributes = cls_data.get('attributes', [])
                    methods = cls_data.get('methods', [])
                    
                    if attributes:
                        attr_names = [attr.get('name', 'unknown') for attr in attributes]
                        context_parts.append(f"  {class_name} atributos: {', '.join(attr_names)}")
                    if methods:
                        method_names = [method.get('name', 'unknown') for method in methods]
                        context_parts.append(f"  {class_name} métodos: {', '.join(method_names)}")
            
            if relationships:
                context_parts.append(f"RELACIONES EXISTENTES: {len(relationships)} relaciones definidas")
            
            return '\n'.join(context_parts)
            
        except UMLDiagram.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting diagram context: {e}")
            return None
    
    def _process_with_patterns(self, command: str, diagram_context: Optional[str] = None) -> Optional[Dict]:
        """Process command using regex patterns for common operations."""
        command_lower = command.lower().strip()
        
        # Try to match create class patterns
        for pattern in self.command_patterns['create_class']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                class_name = match.group(1)
                return self._create_class_element(class_name, command, diagram_context)
        
        # Try to match add attribute patterns  
        for pattern in self.command_patterns['add_attribute']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                attributes_text = match.group(1)
                return self._create_attribute_elements(attributes_text, command, diagram_context)
        
        # Try to match add method patterns
        for pattern in self.command_patterns['add_method']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                method_name = match.group(1)
                return self._create_method_element(method_name, command, diagram_context)
        
        # Try to match relationship patterns
        for pattern in self.command_patterns['create_relationship']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                source_class = match.group(1)
                target_class = match.group(2)
                return self._create_relationship_element(source_class, target_class, command, diagram_context)
        
        return None
    
    def _process_with_ai(self, command: str, diagram_context: Optional[str] = None) -> Dict:
        """Process command using AI for complex natural language understanding."""
        try:
            response = self.openai_service.call_command_processing_api(command, diagram_context)
            
            # Parse AI response
            ai_data = json.loads(response)
            
            # Validate and enhance AI response
            validated_data = self._validate_ai_response(ai_data)
            
            # Add positioning intelligence
            positioned_data = self._apply_intelligent_positioning(validated_data, diagram_context)
            
            return positioned_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from AI: {e}")
            return {
                'error': 'AI response parsing failed',
                'suggestion': 'Please try rephrasing your command'
            }
        except Exception as e:
            self.logger.error(f"AI processing error: {e}")
            return {
                'error': f'AI processing failed: {str(e)}',
                'suggestion': 'Please try again or use simpler command patterns'
            }
    
    def _create_class_element(self, class_name: str, original_command: str, diagram_context: Optional[str] = None) -> Dict:
        """Create a class element from pattern matching."""
        element_id = f"class-{str(uuid.uuid4())[:8]}"
        
        # Calculate intelligent position
        position = self._calculate_next_position(diagram_context)
        
        class_element = {
            "id": element_id,
            "data": {
                "label": class_name,
                "attributes": [],
                "methods": [],
                "nodeType": "class",
                "isAbstract": False
            },
            "type": "class",
            "position": position,
            "style": {"width": 180, "height": "auto"}
        }
        
        return {
            "action": "create_class",
            "elements": [{
                "type": "node",
                "data": class_element
            }],
            "confidence": 0.9,
            "interpretation": f"Crear clase '{class_name}' basado en el comando: '{original_command}'"
        }
    
    def _create_attribute_elements(self, attributes_text: str, original_command: str, diagram_context: Optional[str] = None) -> Dict:
        """Create attribute elements from text parsing."""
        attributes = []
        
        # Parse attributes (name type, name type, ...)
        attr_parts = [part.strip() for part in attributes_text.split(',')]
        
        for attr_part in attr_parts:
            tokens = attr_part.strip().split()
            if len(tokens) >= 2:
                attr_name = tokens[0]
                attr_type = tokens[1]
                
                # Map type to standard format
                mapped_type = self.type_mappings.get(attr_type.lower(), attr_type.capitalize())
                
                # Detect visibility
                visibility = 'private'  # Default
                if len(tokens) > 2:
                    visibility = self.visibility_mappings.get(tokens[2].lower(), visibility)
                
                attribute = {
                    "id": f"attr-{str(uuid.uuid4())[:8]}",
                    "name": attr_name,
                    "type": mapped_type,
                    "visibility": visibility
                }
                attributes.append(attribute)
        
        return {
            "action": "add_attribute",
            "elements": [{
                "type": "attribute_update",
                "data": {
                    "attributes": attributes
                }
            }],
            "confidence": 0.85,
            "interpretation": f"Añadir {len(attributes)} atributos basado en: '{original_command}'"
        }
    
    def _create_method_element(self, method_name: str, original_command: str, diagram_context: Optional[str] = None) -> Dict:
        """Create method element from pattern matching."""
        method = {
            "id": f"method-{str(uuid.uuid4())[:8]}",
            "name": method_name,
            "returnType": "void",
            "visibility": "public",
            "parameters": []
        }
        
        return {
            "action": "add_method", 
            "elements": [{
                "type": "method_update",
                "data": {
                    "methods": [method]
                }
            }],
            "confidence": 0.8,
            "interpretation": f"Añadir método '{method_name}' basado en: '{original_command}'"
        }
    
    def _create_relationship_element(self, source_class: str, target_class: str, original_command: str, diagram_context: Optional[str] = None) -> Dict:
        """Create relationship element from pattern matching."""
        
        # Determine relationship type from command
        command_lower = original_command.lower()
        relationship_type = "ASSOCIATION"  # Default
        source_multiplicity = "1"
        target_multiplicity = "1"
        
        if any(word in command_lower for word in ['has many', 'tiene muchos', 'a plusieurs']):
            relationship_type = "ASSOCIATION"
            source_multiplicity = "1"
            target_multiplicity = "1..*"
        elif any(word in command_lower for word in ['belongs to', 'pertenece a', 'appartient à']):
            relationship_type = "ASSOCIATION"
            source_multiplicity = "1..*"
            target_multiplicity = "1"
        elif any(word in command_lower for word in ['inherits', 'hereda', 'hérite', 'extends', 'extiende']):
            relationship_type = "INHERITANCE"
        elif any(word in command_lower for word in ['composes', 'compone', 'compose']):
            relationship_type = "COMPOSITION"
        elif any(word in command_lower for word in ['aggregates', 'agrega', 'agrège']):
            relationship_type = "AGGREGATION"
        
        edge_element = {
            "id": f"edge-{str(uuid.uuid4())[:8]}",
            "source": f"class-{source_class.lower()}",
            "target": f"class-{target_class.lower()}",
            "type": "umlRelationship",
            "data": {
                "relationshipType": relationship_type,
                "sourceMultiplicity": source_multiplicity,
                "targetMultiplicity": target_multiplicity,
                "label": ""
            }
        }
        
        return {
            "action": "create_relationship",
            "elements": [{
                "type": "edge",
                "data": edge_element
            }],
            "confidence": 0.85,
            "interpretation": f"Crear relación {relationship_type} entre '{source_class}' y '{target_class}'"
        }
    
    def _validate_ai_response(self, ai_data: Dict) -> Dict:
        """Validate and normalize AI response data."""
        validated = {
            "action": ai_data.get("action", "unknown"),
            "elements": [],
            "confidence": min(ai_data.get("confidence", 0.5), 1.0),
            "interpretation": ai_data.get("interpretation", "AI processing completed")
        }
        
        for element in ai_data.get("elements", []):
            if element.get("type") == "node":
                validated_node = self._validate_node_element(element.get("data", {}))
                if validated_node:
                    validated["elements"].append({
                        "type": "node",
                        "data": validated_node
                    })
            elif element.get("type") == "edge":
                validated_edge = self._validate_edge_element(element.get("data", {}))
                if validated_edge:
                    validated["elements"].append({
                        "type": "edge", 
                        "data": validated_edge
                    })
        
        return validated
    
    def _validate_node_element(self, node_data: Dict) -> Optional[Dict]:
        """Validate and normalize node element data."""
        if not node_data.get("id"):
            node_data["id"] = f"class-{str(uuid.uuid4())[:8]}"
        
        # Ensure required fields
        validated_node = {
            "id": node_data["id"],
            "data": {
                "label": node_data.get("data", {}).get("label", "NewClass"),
                "attributes": node_data.get("data", {}).get("attributes", []),
                "methods": node_data.get("data", {}).get("methods", []),
                "nodeType": "class",
                "isAbstract": node_data.get("data", {}).get("isAbstract", False)
            },
            "type": "class",
            "position": node_data.get("position", {"x": 100, "y": 100}),
            "style": {"width": 180, "height": "auto"}
        }
        
        # Validate attributes
        validated_attributes = []
        for attr in validated_node["data"]["attributes"]:
            if attr.get("name"):
                validated_attr = {
                    "id": attr.get("id", f"attr-{str(uuid.uuid4())[:8]}"),
                    "name": attr["name"],
                    "type": self.type_mappings.get(attr.get("type", "String").lower(), attr.get("type", "String")),
                    "visibility": self.visibility_mappings.get(attr.get("visibility", "private").lower(), "private")
                }
                validated_attributes.append(validated_attr)
        validated_node["data"]["attributes"] = validated_attributes
        
        # Validate methods
        validated_methods = []
        for method in validated_node["data"]["methods"]:
            if method.get("name"):
                validated_method = {
                    "id": method.get("id", f"method-{str(uuid.uuid4())[:8]}"),
                    "name": method["name"],
                    "returnType": method.get("returnType", "void"),
                    "visibility": self.visibility_mappings.get(method.get("visibility", "public").lower(), "public"),
                    "parameters": method.get("parameters", [])
                }
                validated_methods.append(validated_method)
        validated_node["data"]["methods"] = validated_methods
        
        return validated_node
    
    def _validate_edge_element(self, edge_data: Dict) -> Optional[Dict]:
        """Validate and normalize edge element data."""
        if not all([edge_data.get("source"), edge_data.get("target")]):
            return None
        
        validated_edge = {
            "id": edge_data.get("id", f"edge-{str(uuid.uuid4())[:8]}"),
            "source": edge_data["source"],
            "target": edge_data["target"],
            "type": "umlRelationship",
            "data": {
                "relationshipType": edge_data.get("data", {}).get("relationshipType", "ASSOCIATION"),
                "sourceMultiplicity": edge_data.get("data", {}).get("sourceMultiplicity", "1"),
                "targetMultiplicity": edge_data.get("data", {}).get("targetMultiplicity", "1"),
                "label": edge_data.get("data", {}).get("label", "")
            }
        }
        
        return validated_edge
    
    def _apply_intelligent_positioning(self, data: Dict, diagram_context: Optional[str] = None) -> Dict:
        """Apply intelligent positioning to elements based on diagram context."""
        for element in data.get("elements", []):
            if element.get("type") == "node":
                node_data = element.get("data", {})
                if not node_data.get("position") or node_data["position"] == {"x": 100, "y": 100}:
                    # Calculate intelligent position
                    new_position = self._calculate_next_position(diagram_context)
                    node_data["position"] = new_position
        
        return data
    
    def _calculate_next_position(self, diagram_context: Optional[str] = None) -> Dict[str, int]:
        """Calculate intelligent position for new elements."""
        # Default position
        base_x, base_y = 100, 100
        
        if diagram_context:
            # Try to parse existing positions from context
            # This is a simplified version - in production you'd parse the actual diagram data
            lines = diagram_context.split('\n')
            class_count = sum(1 for line in lines if 'CLASES EXISTENTES:' in line)
            
            # Simple grid layout
            grid_size = 250
            col = class_count % 4
            row = class_count // 4
            
            return {"x": base_x + (col * grid_size), "y": base_y + (row * grid_size)}
        
        return {"x": base_x, "y": base_y}
    
    def get_supported_commands(self) -> Dict:
        """Return documentation of supported command patterns."""
        return {
            "create_class": [
                "Create class User",
                "Nueva entidad Producto", 
                "Add class Category"
            ],
            "add_attribute": [
                "with attributes name string, age int",
                "con atributos nombre string, edad int",
                "add attribute email string private"
            ],
            "add_method": [
                "add method login",
                "añadir método calcular",
                "create function save"
            ],
            "create_relationship": [
                "User has many Orders",
                "Usuario hereda de Persona",
                "Product belongs to Category"
            ]
        }
