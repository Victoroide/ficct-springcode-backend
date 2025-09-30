"""
DiagramVersion model for comprehensive version control and change tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class DiagramVersion(models.Model):
    """
    Version control for UML diagrams with comprehensive change tracking.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.PositiveIntegerField()
    diagram_data = models.JSONField(
        help_text="Complete diagram state at this version"
    )
    layout_config = models.JSONField(
        default=dict,
        help_text="Layout configuration at this version"
    )
    change_summary = models.TextField(
        help_text="Summary of changes in this version"
    )
    change_details = models.JSONField(
        default=dict,
        help_text="Detailed change information for diff generation"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='diagram_versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_major_version = models.BooleanField(default=False)
    tag = models.CharField(
        max_length=100,
        blank=True,
        help_text="Version tag or label"
    )
    parent_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_versions'
    )
    
    class Meta:
        db_table = 'diagram_versions'
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['diagram', 'version_number']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['is_major_version', 'diagram']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['diagram', 'version_number'],
                name='unique_version_per_diagram'
            )
        ]
    
    def __str__(self):
        return f"{self.diagram.name} v{self.version_number}"
    
    def get_changes_from_previous(self) -> dict:
        """Calculate changes from previous version."""
        if not self.parent_version:
            return {'type': 'initial', 'changes': []}
        
        previous_data = self.parent_version.diagram_data
        current_data = self.diagram_data
        
        changes = {
            'added_classes': [],
            'modified_classes': [],
            'removed_classes': [],
            'added_relationships': [],
            'modified_relationships': [],
            'removed_relationships': []
        }

        prev_classes = {cls['id']: cls for cls in previous_data.get('classes', [])}
        curr_classes = {cls['id']: cls for cls in current_data.get('classes', [])}

        for class_id, class_data in curr_classes.items():
            if class_id not in prev_classes:
                changes['added_classes'].append(class_data)

        for class_id, class_data in prev_classes.items():
            if class_id not in curr_classes:
                changes['removed_classes'].append(class_data)

        for class_id in set(prev_classes.keys()) & set(curr_classes.keys()):
            if prev_classes[class_id] != curr_classes[class_id]:
                changes['modified_classes'].append({
                    'id': class_id,
                    'previous': prev_classes[class_id],
                    'current': curr_classes[class_id]
                })

        prev_rels = {rel['id']: rel for rel in previous_data.get('relationships', [])}
        curr_rels = {rel['id']: rel for rel in current_data.get('relationships', [])}

        for rel_id, rel_data in curr_rels.items():
            if rel_id not in prev_rels:
                changes['added_relationships'].append(rel_data)

        for rel_id, rel_data in prev_rels.items():
            if rel_id not in curr_rels:
                changes['removed_relationships'].append(rel_data)

        for rel_id in set(prev_rels.keys()) & set(curr_rels.keys()):
            if prev_rels[rel_id] != curr_rels[rel_id]:
                changes['modified_relationships'].append({
                    'id': rel_id,
                    'previous': prev_rels[rel_id],
                    'current': curr_rels[rel_id]
                })
        
        return changes
    
    def restore_version(self, user: User) -> 'UMLDiagram':
        """Restore diagram to this version state."""
        diagram = self.diagram
        diagram.diagram_data = self.diagram_data.copy()
        diagram.layout_config = self.layout_config.copy()
        diagram.last_modified_by = user
        diagram.save()
        
        return diagram
    
    def create_branch(self, user: User, branch_name: str) -> 'UMLDiagram':
        """Create new diagram branch from this version."""
        new_diagram = self.diagram.clone_diagram(
            new_name=f"{self.diagram.name} - {branch_name}",
            user=user
        )

        new_diagram.diagram_data = self.diagram_data.copy()
        new_diagram.layout_config = self.layout_config.copy()
        new_diagram.save()
        
        return new_diagram
    
    def get_version_diff(self, other_version: 'DiagramVersion') -> dict:
        """Generate diff between this and another version."""
        if other_version.version_number < self.version_number:
            base_data = other_version.diagram_data
            target_data = self.diagram_data
        else:
            base_data = self.diagram_data
            target_data = other_version.diagram_data
        
        diff = {
            'base_version': other_version.version_number if other_version.version_number < self.version_number else self.version_number,
            'target_version': self.version_number if other_version.version_number < self.version_number else other_version.version_number,
            'changes': []
        }

        base_classes = {cls['id']: cls for cls in base_data.get('classes', [])}
        target_classes = {cls['id']: cls for cls in target_data.get('classes', [])}
        
        for class_id in set(base_classes.keys()) | set(target_classes.keys()):
            if class_id not in base_classes:
                diff['changes'].append({
                    'type': 'class_added',
                    'element_id': class_id,
                    'data': target_classes[class_id]
                })
            elif class_id not in target_classes:
                diff['changes'].append({
                    'type': 'class_removed',
                    'element_id': class_id,
                    'data': base_classes[class_id]
                })
            elif base_classes[class_id] != target_classes[class_id]:
                diff['changes'].append({
                    'type': 'class_modified',
                    'element_id': class_id,
                    'before': base_classes[class_id],
                    'after': target_classes[class_id]
                })
        
        return diff
    
    @classmethod
    def create_version(cls, diagram, user: User, change_summary: str = None,
                      is_major: bool = False, tag: str = None) -> 'DiagramVersion':
        """Create new version for diagram."""
        last_version = cls.objects.filter(diagram=diagram).first()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        version = cls.objects.create(
            diagram=diagram,
            version_number=version_number,
            diagram_data=diagram.diagram_data.copy(),
            layout_config=diagram.layout_config.copy(),
            change_summary=change_summary or f"Version {version_number}",
            created_by=user,
            is_major_version=is_major,
            tag=tag,
            parent_version=last_version
        )
        
        return version
    
    def get_version_statistics(self) -> dict:
        """Get statistics about this version."""
        classes = self.diagram_data.get('classes', [])
        relationships = self.diagram_data.get('relationships', [])
        
        stats = {
            'total_classes': len(classes),
            'total_relationships': len(relationships),
            'class_types': {},
            'relationship_types': {},
            'total_attributes': 0,
            'total_methods': 0
        }

        for cls in classes:
            class_type = cls.get('class_type', 'CLASS')
            stats['class_types'][class_type] = stats['class_types'].get(class_type, 0) + 1
            stats['total_attributes'] += len(cls.get('attributes', []))
            stats['total_methods'] += len(cls.get('methods', []))

        for rel in relationships:
            rel_type = rel.get('relationship_type', 'ASSOCIATION')
            stats['relationship_types'][rel_type] = stats['relationship_types'].get(rel_type, 0) + 1
        
        return stats
