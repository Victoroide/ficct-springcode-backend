"""
DiagramLock model for element-level conflict prevention in real-time editing.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class DiagramLock(models.Model):
    """
    Element-level locks to prevent editing conflicts in real-time collaboration.
    """
    
    class LockType(models.TextChoices):
        ELEMENT = 'ELEMENT', 'Element Lock'
        ATTRIBUTE = 'ATTRIBUTE', 'Attribute Lock'
        RELATIONSHIP = 'RELATIONSHIP', 'Relationship Lock'
        SECTION = 'SECTION', 'Section Lock'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        'collaboration.CollaborationSession',
        on_delete=models.CASCADE,
        related_name='locks'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='active_locks'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='held_locks'
    )
    lock_type = models.CharField(
        max_length=15,
        choices=LockType.choices,
        default=LockType.ELEMENT
    )
    element_id = models.CharField(
        max_length=100,
        help_text="ID of the locked UML element"
    )
    element_path = models.CharField(
        max_length=500,
        help_text="JSON path to the locked element/attribute"
    )
    acquired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    lock_metadata = models.JSONField(
        default=dict,
        help_text="Additional lock information and context"
    )
    
    class Meta:
        db_table = 'diagram_locks'
        ordering = ['acquired_at']
        indexes = [
            models.Index(fields=['diagram', 'element_id', 'is_active']),
            models.Index(fields=['user', 'acquired_at']),
            models.Index(fields=['session', 'is_active']),
            models.Index(fields=['expires_at', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['diagram', 'element_id', 'element_path'],
                condition=models.Q(is_active=True),
                name='unique_active_element_lock'
            )
        ]
    
    def __str__(self):
        return f"Lock on {self.element_id} by {self.user.corporate_email}"
    
    @classmethod
    def acquire_lock(cls, session, diagram, user, element_id: str, 
                    element_path: str = '', lock_type: str = 'ELEMENT',
                    duration_minutes: int = 5) -> 'DiagramLock':
        """
        Acquire a lock on a diagram element.
        """
        expires_at = timezone.now() + timezone.timedelta(minutes=duration_minutes)
        
        # Release any existing locks on the same element
        cls.objects.filter(
            diagram=diagram,
            element_id=element_id,
            element_path=element_path,
            is_active=True
        ).update(is_active=False)
        
        lock = cls.objects.create(
            session=session,
            diagram=diagram,
            user=user,
            lock_type=lock_type,
            element_id=element_id,
            element_path=element_path,
            expires_at=expires_at
        )
        
        return lock
    
    def release_lock(self) -> None:
        """Release the lock."""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def extend_lock(self, additional_minutes: int = 5) -> None:
        """Extend lock expiration time."""
        self.expires_at = timezone.now() + timezone.timedelta(minutes=additional_minutes)
        self.save(update_fields=['expires_at'])
    
    def is_expired(self) -> bool:
        """Check if lock has expired."""
        return timezone.now() > self.expires_at
    
    @classmethod
    def cleanup_expired_locks(cls) -> int:
        """Clean up expired locks and return count of cleaned locks."""
        expired_count = cls.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        ).update(is_active=False)
        
        return expired_count
    
    @classmethod
    def get_active_locks_for_diagram(cls, diagram) -> models.QuerySet:
        """Get all active locks for a diagram."""
        return cls.objects.filter(
            diagram=diagram,
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('user')
    
    def can_user_edit(self, user: User) -> bool:
        """Check if user can edit the locked element."""
        if not self.is_active or self.is_expired():
            return True
        return self.user == user
