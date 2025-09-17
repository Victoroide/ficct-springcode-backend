"""
ChangeEvent model for tracking and broadcasting real-time UML diagram changes.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class ChangeEvent(models.Model):
    """
    Real-time change events for collaborative UML diagram editing.
    """
    
    class EventType(models.TextChoices):
        ELEMENT_CREATED = 'ELEMENT_CREATED', 'Element Created'
        ELEMENT_UPDATED = 'ELEMENT_UPDATED', 'Element Updated'  
        ELEMENT_DELETED = 'ELEMENT_DELETED', 'Element Deleted'
        ELEMENT_MOVED = 'ELEMENT_MOVED', 'Element Moved'
        RELATIONSHIP_CREATED = 'RELATIONSHIP_CREATED', 'Relationship Created'
        RELATIONSHIP_UPDATED = 'RELATIONSHIP_UPDATED', 'Relationship Updated'
        RELATIONSHIP_DELETED = 'RELATIONSHIP_DELETED', 'Relationship Deleted'
        ATTRIBUTE_ADDED = 'ATTRIBUTE_ADDED', 'Attribute Added'
        ATTRIBUTE_UPDATED = 'ATTRIBUTE_UPDATED', 'Attribute Updated'
        ATTRIBUTE_REMOVED = 'ATTRIBUTE_REMOVED', 'Attribute Removed'
        METHOD_ADDED = 'METHOD_ADDED', 'Method Added'
        METHOD_UPDATED = 'METHOD_UPDATED', 'Method Updated'
        METHOD_REMOVED = 'METHOD_REMOVED', 'Method Removed'
        DIAGRAM_SAVED = 'DIAGRAM_SAVED', 'Diagram Saved'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        'collaboration.CollaborationSession',
        on_delete=models.CASCADE,
        related_name='change_events'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='change_events'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='change_events'
    )
    event_type = models.CharField(
        max_length=25,
        choices=EventType.choices
    )
    element_id = models.CharField(
        max_length=100,
        help_text="ID of the affected UML element"
    )
    element_type = models.CharField(
        max_length=50,
        help_text="Type of UML element (class, interface, etc.)"
    )
    change_data = models.JSONField(
        help_text="Detailed change information and new values"
    )
    previous_data = models.JSONField(
        default=dict,
        help_text="Previous state for undo functionality"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_broadcasted = models.BooleanField(default=False)
    broadcast_count = models.IntegerField(default=0)
    sequence_number = models.BigIntegerField()
    conflict_resolved = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'collaboration_change_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['diagram', 'element_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['sequence_number']),
            models.Index(fields=['is_broadcasted', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.event_type} on {self.element_id} by {self.user.corporate_email}"
    
    def save(self, *args, **kwargs):
        """Auto-generate sequence number if not provided."""
        if not self.sequence_number:
            last_event = ChangeEvent.objects.filter(
                session=self.session
            ).order_by('-sequence_number').first()
            
            self.sequence_number = (last_event.sequence_number + 1) if last_event else 1
            
        super().save(*args, **kwargs)
    
    def mark_broadcasted(self, recipient_count: int = 0) -> None:
        """Mark event as successfully broadcasted."""
        self.is_broadcasted = True
        self.broadcast_count = recipient_count
        self.save(update_fields=['is_broadcasted', 'broadcast_count'])
    
    def get_broadcast_data(self) -> dict:
        """Get event data formatted for WebSocket broadcast."""
        return {
            'event_id': str(self.id),
            'event_type': self.event_type,
            'element_id': self.element_id,
            'element_type': self.element_type,
            'user_id': str(self.user.id),
            'user_name': self.user.full_name,
            'user_email': self.user.corporate_email,
            'change_data': self.change_data,
            'timestamp': self.timestamp.isoformat(),
            'sequence_number': self.sequence_number,
        }
    
    @classmethod
    def create_event(cls, session, diagram, user, event_type: str,
                    element_id: str, element_type: str, change_data: dict,
                    previous_data: dict = None) -> 'ChangeEvent':
        """Create and save a new change event."""
        event = cls.objects.create(
            session=session,
            diagram=diagram,
            user=user,
            event_type=event_type,
            element_id=element_id,
            element_type=element_type,
            change_data=change_data,
            previous_data=previous_data or {}
        )
        return event
    
    @classmethod
    def get_events_since(cls, session, since_sequence: int) -> models.QuerySet:
        """Get all events since a specific sequence number."""
        return cls.objects.filter(
            session=session,
            sequence_number__gt=since_sequence
        ).order_by('sequence_number')
    
    @classmethod
    def get_recent_events(cls, session, limit: int = 100) -> models.QuerySet:
        """Get recent events for session synchronization."""
        return cls.objects.filter(
            session=session
        ).order_by('-sequence_number')[:limit]
    
    def can_undo(self, user: User) -> bool:
        """Check if event can be undone by user."""
        return (
            self.user == user and
            self.previous_data and
            not self.conflict_resolved and
            (timezone.now() - self.timestamp).total_seconds() < 3600  # 1 hour limit
        )
