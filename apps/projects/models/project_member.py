"""
ProjectMember model for managing project membership and access control.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ProjectMember(models.Model):
    """
    Project membership model with role-based access control.
    """
    
    MEMBER_ROLE_CHOICES = [
        ('VIEWER', 'Viewer'),
        ('EDITOR', 'Editor'),
        ('DEVELOPER', 'Developer'),
        ('ADMIN', 'Administrator'),
        ('OWNER', 'Owner'),
    ]
    
    MEMBER_STATUS_CHOICES = [
        ('INVITED', 'Invited'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('REMOVED', 'Removed'),
        ('LEFT', 'Left'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='members',
        help_text="Project this membership belongs to"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        help_text="User who is a member of the project"
    )
    
    role = models.CharField(
        max_length=20,
        choices=MEMBER_ROLE_CHOICES,
        default='VIEWER',
        help_text="Member's role and permissions level"
    )
    
    status = models.CharField(
        max_length=20,
        choices=MEMBER_STATUS_CHOICES,
        default='INVITED',
        help_text="Current membership status"
    )
    
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom permissions override for this member"
    )
    
    # Invitation tracking
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_invitations',
        help_text="User who invited this member"
    )
    
    invited_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the invitation was sent"
    )
    
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the invitation was accepted"
    )
    
    # Activity tracking
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time member was active in project"
    )
    
    collaboration_sessions = models.PositiveIntegerField(
        default=0,
        help_text="Number of collaboration sessions participated in"
    )
    
    diagrams_created = models.PositiveIntegerField(
        default=0,
        help_text="Number of diagrams created by this member"
    )
    
    diagrams_edited = models.PositiveIntegerField(
        default=0,
        help_text="Number of diagrams edited by this member"
    )
    
    code_generations = models.PositiveIntegerField(
        default=0,
        help_text="Number of code generations performed by this member"
    )
    
    # Membership lifecycle
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When member actively joined the project"
    )
    
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When member left the project"
    )
    
    rejoined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When member rejoined after leaving"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'projects_project_member'
        verbose_name = 'Project Member'
        verbose_name_plural = 'Project Members'
        ordering = ['-joined_at', '-accepted_at', '-invited_at']
        
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['project', 'role', 'status']),
            models.Index(fields=['invited_by']),
            models.Index(fields=['last_activity_at']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_project_user_membership'
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.role})"
    
    def save(self, *args, **kwargs):
        """Override save to handle automatic status transitions."""
        if self.pk:
            # Get the previous instance to check for changes
            try:
                old_instance = ProjectMember.objects.get(pk=self.pk)
                
                # Auto-set joined_at when status changes from INVITED to ACTIVE
                if old_instance.status == 'INVITED' and self.status == 'ACTIVE':
                    if not self.accepted_at:
                        self.accepted_at = timezone.now()
                    if not self.joined_at:
                        self.joined_at = timezone.now()
                
                # Update left_at when status changes to LEFT or REMOVED
                if self.status in ['LEFT', 'REMOVED'] and old_instance.status not in ['LEFT', 'REMOVED']:
                    self.left_at = timezone.now()
                
            except ProjectMember.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def is_active(self) -> bool:
        """Check if membership is currently active."""
        return self.status == 'ACTIVE'
    
    @property
    def is_admin(self) -> bool:
        """Check if member has admin privileges."""
        return self.role in ['ADMIN', 'OWNER']
    
    @property
    def can_edit_diagrams(self) -> bool:
        """Check if member can edit diagrams."""
        return self.role in ['EDITOR', 'DEVELOPER', 'ADMIN', 'OWNER']
    
    @property
    def can_generate_code(self) -> bool:
        """Check if member can generate code."""
        return self.role in ['DEVELOPER', 'ADMIN', 'OWNER']
    
    @property
    def can_invite_members(self) -> bool:
        """Check if member can invite other members."""
        return self.role in ['ADMIN', 'OWNER']
    
    @property
    def can_manage_project(self) -> bool:
        """Check if member can manage project settings."""
        return self.role in ['ADMIN', 'OWNER']
    
    def accept_invitation(self):
        """Accept project invitation and activate membership."""
        if self.status == 'INVITED':
            self.status = 'ACTIVE'
            self.accepted_at = timezone.now()
            self.joined_at = timezone.now()
            self.save(update_fields=['status', 'accepted_at', 'joined_at', 'updated_at'])
    
    def reject_invitation(self):
        """Reject project invitation."""
        if self.status == 'INVITED':
            self.status = 'REMOVED'
            self.left_at = timezone.now()
            self.save(update_fields=['status', 'left_at', 'updated_at'])
    
    def leave_project(self):
        """Member voluntarily leaves the project."""
        if self.status == 'ACTIVE':
            self.status = 'LEFT'
            self.left_at = timezone.now()
            self.save(update_fields=['status', 'left_at', 'updated_at'])
    
    def suspend_membership(self):
        """Suspend member from project."""
        if self.status == 'ACTIVE':
            self.status = 'SUSPENDED'
            self.save(update_fields=['status', 'updated_at'])
    
    def reactivate_membership(self):
        """Reactivate suspended membership."""
        if self.status == 'SUSPENDED':
            self.status = 'ACTIVE'
            self.rejoined_at = timezone.now()
            self.save(update_fields=['status', 'rejoined_at', 'updated_at'])
    
    def remove_from_project(self):
        """Remove member from project (admin action)."""
        if self.status in ['ACTIVE', 'SUSPENDED']:
            self.status = 'REMOVED'
            self.left_at = timezone.now()
            self.save(update_fields=['status', 'left_at', 'updated_at'])
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
    
    def increment_collaboration_sessions(self):
        """Increment collaboration session count."""
        self.collaboration_sessions = models.F('collaboration_sessions') + 1
        self.save(update_fields=['collaboration_sessions'])
    
    def increment_diagrams_created(self):
        """Increment diagrams created count."""
        self.diagrams_created = models.F('diagrams_created') + 1
        self.save(update_fields=['diagrams_created'])
    
    def increment_diagrams_edited(self):
        """Increment diagrams edited count."""
        self.diagrams_edited = models.F('diagrams_edited') + 1
        self.save(update_fields=['diagrams_edited'])
    
    def increment_code_generations(self):
        """Increment code generation count."""
        self.code_generations = models.F('code_generations') + 1
        self.save(update_fields=['code_generations'])
    
    def update_role(self, new_role: str, updated_by: User):
        """Update member role with audit tracking."""
        old_role = self.role
        self.role = new_role
        self.save(update_fields=['role', 'updated_at'])
        
        # Log role change in project activity
        # This would integrate with an activity logging system
    
    def get_effective_permissions(self) -> dict:
        """Get effective permissions including role-based and custom permissions."""
        # Base permissions by role
        role_permissions = {
            'VIEWER': {
                'view_diagrams': True,
                'edit_diagrams': False,
                'create_diagrams': False,
                'delete_diagrams': False,
                'generate_code': False,
                'invite_members': False,
                'manage_project': False,
            },
            'EDITOR': {
                'view_diagrams': True,
                'edit_diagrams': True,
                'create_diagrams': True,
                'delete_diagrams': False,
                'generate_code': False,
                'invite_members': False,
                'manage_project': False,
            },
            'DEVELOPER': {
                'view_diagrams': True,
                'edit_diagrams': True,
                'create_diagrams': True,
                'delete_diagrams': True,
                'generate_code': True,
                'invite_members': False,
                'manage_project': False,
            },
            'ADMIN': {
                'view_diagrams': True,
                'edit_diagrams': True,
                'create_diagrams': True,
                'delete_diagrams': True,
                'generate_code': True,
                'invite_members': True,
                'manage_project': True,
            },
            'OWNER': {
                'view_diagrams': True,
                'edit_diagrams': True,
                'create_diagrams': True,
                'delete_diagrams': True,
                'generate_code': True,
                'invite_members': True,
                'manage_project': True,
            },
        }
        
        base_permissions = role_permissions.get(self.role, role_permissions['VIEWER'])
        
        # Apply custom permission overrides
        effective_permissions = base_permissions.copy()
        effective_permissions.update(self.permissions)
        
        return effective_permissions
    
    def has_permission(self, permission: str) -> bool:
        """Check if member has specific permission."""
        return self.get_effective_permissions().get(permission, False)
    
    def get_member_statistics(self) -> dict:
        """Get comprehensive member statistics."""
        return {
            'id': str(self.id),
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'full_name': self.user.get_full_name() if hasattr(self.user, 'get_full_name') else ''
            },
            'project': {
                'id': str(self.project.id),
                'name': self.project.name
            },
            'role': self.role,
            'status': self.status,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'activity_stats': {
                'collaboration_sessions': self.collaboration_sessions,
                'diagrams_created': self.diagrams_created,
                'diagrams_edited': self.diagrams_edited,
                'code_generations': self.code_generations,
            },
            'permissions': self.get_effective_permissions()
        }
