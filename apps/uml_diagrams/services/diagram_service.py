"""
Diagram auto-creation service for anonymous WebSocket consumers.
"""

import uuid
from typing import Optional
from django.core.exceptions import ValidationError
from ..models import UMLDiagram


class DiagramAutoCreationService:
    """Service for auto-creating diagrams in WebSocket consumers."""
    
    @staticmethod
    def get_or_create_diagram(diagram_id: str, session_id: str) -> Optional[UMLDiagram]:
        """
        Get existing diagram or create new one with enhanced validation.
        
        Args:
            diagram_id: The diagram ID from WebSocket URL
            session_id: Current session ID
            
        Returns:
            UMLDiagram instance or None if creation fails
        """
        try:
            # Handle local/temporary IDs
            if diagram_id.startswith('local_'):
                return DiagramAutoCreationService._create_new_diagram(session_id)
            
            # Validate UUID format
            try:
                uuid.UUID(diagram_id)
                valid_uuid = diagram_id
            except ValueError:
                # Invalid UUID - create new one
                return DiagramAutoCreationService._create_new_diagram(session_id)
            
            # Try to get existing diagram or create new one
            diagram, created = UMLDiagram.objects.get_or_create(
                id=valid_uuid,
                defaults={
                    'title': f'Collaborative Diagram {valid_uuid[:8]}',
                    'description': 'Auto-created for WebSocket collaboration',
                    'diagram_type': 'CLASS',
                    'content': DiagramAutoCreationService._get_default_content(),
                    'layout_config': DiagramAutoCreationService._get_default_layout(),
                    'session_id': session_id,
                    'active_sessions': []
                }
            )
            
            return diagram
            
        except Exception as e:
            print(f"Error in get_or_create_diagram: {e}")
            return DiagramAutoCreationService._create_new_diagram(session_id)
    
    @staticmethod
    def _create_new_diagram(session_id: str) -> UMLDiagram:
        """Create a new diagram with generated UUID."""
        new_uuid = str(uuid.uuid4())
        
        diagram = UMLDiagram.objects.create(
            id=new_uuid,
            title=f'Anonymous Diagram {new_uuid[:8]}',
            description='Auto-created anonymous diagram',
            diagram_type='CLASS',
            content=DiagramAutoCreationService._get_default_content(),
            layout_config=DiagramAutoCreationService._get_default_layout(),
            session_id=session_id,
            active_sessions=[]
        )
        
        return diagram
    
    @staticmethod
    def _get_default_content() -> dict:
        """Get default UML diagram content."""
        return {
            'classes': [],
            'relationships': [],
            'version': '1.0'
        }
    
    @staticmethod
    def _get_default_layout() -> dict:
        """Get default layout configuration."""
        return {
            'zoom': 1.0,
            'pan': {'x': 0, 'y': 0},
            'grid': True,
            'snap': True
        }
    
    @staticmethod
    def validate_and_normalize_diagram_id(diagram_id: str) -> str:
        """
        Validate and normalize diagram ID.
        
        Args:
            diagram_id: Original diagram ID
            
        Returns:
            Valid UUID string
        """
        if diagram_id.startswith('local_'):
            return str(uuid.uuid4())
        
        try:
            # Validate UUID format
            uuid.UUID(diagram_id)
            return diagram_id
        except ValueError:
            # Generate new UUID for invalid format
            return str(uuid.uuid4())
