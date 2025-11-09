import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
from .openai_service import OpenAIService
from apps.uml_diagrams.models import UMLDiagram


class AIAssistantService:
    """
    AI Assistant service for contextual help about UML diagrams and system functionality.
    """
    
    def __init__(self):
        try:
            self.openai_service = OpenAIService()
            self.openai_available = True
        except ImportError as e:
            self.openai_service = None
            self.openai_available = False
            
        self.system_context = self._build_system_context()
        self.logger = logging.getLogger(__name__)
    
    def _build_system_context(self) -> str:
        """Build comprehensive system context for AI assistant."""
        return """
        You are an expert AI assistant for a collaborative UML diagram editor system.
        
        SYSTEM CAPABILITIES:
        - Real-time collaborative UML class diagram editing
        - SpringBoot code generation from UML diagrams
        - Group chat for team collaboration
        - Professional UML 2.5+ standards support
        - Anonymous session-based access (no user registration required)
        
        HELP USERS WITH:
        - UML diagram design best practices
        - Class relationships (Association, Aggregation, Composition, Inheritance)
        - SpringBoot code generation options
        - System features and functionality
        - Collaborative features usage
        - Anonymous session management
        
        RESPONSE GUIDELINES:
        - Always provide practical, actionable advice in the user's language
        - Be concise but comprehensive in explanations

        IMPORTANT: You ALWAYS need to be concise and comprehensive in your responses. Make your responses longer ONLY when the user asks for it.
        """
    
    def get_contextual_help(self, user_question: str, diagram_id: Optional[str] = None, 
                          context_type: str = "general") -> Dict:
        """
        Get contextual help based on user question and optional diagram context.
        
        Args:
            user_question: The user's question in Spanish
            diagram_id: Optional UUID of specific diagram for context
            context_type: Type of context ("general", "diagram", "code-generation")
            
        Returns:
            Dict with answer, suggestions, and related features
        """
        try:

            if not self.openai_available:
                return {
                    "answer": "El asistente de IA no está disponible en este momento. Por favor, contacta al administrador del sistema para configurar el servicio OpenAI.",
                    "suggestions": ["Contactar administrador", "Consultar documentación"],
                    "related_features": ["uml_editing", "system_help"]
                }

            diagram_context = ""
            diagram_data = None
            
            if diagram_id:
                diagram_data = self._get_diagram_data(diagram_id)
                diagram_context = self._build_diagram_context(diagram_data)

            prompt = self._select_prompt_template(context_type, user_question, diagram_context)

            messages = [
                {"role": "system", "content": self.system_context},
                {"role": "user", "content": prompt}
            ]
            
            response = self.openai_service.call_api(messages)

            formatted_response = self._format_response(response, context_type, diagram_data)
            
            self.logger.info(f"AI Assistant responded to question: {user_question[:50]}...")
            
            return formatted_response
            
        except Exception as e:
            self.logger.error(f"Error in get_contextual_help: {e}", exc_info=True)
            self.logger.error(f"Question was: {user_question}")
            self.logger.error(f"Diagram ID: {diagram_id}, Context type: {context_type}")
            return {
                "answer": "Lo siento, hubo un error al procesar tu pregunta. Por favor, inténtalo de nuevo.",
                "suggestions": ["Reformular la pregunta", "Verificar conexión"],
                "related_features": [],
                "error_type": str(type(e).__name__),
                "error_message": str(e) if __debug__ else "Internal error"
            }
    
    def _get_diagram_data(self, diagram_id: str) -> Optional[Dict]:
        """Retrieve diagram data by ID."""
        try:
            diagram = UMLDiagram.objects.get(id=diagram_id)
            return {
                'id': str(diagram.id),
                'title': diagram.title,
                'description': diagram.description,
                'diagram_type': diagram.diagram_type,
                'content': diagram.content,
                'classes': diagram.get_classes(),
                'relationships': diagram.get_relationships(),
                'active_sessions': diagram.active_sessions,
                'created_at': diagram.created_at.isoformat(),
                'last_modified': diagram.last_modified.isoformat()
            }
        except UMLDiagram.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving diagram {diagram_id}: {e}")
            return None
    
    def _build_diagram_context(self, diagram_data: Optional[Dict]) -> str:
        """Build context from current diagram data."""
        if not diagram_data:
            return ""
        
        classes = diagram_data.get('classes', [])
        relationships = diagram_data.get('relationships', [])
        active_sessions = diagram_data.get('active_sessions', [])

        class_details = []
        for cls in classes:
            if isinstance(cls, dict):
                class_name = cls.get('name', cls.get('label', 'Unknown'))
                attributes = cls.get('attributes', [])
                methods = cls.get('methods', [])
                is_abstract = cls.get('isAbstract', False)

                attr_list = []
                for attr in attributes:
                    if isinstance(attr, dict):
                        attr_name = attr.get('name', 'unknown')
                        attr_type = attr.get('type', 'unknown')
                        visibility = attr.get('visibility', 'private')
                        attr_list.append(f"{visibility} {attr_name}: {attr_type}")

                method_list = []
                for method in methods:
                    if isinstance(method, dict):
                        method_name = method.get('name', 'unknown')
                        return_type = method.get('returnType', 'void')
                        visibility = method.get('visibility', 'public')
                        method_list.append(f"{visibility} {method_name}(): {return_type}")
                
                class_info = f"  * {class_name}"
                if is_abstract:
                    class_info += " (abstracta)"
                if attr_list:
                    class_info += f"\n    - Atributos: {', '.join(attr_list)}"
                if method_list:
                    class_info += f"\n    - Métodos: {', '.join(method_list)}"
                
                class_details.append(class_info)

        relationship_details = []
        for rel in relationships:
            if isinstance(rel, dict):
                rel_type = rel.get('type', rel.get('relationship_type', 'Unknown'))
                source = rel.get('source_id', 'Unknown')
                target = rel.get('target_id', 'Unknown')
                source_mult = rel.get('source_multiplicity', '1')
                target_mult = rel.get('target_multiplicity', '1')

                source_name = source
                target_name = target
                for cls in classes:
                    if cls.get('id') == source:
                        source_name = cls.get('name', cls.get('label', source))
                    if cls.get('id') == target:
                        target_name = cls.get('name', cls.get('label', target))
                
                relationship_details.append(f"  * {source_name} --[{rel_type}]-> {target_name} ({source_mult}:{target_mult})")

        complexity = "Simple"
        total_attributes = sum(len(cls.get('attributes', [])) for cls in classes if isinstance(cls, dict))
        if len(classes) > 10 or total_attributes > 30:
            complexity = "Complejo"
        elif len(classes) > 5 or total_attributes > 15:
            complexity = "Moderado"

        context = f"""
        CONTEXTO DEL DIAGRAMA ACTUAL:
        
        INFORMACIÓN GENERAL:
        - Título: "{diagram_data.get('title', 'Sin título')}"
        - Tipo: {diagram_data.get('diagram_type', 'CLASS')}
        - Nivel de complejidad: {complexity}
        - Última modificación: {diagram_data.get('last_modified', 'Desconocida')}
        - Sesiones activas: {len(active_sessions)} usuarios colaborando
        
        CLASES DEFINIDAS ({len(classes)}):
        {chr(10).join(class_details) if class_details else '  * No hay clases definidas todavía'}
        
        RELACIONES ({len(relationships)}):
        {chr(10).join(relationship_details) if relationship_details else '  * No hay relaciones definidas todavía'}
        
        OBSERVACIONES:
        - Total de atributos en el sistema: {sum(len(cls.get('attributes', [])) for cls in classes if isinstance(cls, dict))}
        - Total de métodos en el sistema: {sum(len(cls.get('methods', [])) for cls in classes if isinstance(cls, dict))}
        - Clases abstractas: {sum(1 for cls in classes if isinstance(cls, dict) and cls.get('isAbstract', False))}
        """
        
        return context
    
    def _select_prompt_template(self, context_type: str, user_question: str, diagram_context: str) -> str:
        """Select appropriate prompt template based on context type."""
        
        if context_type == "diagram" and diagram_context:
            return f"""
            {diagram_context}
            
            PREGUNTA DEL USUARIO: {user_question}
            
            Analiza el diagrama actual y proporciona consejos específicos.
            Sugiere mejoras o explica conceptos relacionados con este diagrama.
            Responde en el idioma del usuario con instrucciones prácticas y específicas.
            """
        else:  # general help
            return f"""
            PREGUNTA DEL USUARIO: {user_question}
            
            Proporciona ayuda general sobre el sistema de diagramas UML colaborativo.
            Enfócate en pasos prácticos y funcionalidades del sistema.
            
            Temas que puedes cubrir:
            - Navegación del sistema
            - Creación y edición de diagramas
            - Funciones de colaboración en tiempo real
            - Generación de código SpringBoot
            - Mejores prácticas de UML
            - Resolución de problemas comunes
            
            Responde en el idioma del usuario de manera clara y práctica.
            """
    
    def _format_response(self, ai_response: str, context_type: str, diagram_data: Optional[Dict]) -> Dict:
        """Format AI response into structured output."""

        suggestions = self._generate_suggestions(context_type, diagram_data)

        related_features = self._generate_related_features(context_type, diagram_data)
        
        return {
            "answer": ai_response,
            "suggestions": suggestions,
            "related_features": related_features,
            "context_type": context_type,
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_suggestions(self, context_type: str, diagram_data: Optional[Dict]) -> List[str]:
        """Generate contextual suggestions based on current state."""
        suggestions = []
        
        if context_type == "diagram" and diagram_data:
            classes = diagram_data.get('classes', [])
            relationships = diagram_data.get('relationships', [])
            
            if len(classes) == 0:
                suggestions.append("Crear tu primera clase UML")
                suggestions.append("Usar plantilla de diagrama")
            elif len(classes) > 0 and len(relationships) == 0:
                suggestions.append("Añadir relaciones entre clases")
                suggestions.append("Definir herencia o asociación")
            else:
                suggestions.append("Generar código SpringBoot")
                suggestions.append("Exportar a PlantUML")
                suggestions.append("Invitar colaboradores")
        
        elif context_type == "code-generation":
            suggestions.extend([
                "Revisar estructura de clases",
                "Validar relaciones UML",
                "Configurar propiedades del proyecto",
                "Descargar código generado"
            ])
        
        else:  # general
            suggestions.extend([
                "Explorar ejemplos de diagramas",
                "Probar colaboración en tiempo real",
                "Aprender atajos de teclado",
                "Ver guía de mejores prácticas"
            ])
        
        return suggestions[:4]  # Limit to 4 suggestions
    
    def _generate_related_features(self, context_type: str, diagram_data: Optional[Dict]) -> List[str]:
        """Generate list of related system features."""
        
        base_features = ["uml_editing", "real_time_collaboration", "chat_system"]
        
        if context_type == "diagram":
            return base_features + ["plantuml_export", "diagram_validation"]
        elif context_type == "code-generation":
            return base_features + ["springboot_generation", "project_download"]
        else:
            return base_features + ["diagram_templates", "system_help"]
    
    def get_system_statistics(self) -> Dict:
        """Get system statistics for AI context."""
        try:
            total_diagrams = UMLDiagram.objects.count()
            recent_diagrams = UMLDiagram.objects.filter(
                created_at__gte=datetime.now().replace(hour=0, minute=0, second=0)
            ).count()
            
            return {
                "total_diagrams": total_diagrams,
                "diagrams_today": recent_diagrams,
                "system_status": "operational"
            }
        except Exception as e:
            self.logger.error(f"Error getting system statistics: {e}")
            return {
                "total_diagrams": 0,
                "diagrams_today": 0,
                "system_status": "unknown"
            }
    
    def get_diagram_analysis(self, diagram_id: str) -> Dict:
        """Get detailed analysis of a specific diagram for AI context."""
        diagram_data = self._get_diagram_data(diagram_id)
        if not diagram_data:
            return {"error": "Diagram not found"}
        
        classes = diagram_data.get('classes', [])
        relationships = diagram_data.get('relationships', [])
        
        analysis = {
            "complexity_score": min(len(classes) * 2 + len(relationships), 100),
            "completeness": "high" if len(classes) > 3 and len(relationships) > 2 else "medium" if len(classes) > 1 else "low",
            "springboot_ready": len(classes) > 0 and any(cls.get('attributes') for cls in classes if isinstance(cls, dict)),
            "collaboration_active": len(diagram_data.get('active_sessions', [])) > 1,
            "recommendations": []
        }

        if analysis["complexity_score"] < 20:
            analysis["recommendations"].append("Considerar añadir más clases o relaciones")
        if not analysis["springboot_ready"]:
            analysis["recommendations"].append("Definir atributos en las clases para generación de código")
        if not analysis["collaboration_active"]:
            analysis["recommendations"].append("Invitar colaboradores para trabajo en equipo")
        
        return analysis
