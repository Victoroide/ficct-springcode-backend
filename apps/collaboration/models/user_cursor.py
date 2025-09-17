"""
UserCursor model for real-time cursor tracking in collaborative editing.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class UserCursor(models.Model):
    """
    Real-time cursor position tracking for collaborative UML editing.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        'collaboration.CollaborationSession',
        on_delete=models.CASCADE,
        related_name='user_cursors'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cursor_positions'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='user_cursors'
    )
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    viewport_zoom = models.FloatField(default=1.0)
    viewport_center_x = models.FloatField(default=0.0)
    viewport_center_y = models.FloatField(default=0.0)
    selected_element_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Currently selected UML element ID"
    )
    cursor_color = models.CharField(
        max_length=7,
        default='#3B82F6',
        help_text="Hex color code for cursor display"
    )
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_cursors'
        ordering = ['-last_updated']
        indexes = [
            models.Index(fields=['session', 'is_active']),
            models.Index(fields=['diagram', 'user']),
            models.Index(fields=['last_updated']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'user'],
                condition=models.Q(is_active=True),
                name='unique_active_user_cursor'
            )
        ]
    
    def __str__(self):
        return f"Cursor for {self.user.corporate_email} in {self.session.id}"
    
    def update_position(self, x: float, y: float, 
                       selected_element: str = None) -> None:
        """Update cursor position and selected element."""
        self.position_x = x
        self.position_y = y
        if selected_element is not None:
            self.selected_element_id = selected_element
        self.last_updated = timezone.now()
        self.save(update_fields=[
            'position_x', 'position_y', 'selected_element_id', 'last_updated'
        ])
    
    def update_viewport(self, zoom: float, center_x: float, center_y: float) -> None:
        """Update viewport information."""
        self.viewport_zoom = zoom
        self.viewport_center_x = center_x  
        self.viewport_center_y = center_y
        self.last_updated = timezone.now()
        self.save(update_fields=[
            'viewport_zoom', 'viewport_center_x', 'viewport_center_y', 'last_updated'
        ])
    
    @classmethod
    def get_active_cursors(cls, session) -> models.QuerySet:
        """Get all active cursors for a collaboration session."""
        return cls.objects.filter(
            session=session,
            is_active=True
        ).select_related('user')
    
    @classmethod
    def cleanup_inactive_cursors(cls, session, active_user_ids: list) -> int:
        """Mark cursors as inactive for users not in active list."""
        return cls.objects.filter(
            session=session,
            is_active=True
        ).exclude(
            user_id__in=active_user_ids
        ).update(is_active=False)
    
    def deactivate(self) -> None:
        """Deactivate cursor when user leaves session."""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def get_cursor_data(self) -> dict:
        """Get cursor data for WebSocket broadcast."""
        return {
            'user_id': str(self.user.id),
            'user_name': self.user.full_name,
            'user_email': self.user.corporate_email,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'viewport_zoom': self.viewport_zoom,
            'viewport_center_x': self.viewport_center_x,
            'viewport_center_y': self.viewport_center_y,
            'selected_element_id': self.selected_element_id,
            'cursor_color': self.cursor_color,
            'last_updated': self.last_updated.isoformat()
        }
