"""
ValidationRule model for enterprise architectural pattern validation.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class ValidationRule(models.Model):
    """
    Enterprise architectural validation rules for UML diagrams.
    """
    
    class RuleType(models.TextChoices):
        NAMING_CONVENTION = 'NAMING_CONVENTION', 'Naming Convention'
        ARCHITECTURAL_PATTERN = 'ARCHITECTURAL_PATTERN', 'Architectural Pattern'
        DESIGN_PRINCIPLE = 'DESIGN_PRINCIPLE', 'Design Principle'
        CODE_QUALITY = 'CODE_QUALITY', 'Code Quality'
        SECURITY = 'SECURITY', 'Security'
        PERFORMANCE = 'PERFORMANCE', 'Performance'
    
    class Severity(models.TextChoices):
        ERROR = 'ERROR', 'Error'
        WARNING = 'WARNING', 'Warning'
        INFO = 'INFO', 'Information'
        SUGGESTION = 'SUGGESTION', 'Suggestion'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    rule_type = models.CharField(
        max_length=25,
        choices=RuleType.choices,
        default=RuleType.DESIGN_PRINCIPLE
    )
    severity = models.CharField(
        max_length=15,
        choices=Severity.choices,
        default=Severity.WARNING
    )
    rule_pattern = models.JSONField(
        help_text="Pattern definition for rule matching"
    )
    validation_logic = models.TextField(
        help_text="Python code for validation logic"
    )
    error_message = models.CharField(max_length=500)
    suggestion = models.TextField(blank=True)
    applicable_diagrams = models.JSONField(
        default=list,
        help_text="Diagram types this rule applies to"
    )
    is_active = models.BooleanField(default=True)
    is_system_rule = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_validation_rules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'validation_rules'
        ordering = ['rule_type', 'name']
        indexes = [
            models.Index(fields=['rule_type', 'is_active']),
            models.Index(fields=['severity', 'is_active']),
            models.Index(fields=['is_system_rule', 'rule_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"
    
    def validate_diagram(self, diagram) -> dict:
        """Validate diagram against this rule."""
        try:
            # Create validation context
            context = {
                'diagram': diagram,
                'classes': diagram.get_classes(),
                'relationships': diagram.get_relationships(),
                'validation_helpers': self.get_validation_helpers()
            }
            
            # Execute validation logic  
            exec(self.validation_logic, context)
            
            # Get validation result
            result = context.get('validation_result', {
                'is_valid': True,
                'violations': []
            })
            
            return {
                'rule_id': str(self.id),
                'rule_name': self.name,
                'rule_type': self.rule_type,
                'severity': self.severity,
                'is_valid': result.get('is_valid', True),
                'violations': result.get('violations', []),
                'suggestion': self.suggestion if not result.get('is_valid', True) else None
            }
            
        except Exception as e:
            return {
                'rule_id': str(self.id),
                'rule_name': self.name,
                'rule_type': self.rule_type,
                'severity': 'ERROR',
                'is_valid': False,
                'violations': [f"Rule execution error: {str(e)}"],
                'suggestion': "Please contact administrator about this validation rule"
            }
    
    def get_validation_helpers(self) -> dict:
        """Get helper functions for validation logic."""
        return {
            'is_pascal_case': lambda s: s and s[0].isupper() and '_' not in s,
            'is_camel_case': lambda s: s and s[0].islower() and '_' not in s,
            'is_snake_case': lambda s: s and s.islower() and ' ' not in s,
            'has_pattern': lambda text, pattern: pattern.lower() in text.lower(),
            'count_classes': lambda classes: len(classes),
            'count_relationships': lambda rels: len(rels),
            'get_class_by_name': lambda classes, name: next((c for c in classes if c.get('name') == name), None),
            'get_relationships_for_class': lambda rels, class_id: [r for r in rels if r.get('source_id') == class_id or r.get('target_id') == class_id]
        }
    
    @classmethod
    def get_system_rules(cls) -> list:
        """Get predefined system validation rules."""
        return [
            {
                'name': 'Class Naming Convention',
                'description': 'Classes should use PascalCase naming convention',
                'rule_type': 'NAMING_CONVENTION',
                'severity': 'WARNING',
                'applicable_diagrams': ['CLASS'],
                'validation_logic': '''
violations = []
for cls in classes:
    class_name = cls.get('name', '')
    if not validation_helpers['is_pascal_case'](class_name):
        violations.append(f"Class '{class_name}' should use PascalCase naming")

validation_result = {
    'is_valid': len(violations) == 0,
    'violations': violations
}
''',
                'error_message': 'Class names should follow PascalCase convention',
                'suggestion': 'Use PascalCase for class names (e.g., UserAccount, OrderService)'
            },
            {
                'name': 'Interface Naming Pattern',
                'description': 'Interfaces should be prefixed with "I" or suffixed with "able"',
                'rule_type': 'NAMING_CONVENTION',
                'severity': 'INFO',
                'applicable_diagrams': ['CLASS'],
                'validation_logic': '''
violations = []
for cls in classes:
    if cls.get('class_type') == 'INTERFACE':
        class_name = cls.get('name', '')
        if not (class_name.startswith('I') or class_name.endswith('able') or class_name.endswith('Service')):
            violations.append(f"Interface '{class_name}' should follow naming patterns")

validation_result = {
    'is_valid': len(violations) == 0,
    'violations': violations
}
''',
                'error_message': 'Interfaces should follow standard naming patterns',
                'suggestion': 'Prefix interfaces with "I" or suffix with "able" or "Service"'
            },
            {
                'name': 'Entity Class Pattern',
                'description': 'Entity classes should have ID field and basic CRUD methods',
                'rule_type': 'ARCHITECTURAL_PATTERN',
                'severity': 'WARNING',
                'applicable_diagrams': ['CLASS'],
                'validation_logic': '''
violations = []
entity_indicators = ['Entity', 'Model', 'DO', 'PO']

for cls in classes:
    class_name = cls.get('name', '')
    if any(indicator in class_name for indicator in entity_indicators):
        attributes = cls.get('attributes', [])
        has_id = any(attr.get('name', '').lower() in ['id', 'identifier'] for attr in attributes)
        
        if not has_id:
            violations.append(f"Entity class '{class_name}' should have an ID field")

validation_result = {
    'is_valid': len(violations) == 0,
    'violations': violations
}
''',
                'error_message': 'Entity classes should have proper structure',
                'suggestion': 'Add an ID field to entity classes for proper persistence mapping'
            },
            {
                'name': 'Composition Relationship Validation',
                'description': 'Composition relationships should be used appropriately',
                'rule_type': 'DESIGN_PRINCIPLE',
                'severity': 'INFO',
                'applicable_diagrams': ['CLASS'],
                'validation_logic': '''
violations = []
compositions = [rel for rel in relationships if rel.get('relationship_type') == 'COMPOSITION']

for comp in compositions:
    if comp.get('source_multiplicity') == '*' and comp.get('target_multiplicity') == '*':
        violations.append(f"Many-to-many composition may indicate design issue")

validation_result = {
    'is_valid': len(violations) == 0,
    'violations': violations
}
''',
                'error_message': 'Composition relationships should be used carefully',
                'suggestion': 'Consider using aggregation for many-to-many relationships'
            },
            {
                'name': 'Cyclic Inheritance Check',
                'description': 'Inheritance hierarchies should not contain cycles',
                'rule_type': 'DESIGN_PRINCIPLE',
                'severity': 'ERROR',
                'applicable_diagrams': ['CLASS'],
                'validation_logic': '''
violations = []
inheritances = [rel for rel in relationships if rel.get('relationship_type') == 'INHERITANCE']

# Simple cycle detection
class_graph = {}
for rel in inheritances:
    source = rel.get('source_id')
    target = rel.get('target_id')
    if source not in class_graph:
        class_graph[source] = []
    class_graph[source].append(target)

def has_cycle(graph, start, visited, rec_stack):
    visited[start] = True
    rec_stack[start] = True
    
    for neighbor in graph.get(start, []):
        if not visited.get(neighbor, False):
            if has_cycle(graph, neighbor, visited, rec_stack):
                return True
        elif rec_stack.get(neighbor, False):
            return True
    
    rec_stack[start] = False
    return False

visited = {}
rec_stack = {}
for class_id in class_graph:
    if not visited.get(class_id, False):
        if has_cycle(class_graph, class_id, visited, rec_stack):
            violations.append("Cyclic inheritance detected in class hierarchy")
            break

validation_result = {
    'is_valid': len(violations) == 0,
    'violations': violations
}
''',
                'error_message': 'Cyclic inheritance is not allowed',
                'suggestion': 'Remove cycles in inheritance hierarchy to ensure proper class design'
            }
        ]
    
    @classmethod
    def initialize_system_rules(cls, user: User) -> None:
        """Initialize predefined system validation rules."""
        system_rules = cls.get_system_rules()
        
        for rule_data in system_rules:
            cls.objects.get_or_create(
                name=rule_data['name'],
                defaults={
                    'description': rule_data['description'],
                    'rule_type': rule_data['rule_type'],
                    'severity': rule_data['severity'],
                    'rule_pattern': {},
                    'validation_logic': rule_data['validation_logic'],
                    'error_message': rule_data['error_message'],
                    'suggestion': rule_data['suggestion'],
                    'applicable_diagrams': rule_data['applicable_diagrams'],
                    'is_system_rule': True,
                    'created_by': user
                }
            )
