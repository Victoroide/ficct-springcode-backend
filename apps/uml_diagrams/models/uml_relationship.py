"""
UMLRelationship model for managing relationships between UML classes.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class UMLRelationship(models.Model):
    """
    UML relationships between classes with comprehensive relationship types and properties.
    """
    
    class RelationshipType(models.TextChoices):
        ASSOCIATION = 'ASSOCIATION', 'Association'
        AGGREGATION = 'AGGREGATION', 'Aggregation'
        COMPOSITION = 'COMPOSITION', 'Composition'
        INHERITANCE = 'INHERITANCE', 'Inheritance'
        REALIZATION = 'REALIZATION', 'Realization'
        DEPENDENCY = 'DEPENDENCY', 'Dependency'
        GENERALIZATION = 'GENERALIZATION', 'Generalization'
    
    class Multiplicity(models.TextChoices):
        ZERO_ONE = '0..1', '0..1'
        ONE = '1', '1'
        ZERO_MANY = '0..*', '0..*'
        ONE_MANY = '1..*', '1..*'
        MANY = '*', '*'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='relationships'
    )
    name = models.CharField(max_length=255, blank=True)
    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        default=RelationshipType.ASSOCIATION
    )
    source_class = models.ForeignKey(
        'uml_diagrams.UMLClass',
        on_delete=models.CASCADE,
        related_name='outgoing_relationships'
    )
    target_class = models.ForeignKey(
        'uml_diagrams.UMLClass',
        on_delete=models.CASCADE,
        related_name='incoming_relationships'
    )
    source_multiplicity = models.CharField(
        max_length=10,
        choices=Multiplicity.choices,
        default=Multiplicity.ONE
    )
    target_multiplicity = models.CharField(
        max_length=10,
        choices=Multiplicity.choices,
        default=Multiplicity.ONE
    )
    source_role = models.CharField(max_length=100, blank=True)
    target_role = models.CharField(max_length=100, blank=True)
    source_navigable = models.BooleanField(default=True)
    target_navigable = models.BooleanField(default=True)
    documentation = models.TextField(blank=True)
    stereotype = models.CharField(max_length=100, blank=True)
    style_config = models.JSONField(default=dict)
    path_points = models.JSONField(
        default=list,
        help_text="Connection path points for visual representation"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_relationships'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'uml_relationships'
        ordering = ['name', 'relationship_type']
        indexes = [
            models.Index(fields=['diagram', 'relationship_type']),
            models.Index(fields=['source_class', 'target_class']),
            models.Index(fields=['relationship_type', 'diagram']),
        ]
    
    def __str__(self):
        return (f"{self.source_class.name} {self.get_relationship_type_display()} "
                f"{self.target_class.name}")
    
    def get_springboot_mapping(self) -> dict:
        """Generate SpringBoot JPA relationship mapping."""
        mapping = {
            'relationship_type': self.relationship_type,
            'source_class': self.source_class.name,
            'target_class': self.target_class.name,
            'source_field_name': self.get_source_field_name(),
            'target_field_name': self.get_target_field_name(),
            'jpa_annotations': self.get_jpa_annotations(),
            'fetch_type': self.get_fetch_type(),
            'cascade_options': self.get_cascade_options()
        }
        
        return mapping
    
    def get_source_field_name(self) -> str:
        """Generate field name for source class."""
        if self.source_role:
            return self.source_role
        
        # Default naming based on relationship type
        if self.relationship_type in ['ASSOCIATION', 'AGGREGATION', 'COMPOSITION']:
            if self.target_multiplicity in ['0..*', '1..*', '*']:
                return f"{self.target_class.name.lower()}s"
            else:
                return self.target_class.name.lower()
        
        return f"{self.target_class.name.lower()}"
    
    def get_target_field_name(self) -> str:
        """Generate field name for target class."""
        if self.target_role:
            return self.target_role
        
        # Default naming for bidirectional relationships
        if self.target_navigable:
            if self.source_multiplicity in ['0..*', '1..*', '*']:
                return f"{self.source_class.name.lower()}s"
            else:
                return self.source_class.name.lower()
        
        return None
    
    def get_jpa_annotations(self) -> dict:
        """Generate JPA annotations for relationship."""
        annotations = {
            'source': [],
            'target': []
        }
        
        if self.relationship_type == 'INHERITANCE':
            # Handle inheritance relationships
            annotations['target'].append('@Inheritance(strategy = InheritanceType.JOINED)')
            return annotations
        
        # Determine JPA relationship type
        if self.relationship_type in ['ASSOCIATION', 'DEPENDENCY']:
            if self.is_one_to_many():
                annotations['source'].append('@OneToMany')
                if self.target_navigable:
                    annotations['target'].append('@ManyToOne')
            elif self.is_many_to_many():
                annotations['source'].append('@ManyToMany')
                if self.target_navigable:
                    annotations['target'].append('@ManyToMany(mappedBy = "' + self.get_source_field_name() + '")')
            else:
                annotations['source'].append('@OneToOne')
                if self.target_navigable:
                    annotations['target'].append('@OneToOne(mappedBy = "' + self.get_source_field_name() + '")')
        
        elif self.relationship_type == 'COMPOSITION':
            annotations['source'].append('@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)')
            if self.target_navigable:
                annotations['target'].append('@ManyToOne')
        
        elif self.relationship_type == 'AGGREGATION':
            annotations['source'].append('@OneToMany')
            if self.target_navigable:
                annotations['target'].append('@ManyToOne')
        
        # Add fetch type
        fetch_type = self.get_fetch_type()
        if fetch_type != 'LAZY':  # LAZY is default
            for key in annotations:
                if annotations[key]:
                    annotations[key][-1] = annotations[key][-1].replace(')', f', fetch = FetchType.{fetch_type})')
        
        return annotations
    
    def get_fetch_type(self) -> str:
        """Determine optimal fetch type for relationship."""
        if self.relationship_type in ['COMPOSITION', 'AGGREGATION']:
            return 'LAZY'
        elif self.is_many_to_many() or self.is_one_to_many():
            return 'LAZY'
        else:
            return 'EAGER'  # For @OneToOne and @ManyToOne
    
    def get_cascade_options(self) -> list:
        """Determine cascade options for relationship."""
        if self.relationship_type == 'COMPOSITION':
            return ['CascadeType.ALL']
        elif self.relationship_type == 'AGGREGATION':
            return ['CascadeType.PERSIST', 'CascadeType.MERGE']
        else:
            return []
    
    def is_one_to_many(self) -> bool:
        """Check if relationship is one-to-many."""
        return (self.source_multiplicity in ['1', '0..1'] and 
                self.target_multiplicity in ['0..*', '1..*', '*'])
    
    def is_many_to_one(self) -> bool:
        """Check if relationship is many-to-one."""
        return (self.source_multiplicity in ['0..*', '1..*', '*'] and 
                self.target_multiplicity in ['1', '0..1'])
    
    def is_many_to_many(self) -> bool:
        """Check if relationship is many-to-many."""
        return (self.source_multiplicity in ['0..*', '1..*', '*'] and 
                self.target_multiplicity in ['0..*', '1..*', '*'])
    
    def is_one_to_one(self) -> bool:
        """Check if relationship is one-to-one."""
        return (self.source_multiplicity in ['1', '0..1'] and 
                self.target_multiplicity in ['1', '0..1'])
    
    def get_java_field_type(self, is_source: bool = True) -> str:
        """Get Java field type for relationship."""
        target_class_name = self.target_class.name if is_source else self.source_class.name
        multiplicity = self.target_multiplicity if is_source else self.source_multiplicity
        
        if multiplicity in ['0..*', '1..*', '*']:
            return f"List<{target_class_name}>"
        else:
            return target_class_name
    
    def validate_relationship(self) -> dict:
        """Validate relationship consistency and best practices."""
        errors = []
        warnings = []
        
        # Check for circular inheritance
        if self.relationship_type == 'INHERITANCE':
            if self.creates_inheritance_cycle():
                errors.append("Circular inheritance detected")
        
        # Check multiplicity consistency
        if self.relationship_type == 'COMPOSITION' and self.is_many_to_many():
            warnings.append("Many-to-many composition is unusual and may indicate design issue")
        
        # Check navigability
        if not self.source_navigable and not self.target_navigable:
            warnings.append("Non-navigable relationship may be unnecessary")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def creates_inheritance_cycle(self) -> bool:
        """Check if this inheritance relationship creates a cycle."""
        if self.relationship_type != 'INHERITANCE':
            return False
        
        # Simple cycle detection - check if target inherits from source
        visited = set()
        current = self.target_class
        
        while current and current.id not in visited:
            visited.add(current.id)
            
            # Find parent class
            parent_rel = UMLRelationship.objects.filter(
                diagram=self.diagram,
                relationship_type='INHERITANCE',
                source_class=current
            ).first()
            
            if parent_rel:
                if parent_rel.target_class == self.source_class:
                    return True
                current = parent_rel.target_class
            else:
                break
        
        return False
