
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
from typing import Dict, List

User = get_user_model()


class CollaborationSession(models.Model):
    """
    Active collaboration sessions for real-time UML diagram editing.
    """
    
    class SessionStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        PAUSED = 'PAUSED', 'Paused'
        ENDED = 'ENDED', 'Ended'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='collaboration_sessions'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='collaboration_sessions'
    )
    host_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hosted_sessions'
    )
    participants = models.ManyToManyField(
        User,
        through='CollaborationParticipant',
        related_name='collaboration_sessions'
    )
    status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE
    )
    session_data = models.JSONField(
        default=dict,
        help_text="Session configuration and metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'collaboration_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['diagram', 'created_at']),
            models.Index(fields=['host_user', 'status']),
        ]
    
    def __str__(self):
        return f"Session {self.id} - {self.diagram.name}"
    
    def add_participant(self, user: User, role: str = 'EDITOR') -> 'CollaborationParticipant':
        """Add user to collaboration session with specified role."""
        participant, created = CollaborationParticipant.objects.get_or_create(
            session=self,
            user=user,
            defaults={'role': role, 'joined_at': timezone.now()}
        )
        return participant
    
    def remove_participant(self, user: User) -> None:
        """Remove user from collaboration session."""
        CollaborationParticipant.objects.filter(
            session=self,
            user=user
        ).delete()
    
    def get_active_participants(self) -> List[User]:
        """Get list of currently active participants."""
        return [
            p.user for p in self.participants_detail.filter(
                is_active=True,
                left_at__isnull=True
            )
        ]
    
    def end_session(self) -> None:
        """End collaboration session and cleanup."""
        self.status = self.SessionStatus.ENDED
        self.ended_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['status', 'ended_at', 'is_active'])
        
        # Mark all participants as inactive
        self.participants_detail.update(
            is_active=False,
            left_at=timezone.now()
        )


class CollaborationParticipant(models.Model):
    """
    Through model for session participants with roles and activity tracking.
    """
    
    class ParticipantRole(models.TextChoices):
        HOST = 'HOST', 'Host'
        EDITOR = 'EDITOR', 'Editor'
        VIEWER = 'VIEWER', 'Viewer'
        COMMENTER = 'COMMENTER', 'Commenter'
    
    class ParticipantStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        DELETED = 'DELETED', 'Deleted'
    
    session = models.ForeignKey(
        CollaborationSession,
        on_delete=models.CASCADE,
        related_name='participants_detail'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='participation_details'
    )
    role = models.CharField(
        max_length=15,
        choices=ParticipantRole.choices,
        default=ParticipantRole.EDITOR
    )
    status = models.CharField(
        max_length=15,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.ACTIVE
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    cursor_position = models.JSONField(
        default=dict,
        help_text="Last known cursor position in diagram"
    )
    
    class Meta:
        db_table = 'collaboration_participants'
        unique_together = ['session', 'user']
        indexes = [
            models.Index(fields=['session', 'is_active']),
            models.Index(fields=['user', 'joined_at']),
        ]
    
    def __str__(self):
        return f"{self.user.corporate_email} - {self.role} in {self.session.id}"
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def leave_session(self) -> None:
        """Mark participant as left."""
        self.is_active = False
        self.status = self.ParticipantStatus.INACTIVE
        self.left_at = timezone.now()
        self.save(update_fields=['is_active', 'status', 'left_at'])
    
    def update_cursor_position(self, cursor_data: dict) -> None:
        """Update cursor position data."""
        self.cursor_position = cursor_data
        self.last_activity = timezone.now()
        self.save(update_fields=['cursor_position', 'last_activity'])
