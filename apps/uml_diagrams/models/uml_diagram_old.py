"""
UMLDiagram model for managing enterprise UML diagram structure and metadata.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import json
from typing import Dict, List, Optional

User = get_user_model()


class UMLDiagram(models.Model):
    """
    Enterprise UML diagram with comprehensive metadata and version control.
    """
    
    class DiagramType(models.TextChoices):
        CLASS = 'CLASS', 'Class Diagram'
        SEQUENCE = 'SEQUENCE', 'Sequence Diagram'
        USE_CASE = 'USE_CASE', 'Use Case Diagram'
        ACTIVITY = 'ACTIVITY', 'Activity Diagram'
        STATE = 'STATE', 'State Diagram'
        COMPONENT = 'COMPONENT', 'Component Diagram'
        DEPLOYMENT = 'DEPLOYMENT', 'Deployment Diagram'
    
    class DiagramStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        APPROVED = 'APPROVED', 'Approved'
        DEPRECATED = 'DEPRECATED', 'Deprecated'
    
    class VisibilityLevel(models.TextChoices):
        PRIVATE = 'PRIVATE', 'Private'
        TEAM = 'TEAM', 'Team'
        ORGANIZATION = 'ORGANIZATION', 'Organization'
        PUBLIC = 'PUBLIC', 'Public'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uml_diagrams',
        help_text="Owner of the UML diagram"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    diagram_type = models.CharField(
        max_length=15,
        choices=DiagramType.choices,
        default=DiagramType.CLASS
    )
    status = models.CharField(
        max_length=15,
        choices=DiagramStatus.choices,
        default=DiagramStatus.DRAFT
    )
    visibility = models.CharField(
        max_length=15,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.TEAM
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_diagrams'
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='modified_diagrams'
    )
    diagram_data = models.JSONField(
        default=dict,
        help_text="Complete UML diagram structure and elements"
    )
    layout_config = models.JSONField(
        default=dict,
        help_text="Diagram layout and presentation configuration"
    )
    validation_results = models.JSONField(
        default=dict,
        help_text="Latest validation results and architectural recommendations"
    )
    tags = models.JSONField(
        default=list,
        help_text="Searchable tags for diagram categorization"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional diagram metadata and custom fields"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    version_number = models.PositiveIntegerField(default=1)
    is_template = models.BooleanField(default=False)
    parent_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_diagrams'
    )

    is_public = models.BooleanField(
        default=True,
        help_text="Allow public access without authentication"
    )
    public_edit_url = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text="Unique URL for public editing access"
    )
    
    class Meta:
        db_table = 'uml_diagrams'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['owner', 'diagram_type']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['status', 'updated_at']),
            models.Index(fields=['name', 'owner']),
            models.Index(fields=['is_template', 'diagram_type']),
            models.Index(fields=['is_public', 'visibility']),
            models.Index(fields=['public_edit_url']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_diagram_type_display()}) - {self.owner.corporate_email}"
    
    def save(self, *args, **kwargs):
        """Override save to update version and validation."""
        is_new = self.pk is None

        if not self.public_edit_url:
            self.public_edit_url = uuid.uuid4()

        
        super().save(*args, **kwargs)

    
    def create_version_snapshot(self) -> 'DiagramVersion':
        """Create version snapshot for change tracking."""
        from .diagram_version import DiagramVersion
        
        return DiagramVersion.objects.create(
            diagram=self,
            version_number=self.version_number,
            diagram_data=self.diagram_data,
            layout_config=self.layout_config,
            created_by=self.last_modified_by,
            change_summary=f"Version {self.version_number} auto-save"
        )
    
    def get_classes(self) -> List[Dict]:
        """Extract UML classes from diagram data."""
        if not self.diagram_data:
            return []
        return self.diagram_data.get('classes', [])
    
    def get_relationships(self) -> List[Dict]:
        """Extract UML relationships from diagram data."""
        if not self.diagram_data:
            return []
        return self.diagram_data.get('relationships', [])
    
    def add_class(self, class_data: Dict) -> None:
        """Add UML class to diagram."""
        classes = self.get_classes()
        classes.append(class_data)
        self.diagram_data['classes'] = classes
        self.save()
    
    def update_class(self, class_id: str, class_data: Dict) -> bool:
        """Update existing UML class."""
        classes = self.get_classes()
        for i, cls in enumerate(classes):
            if cls.get('id') == class_id:
                classes[i] = {**cls, **class_data}
                self.diagram_data['classes'] = classes
                self.save()
                return True
        return False
    
    def remove_class(self, class_id: str) -> bool:
        """Remove UML class from diagram."""
        classes = self.get_classes()
        original_count = len(classes)
        classes = [cls for cls in classes if cls.get('id') != class_id]
        
        if len(classes) < original_count:
            self.diagram_data['classes'] = classes

            self.remove_relationships_for_class(class_id)
            self.save()
            return True
        return False
    
    def add_relationship(self, relationship_data: Dict) -> None:
        """Add UML relationship to diagram."""
        relationships = self.get_relationships()
        relationships.append(relationship_data)
        self.diagram_data['relationships'] = relationships
        self.save()
    
    def remove_relationships_for_class(self, class_id: str) -> None:
        """Remove all relationships involving a specific class."""
        relationships = self.get_relationships()
        relationships = [
            rel for rel in relationships
            if rel.get('source_id') != class_id and rel.get('target_id') != class_id
        ]
        self.diagram_data['relationships'] = relationships
    
    def validate_diagram(self) -> Dict:
        """Validate diagram structure and architectural patterns."""
        from ..services import UMLValidationService
        
        validation_service = UMLValidationService()
        results = validation_service.validate_diagram(self)
        
        self.validation_results = results
        self.last_validated_at = timezone.now()
        self.save(update_fields=['validation_results', 'last_validated_at'])
        
        return results
    
    def get_springboot_mapping(self) -> Dict:
        """Generate SpringBoot code generation mapping."""
        from ..services import UMLToSpringBootMapper
        
        mapper = UMLToSpringBootMapper()
        return mapper.generate_mapping(self)
    
    def clone_diagram(self, new_name: str, user: User) -> 'UMLDiagram':
        """Create copy of diagram with new name."""
        clone = UMLDiagram.objects.create(
            owner=user,
            name=new_name,
            description=f"Clone of {self.name}",
            diagram_type=self.diagram_type,
            visibility=self.visibility,
            created_by=user,
            last_modified_by=user,
            diagram_data=self.diagram_data.copy(),
            layout_config=self.layout_config.copy(),
            tags=self.tags.copy(),
            parent_template=self if self.is_template else None
        )
        return clone
    
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
                self.diagram_data['relationships'] = relationships
                self.save()
                return True
        
        return False
    
    @classmethod
    def get_user_diagrams(cls, user: User) -> models.QuerySet:
        """Get diagrams accessible to user."""
        queryset = cls.objects.filter(
            models.Q(owner=user) |
            models.Q(created_by=user) |
            models.Q(visibility__in=['TEAM', 'ORGANIZATION', 'PUBLIC'])
        ).distinct()
        
        return queryset
    
    @classmethod
    def get_templates(cls, diagram_type: str = None) -> models.QuerySet:
        """Get available diagram templates."""
        queryset = cls.objects.filter(is_template=True)
        
        if diagram_type:
            queryset = queryset.filter(diagram_type=diagram_type)
        
        return queryset
