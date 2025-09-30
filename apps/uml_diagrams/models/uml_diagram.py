"""
Anonymous UML Diagram model for collaborative UML diagram creation.
"""

from django.db import models
from django.utils import timezone
import uuid
import json
from typing import Dict, List, Optional


class UMLDiagram(models.Model):
    """
    Anonymous UML diagram with session-based tracking and auto-cleanup.
    """
    
    class DiagramType(models.TextChoices):
        CLASS = 'CLASS', 'Class Diagram'
        SEQUENCE = 'SEQUENCE', 'Sequence Diagram'
        USE_CASE = 'USE_CASE', 'Use Case Diagram'
        ACTIVITY = 'ACTIVITY', 'Activity Diagram'
        STATE = 'STATE', 'State Diagram'
        COMPONENT = 'COMPONENT', 'Component Diagram'
        DEPLOYMENT = 'DEPLOYMENT', 'Deployment Diagram'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, default="Untitled Diagram")
    description = models.TextField(blank=True)

    session_id = models.CharField(
        max_length=64, 
        db_index=True,
        help_text="Session ID of the creator/last editor"
    )

    diagram_type = models.CharField(
        max_length=15,
        choices=DiagramType.choices,
        default=DiagramType.CLASS
    )
    content = models.JSONField(
        default=dict,
        help_text="Complete UML diagram structure and elements"
    )
    layout_config = models.JSONField(
        default=dict,
        help_text="Diagram layout and positioning"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    active_sessions = models.JSONField(
        default=list,
        help_text="List of currently active sessions viewing/editing"
    )
    
    class Meta:
        db_table = 'uml_diagrams'
        ordering = ['-last_modified']
        indexes = [
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_modified']),
            models.Index(fields=['diagram_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_diagram_type_display()}) - Session: {self.session_id[:8]}"
    
    def save(self, *args, **kwargs):
        """Override save to ensure consistency and normalize diagram_type."""

        if self.diagram_type:
            self.diagram_type = self.diagram_type.upper()
        super().save(*args, **kwargs)
    
    @classmethod
    def normalize_diagram_type(cls, diagram_type):
        """Normalize diagram_type to handle case-insensitive input."""
        if not diagram_type:
            return cls.DiagramType.CLASS

        normalized = diagram_type.upper()
        valid_types = [choice[0] for choice in cls.DiagramType.choices]
        
        if normalized in valid_types:
            return normalized

        type_aliases = {
            'CLASS': 'CLASS',
            'SEQUENCE': 'SEQUENCE', 
            'USECASE': 'USE_CASE',
            'USE-CASE': 'USE_CASE',
            'ACTIVITY': 'ACTIVITY',
            'STATE': 'STATE',
            'COMPONENT': 'COMPONENT',
            'DEPLOYMENT': 'DEPLOYMENT'
        }
        
        return type_aliases.get(normalized, cls.DiagramType.CLASS)
    
    def get_classes(self) -> List[Dict]:
        """Extract UML classes from diagram data."""
        if not self.content:
            return []

        classes = self.content.get('classes', [])
        if not classes:

            nodes = self.content.get('nodes', [])
            classes = [
                {
                    'id': node.get('id'),
                    'name': node.get('data', {}).get('label', 'Unknown'),
                    'label': node.get('data', {}).get('label', 'Unknown'),
                    'attributes': node.get('data', {}).get('attributes', []),
                    'methods': node.get('data', {}).get('methods', []),
                    'nodeType': node.get('data', {}).get('nodeType', 'class'),
                    'isAbstract': node.get('data', {}).get('isAbstract', False)
                }
                for node in nodes if node.get('type') == 'class'
            ]
        return classes
    
    def get_relationships(self) -> List[Dict]:
        """Extract UML relationships from diagram data."""
        if not self.content:
            return []

        relationships = self.content.get('relationships', [])
        if not relationships:

            edges = self.content.get('edges', [])
            relationships = [
                {
                    'id': edge.get('id'),
                    'source_id': edge.get('source'),
                    'target_id': edge.get('target'),
                    'type': edge.get('data', {}).get('relationshipType', 'ASSOCIATION'),
                    'relationship_type': edge.get('data', {}).get('relationshipType', 'ASSOCIATION'),
                    'source_multiplicity': edge.get('data', {}).get('sourceMultiplicity', '1'),
                    'target_multiplicity': edge.get('data', {}).get('targetMultiplicity', '1'),
                    'label': edge.get('data', {}).get('label', '')
                }
                for edge in edges if edge.get('type') == 'umlRelationship'
            ]
        return relationships
    
    def add_class(self, class_data: Dict) -> None:
        """Add UML class to diagram."""
        classes = self.get_classes()
        classes.append(class_data)
        self.content['classes'] = classes
        self.save()
    
    def update_class(self, class_id: str, class_data: Dict) -> bool:
        """Update existing UML class."""
        classes = self.get_classes()
        for i, cls in enumerate(classes):
            if cls.get('id') == class_id:
                classes[i] = {**cls, **class_data}
                self.content['classes'] = classes
                self.save()
                return True
        return False
    
    def remove_class(self, class_id: str) -> bool:
        """Remove UML class from diagram."""
        classes = self.get_classes()
        original_count = len(classes)
        classes = [cls for cls in classes if cls.get('id') != class_id]
        
        if len(classes) < original_count:
            self.content['classes'] = classes

            self.remove_relationships_for_class(class_id)
            self.save()
            return True
        return False
    
    def add_relationship(self, relationship_data: Dict) -> None:
        """Add UML relationship to diagram."""
        relationships = self.get_relationships()
        relationships.append(relationship_data)
        self.content['relationships'] = relationships
        self.save()
    
    def remove_relationships_for_class(self, class_id: str) -> None:
        """Remove all relationships involving a specific class."""
        relationships = self.get_relationships()
        relationships = [
            rel for rel in relationships
            if rel.get('source_id') != class_id and rel.get('target_id') != class_id
        ]
        self.content['relationships'] = relationships
    
    def export_to_plantuml(self) -> str:
        """Export diagram to PlantUML format."""
        from ..services import PlantUMLExporter
        
        exporter = PlantUMLExporter()
        return exporter.export_diagram(self)
    
    def get_element_by_id(self, element_id: str) -> Optional[Dict]:
        """Find diagram element by ID."""

        for cls in self.get_classes():
            if cls.get('id') == element_id:
                return cls

        for rel in self.get_relationships():
            if rel.get('id') == element_id:
                return rel
        
        return None
    
    def update_element(self, element_id: str, element_data: Dict) -> bool:
        """Update any diagram element by ID."""

        if self.update_class(element_id, element_data):
            return True

        relationships = self.get_relationships()
        for i, rel in enumerate(relationships):
            if rel.get('id') == element_id:
                relationships[i] = {**rel, **element_data}
                self.content['relationships'] = relationships
                self.save()
                return True
        
        return False
    
    def add_active_session(self, session_id: str, nickname: str = None) -> None:
        """Add session to active sessions list."""
        if not isinstance(self.active_sessions, list):
            self.active_sessions = []

        self.active_sessions = [
            s for s in self.active_sessions 
            if s.get('session_id') != session_id
        ]

        self.active_sessions.append({
            'session_id': session_id,
            'nickname': nickname or f"Guest_{session_id[:8]}",
            'joined_at': timezone.now().isoformat()
        })
        
        self.save(update_fields=['active_sessions'])
    
    def remove_active_session(self, session_id: str) -> None:
        """Remove session from active sessions list."""
        if not isinstance(self.active_sessions, list):
            return
        
        self.active_sessions = [
            s for s in self.active_sessions 
            if s.get('session_id') != session_id
        ]
        
        self.save(update_fields=['active_sessions'])
    
    def get_active_sessions_count(self) -> int:
        """Get count of currently active sessions (filtered by last 10 minutes)."""
        if not isinstance(self.active_sessions, list):
            return 0

        from datetime import timedelta
        cutoff_time = timezone.now() - timedelta(minutes=10)
        
        active_count = 0
        for session in self.active_sessions:
            joined_at_str = session.get('joined_at')
            if joined_at_str:
                try:
                    from dateutil import parser
                    joined_at = parser.parse(joined_at_str)
                    if joined_at.tzinfo is None:
                        joined_at = timezone.make_aware(joined_at)
                    
                    if joined_at >= cutoff_time:
                        active_count += 1
                except (ValueError, AttributeError):

                    pass
        
        return active_count
    
    def clone_diagram(self, new_session_id: str, new_title: str = None) -> 'UMLDiagram':
        """Create copy of diagram for new session."""
        clone = UMLDiagram.objects.create(
            title=new_title or f"Copy of {self.title}",
            description=f"Clone of {self.description}",
            session_id=new_session_id,
            diagram_type=self.diagram_type,
            content=self.content.copy() if self.content else {},
            layout_config=self.layout_config.copy() if self.layout_config else {}
        )
        return clone
    
    @classmethod
    def get_recent_diagrams(cls, limit: int = 20) -> models.QuerySet:
        """Get recently modified diagrams."""
        return cls.objects.order_by('-last_modified')[:limit]
    
    @classmethod
    def cleanup_old_diagrams(cls, days: int = 30) -> int:
        """Delete diagrams older than specified days."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        count = cls.objects.filter(created_at__lt=cutoff_date).count()
        cls.objects.filter(created_at__lt=cutoff_date).delete()
        return count
    
    @classmethod
    def get_session_diagrams(cls, session_id: str) -> models.QuerySet:
        """Get diagrams created by a specific session."""
        return cls.objects.filter(session_id=session_id).order_by('-last_modified')
