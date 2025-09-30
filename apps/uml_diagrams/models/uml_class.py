"""
UMLClass model for individual UML class elements with comprehensive attribute and method management.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class UMLClass(models.Model):
    """
    Individual UML class element with detailed attribute and method definitions.
    """
    
    class ClassType(models.TextChoices):
        CLASS = 'CLASS', 'Class'
        ABSTRACT_CLASS = 'ABSTRACT_CLASS', 'Abstract Class'
        INTERFACE = 'INTERFACE', 'Interface'
        ENUM = 'ENUM', 'Enumeration'
        RECORD = 'RECORD', 'Record'
    
    class Visibility(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public (+)'
        PRIVATE = 'PRIVATE', 'Private (-)'
        PROTECTED = 'PROTECTED', 'Protected (#)'
        PACKAGE = 'PACKAGE', 'Package (~)'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='classes'
    )
    name = models.CharField(max_length=255)
    package = models.CharField(max_length=500, blank=True)
    class_type = models.CharField(
        max_length=20,
        choices=ClassType.choices,
        default=ClassType.CLASS
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PUBLIC
    )
    is_abstract = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False)
    is_static = models.BooleanField(default=False)
    stereotype = models.CharField(max_length=100, blank=True)
    documentation = models.TextField(blank=True)
    attributes = models.JSONField(default=list)
    methods = models.JSONField(default=list)
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    width = models.FloatField(default=120.0)
    height = models.FloatField(default=80.0)
    style_config = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_classes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'uml_classes'
        ordering = ['name']
        indexes = [
            models.Index(fields=['diagram', 'name']),
            models.Index(fields=['class_type', 'diagram']),
            models.Index(fields=['package', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['diagram', 'name', 'package'],
                name='unique_class_per_diagram'
            )
        ]
    
    def __str__(self):
        return f"{self.package}.{self.name}" if self.package else self.name
    
    def add_attribute(self, name: str, data_type: str, visibility: str = 'PRIVATE',
                     is_static: bool = False, is_final: bool = False,
                     default_value: str = None) -> None:
        """Add attribute to UML class."""
        attribute = {
            'id': str(uuid.uuid4()),
            'name': name,
            'type': data_type,
            'visibility': visibility,
            'is_static': is_static,
            'is_final': is_final,
            'default_value': default_value,
            'documentation': '',
            'annotations': []
        }
        
        self.attributes.append(attribute)
        self.save(update_fields=['attributes'])
    
    def add_method(self, name: str, return_type: str = 'void', 
                  visibility: str = 'PUBLIC', is_static: bool = False,
                  is_abstract: bool = False, parameters: list = None) -> None:
        """Add method to UML class."""
        method = {
            'id': str(uuid.uuid4()),
            'name': name,
            'return_type': return_type,
            'visibility': visibility,
            'is_static': is_static,
            'is_abstract': is_abstract,
            'is_final': False,
            'parameters': parameters or [],
            'documentation': '',
            'annotations': [],
            'exceptions': []
        }
        
        self.methods.append(method)
        self.save(update_fields=['methods'])
    
    def update_attribute(self, attribute_id: str, **kwargs) -> bool:
        """Update existing attribute."""
        for attr in self.attributes:
            if attr.get('id') == attribute_id:
                attr.update(kwargs)
                self.save(update_fields=['attributes'])
                return True
        return False
    
    def update_method(self, method_id: str, **kwargs) -> bool:
        """Update existing method."""
        for method in self.methods:
            if method.get('id') == method_id:
                method.update(kwargs)
                self.save(update_fields=['methods'])
                return True
        return False
    
    def remove_attribute(self, attribute_id: str) -> bool:
        """Remove attribute from class."""
        original_count = len(self.attributes)
        self.attributes = [attr for attr in self.attributes if attr.get('id') != attribute_id]
        
        if len(self.attributes) < original_count:
            self.save(update_fields=['attributes'])
            return True
        return False
    
    def remove_method(self, method_id: str) -> bool:
        """Remove method from class."""
        original_count = len(self.methods)
        self.methods = [method for method in self.methods if method.get('id') != method_id]
        
        if len(self.methods) < original_count:
            self.save(update_fields=['methods'])
            return True
        return False
    
    def get_springboot_entity_data(self) -> dict:
        """Generate SpringBoot entity mapping data."""
        return {
            'class_name': self.name,
            'package_name': self.package or 'com.enterprise.generated.entities',
            'table_name': self.name.lower(),
            'attributes': [
                {
                    'name': attr['name'],
                    'type': self.map_uml_type_to_java(attr['type']),
                    'column_name': attr['name'].lower(),
                    'is_primary_key': attr.get('name') == 'id',
                    'is_nullable': not attr.get('is_final', False),
                    'annotations': self.generate_jpa_annotations(attr)
                }
                for attr in self.attributes
            ],
            'methods': [
                {
                    'name': method['name'],
                    'return_type': self.map_uml_type_to_java(method['return_type']),
                    'parameters': method.get('parameters', []),
                    'visibility': method['visibility'].lower(),
                    'annotations': method.get('annotations', [])
                }
                for method in self.methods
            ],
            'annotations': self.get_class_annotations(),
            'imports': self.get_required_imports()
        }
    
    def map_uml_type_to_java(self, uml_type: str) -> str:
        """Map UML data types to Java types."""
        type_mapping = {
            'String': 'String',
            'Integer': 'Integer',
            'Long': 'Long',
            'Double': 'Double',
            'Float': 'Float',
            'Boolean': 'Boolean',
            'Date': 'LocalDateTime',
            'LocalDate': 'LocalDate',
            'LocalTime': 'LocalTime',
            'BigDecimal': 'BigDecimal',
            'UUID': 'UUID',
            'List': 'List',
            'Set': 'Set',
            'Map': 'Map'
        }
        return type_mapping.get(uml_type, uml_type)
    
    def generate_jpa_annotations(self, attribute: dict) -> list:
        """Generate JPA annotations for attribute."""
        annotations = []
        
        if attribute.get('name') == 'id':
            annotations.extend(['@Id', '@GeneratedValue(strategy = GenerationType.IDENTITY)'])
        
        if attribute.get('is_final'):
            annotations.append('@Column(nullable = false)')
        
        if attribute.get('name') in ['created_at', 'updated_at']:
            if 'created' in attribute.get('name'):
                annotations.append('@CreationTimestamp')
            else:
                annotations.append('@UpdateTimestamp')
        
        return annotations
    
    def get_class_annotations(self) -> list:
        """Get JPA annotations for the class."""
        annotations = ['@Entity']
        
        if self.name.lower() != self.name:
            annotations.append(f'@Table(name = "{self.name.lower()}")')
        
        return annotations
    
    def get_required_imports(self) -> list:
        """Get required imports for SpringBoot entity."""
        imports = [
            'javax.persistence.*',
            'org.hibernate.annotations.CreationTimestamp',
            'org.hibernate.annotations.UpdateTimestamp',
            'java.time.LocalDateTime'
        ]

        for attr in self.attributes:
            attr_type = attr.get('type', '')
            if 'UUID' in attr_type:
                imports.append('java.util.UUID')
            elif 'List' in attr_type or 'Set' in attr_type:
                imports.append('java.util.*')
            elif 'BigDecimal' in attr_type:
                imports.append('java.math.BigDecimal')
        
        return list(set(imports))
    
    def get_full_class_name(self) -> str:
        """Get fully qualified class name."""
        return f"{self.package}.{self.name}" if self.package else self.name
