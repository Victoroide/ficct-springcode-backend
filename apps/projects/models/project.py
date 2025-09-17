"""
Project model for managing UML collaboration projects and workspaces.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.utils import timezone

User = get_user_model()


class Project(models.Model):
    """
    Core project model for UML collaboration workspace management.
    """
    
    PROJECT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
        ('SUSPENDED', 'Suspended'),
        ('DELETED', 'Deleted'),
    ]
    
    PROJECT_VISIBILITY_CHOICES = [
        ('PRIVATE', 'Private'),
        ('TEAM', 'Team Only'),
        ('ORGANIZATION', 'Organization'),
        ('PUBLIC', 'Public'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(3), MaxLengthValidator(255)],
        help_text="Project name (3-255 characters)"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        max_length=2000,
        help_text="Project description and objectives"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        help_text="Project owner with full administrative rights"
    )
    
    workspace = models.ForeignKey(
        'projects.Workspace',
        on_delete=models.CASCADE,
        related_name='projects',
        help_text="Parent workspace containing this project"
    )
    
    status = models.CharField(
        max_length=20,
        choices=PROJECT_STATUS_CHOICES,
        default='ACTIVE',
        help_text="Current project status"
    )
    
    visibility = models.CharField(
        max_length=20,
        choices=PROJECT_VISIBILITY_CHOICES,
        default='PRIVATE',
        help_text="Project visibility and access level"
    )
    
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Project-specific configuration settings"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional project metadata and tags"
    )
    
    # SpringBoot generation configuration
    springboot_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="SpringBoot code generation configuration"
    )
    
    # Collaboration settings
    max_collaborators = models.PositiveIntegerField(
        default=10,
        help_text="Maximum number of concurrent collaborators"
    )
    
    auto_save_interval = models.PositiveIntegerField(
        default=30,
        help_text="Auto-save interval in seconds"
    )
    
    enable_real_time_collaboration = models.BooleanField(
        default=True,
        help_text="Enable real-time collaborative editing"
    )
    
    enable_version_control = models.BooleanField(
        default=True,
        help_text="Enable diagram version control"
    )
    
    # Activity tracking
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last project activity"
    )
    
    diagram_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of diagrams in project"
    )
    
    generation_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of code generations performed"
    )
    
    # Audit fields  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_projects'
    )
    
    class Meta:
        db_table = 'projects_project'
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        ordering = ['-last_activity_at', '-created_at']
        
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['workspace', 'status']),
            models.Index(fields=['status', 'visibility']),
            models.Index(fields=['last_activity_at']),
            models.Index(fields=['created_at']),
        ]
        
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_collaborators__gte=1) & models.Q(max_collaborators__lte=100),
                name='valid_max_collaborators_range'
            ),
            models.CheckConstraint(
                check=models.Q(auto_save_interval__gte=5) & models.Q(auto_save_interval__lte=300),
                name='valid_auto_save_interval_range'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.workspace.name})"
    
    def save(self, *args, **kwargs):
        """Override save to handle automatic field updates."""
        if not self.pk:
            # Set default SpringBoot configuration for new projects
            if not self.springboot_config:
                self.springboot_config = self.get_default_springboot_config()
        
        super().save(*args, **kwargs)
    
    def get_default_springboot_config(self) -> dict:
        """Get default SpringBoot configuration for new projects."""
        return {
            'group_id': 'com.example',
            'artifact_id': self.name.lower().replace(' ', '-').replace('_', '-'),
            'version': '1.0.0',
            'java_version': '17',
            'spring_boot_version': '3.2.0',
            'packaging': 'jar',
            'description': self.description or f"Generated SpringBoot application for {self.name}",
            'server_port': 8080,
            'database_type': 'h2',
            'enable_swagger': True,
            'enable_actuator': True,
            'enable_security': False
        }
    
    def is_accessible_by(self, user: User) -> bool:
        """Check if project is accessible by given user."""
        if self.owner == user:
            return True
        
        if self.members.filter(user=user, status='ACTIVE').exists():
            return True
        
        if self.visibility == 'PUBLIC':
            return True
        
        if self.visibility == 'ORGANIZATION' and user.is_authenticated:
            # Additional organization logic would go here
            return True
        
        return False
    
    def can_edit(self, user: User) -> bool:
        """Check if user can edit this project."""
        if self.owner == user:
            return True
        
        member = self.members.filter(user=user, status='ACTIVE').first()
        if member and member.role in ['ADMIN', 'EDITOR']:
            return True
        
        return False
    
    def can_generate_code(self, user: User) -> bool:
        """Check if user can generate code from this project."""
        if not self.is_accessible_by(user):
            return False
        
        if self.owner == user:
            return True
        
        member = self.members.filter(user=user, status='ACTIVE').first()
        if member and member.role in ['ADMIN', 'EDITOR', 'DEVELOPER']:
            return True
        
        return False
    
    def get_active_members(self):
        """Get all active project members."""
        return self.members.filter(status='ACTIVE').select_related('user')
    
    def get_member_count(self) -> int:
        """Get total number of active members."""
        return self.members.filter(status='ACTIVE').count()
    
    def get_admin_members(self):
        """Get all admin members."""
        return self.members.filter(status='ACTIVE', role='ADMIN').select_related('user')
    
    def add_member(self, user: User, role: str = 'VIEWER', invited_by: User = None) -> 'ProjectMember':
        """Add new member to project."""
        from .project_member import ProjectMember
        
        member, created = ProjectMember.objects.get_or_create(
            project=self,
            user=user,
            defaults={
                'role': role,
                'invited_by': invited_by or self.owner,
                'status': 'ACTIVE'
            }
        )
        
        if not created and member.status != 'ACTIVE':
            member.status = 'ACTIVE'
            member.role = role
            member.rejoined_at = timezone.now()
            member.save()
        
        return member
    
    def remove_member(self, user: User) -> bool:
        """Remove member from project."""
        try:
            member = self.members.get(user=user, status='ACTIVE')
            member.status = 'REMOVED'
            member.left_at = timezone.now()
            member.save()
            return True
        except self.members.model.DoesNotExist:
            return False
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])
    
    def increment_diagram_count(self):
        """Increment diagram count."""
        self.diagram_count = models.F('diagram_count') + 1
        self.save(update_fields=['diagram_count'])
    
    def increment_generation_count(self):
        """Increment code generation count."""
        self.generation_count = models.F('generation_count') + 1
        self.save(update_fields=['generation_count'])
    
    def archive(self, archived_by: User):
        """Archive the project."""
        self.status = 'ARCHIVED'
        self.updated_by = archived_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def activate(self, activated_by: User):
        """Activate archived project."""
        self.status = 'ACTIVE'
        self.updated_by = activated_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def soft_delete(self, deleted_by: User):
        """Soft delete the project."""
        self.status = 'DELETED'
        self.updated_by = deleted_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def get_springboot_application_class_name(self) -> str:
        """Generate SpringBoot application class name."""
        name = self.springboot_config.get('artifact_id', self.name)
        # Convert to PascalCase and add Application suffix
        class_name = ''.join(word.capitalize() for word in name.replace('-', ' ').replace('_', ' ').split())
        return f"{class_name}Application"
    
    def update_springboot_config(self, config_updates: dict, updated_by: User):
        """Update SpringBoot configuration."""
        self.springboot_config.update(config_updates)
        self.updated_by = updated_by
        self.save(update_fields=['springboot_config', 'updated_by', 'updated_at'])
    
    def get_project_statistics(self) -> dict:
        """Get comprehensive project statistics."""
        return {
            'id': str(self.id),
            'name': self.name,
            'status': self.status,
            'member_count': self.get_member_count(),
            'diagram_count': self.diagram_count,
            'generation_count': self.generation_count,
            'created_at': self.created_at.isoformat(),
            'last_activity_at': self.last_activity_at.isoformat(),
            'owner': {
                'id': self.owner.id,
                'username': self.owner.username,
                'email': self.owner.email
            },
            'workspace': {
                'id': str(self.workspace.id),
                'name': self.workspace.name
            }
        }
