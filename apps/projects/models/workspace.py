"""
Workspace model for organizing projects and managing organizational boundaries.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator, MaxLengthValidator

User = get_user_model()


class Workspace(models.Model):
    """
    Workspace model for organizing projects within organizational boundaries.
    """
    
    WORKSPACE_TYPE_CHOICES = [
        ('PERSONAL', 'Personal Workspace'),
        ('TEAM', 'Team Workspace'),
        ('ORGANIZATION', 'Organization Workspace'),
        ('ENTERPRISE', 'Enterprise Workspace'),
    ]
    
    WORKSPACE_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('ARCHIVED', 'Archived'),
        ('DELETED', 'Deleted'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(3), MaxLengthValidator(255)],
        help_text="Workspace name (3-255 characters)"
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly workspace identifier"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        max_length=1000,
        help_text="Workspace description and purpose"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_workspaces',
        help_text="Workspace owner with full administrative rights"
    )
    
    workspace_type = models.CharField(
        max_length=20,
        choices=WORKSPACE_TYPE_CHOICES,
        default='PERSONAL',
        help_text="Type of workspace determining features and limits"
    )
    
    status = models.CharField(
        max_length=20,
        choices=WORKSPACE_STATUS_CHOICES,
        default='ACTIVE',
        help_text="Current workspace status"
    )
    
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Workspace-specific configuration settings"
    )
    
    # Resource limits based on workspace type
    max_projects = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of projects allowed in workspace"
    )
    
    max_members_per_project = models.PositiveIntegerField(
        default=10,
        help_text="Maximum members allowed per project"
    )
    
    max_diagrams_per_project = models.PositiveIntegerField(
        default=50,
        help_text="Maximum diagrams allowed per project"
    )
    
    max_storage_mb = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum storage in MB for workspace"
    )
    
    # Features enabled for this workspace
    enable_real_time_collaboration = models.BooleanField(
        default=True,
        help_text="Enable real-time collaborative editing"
    )
    
    enable_version_control = models.BooleanField(
        default=True,
        help_text="Enable diagram version control"
    )
    
    enable_code_generation = models.BooleanField(
        default=True,
        help_text="Enable SpringBoot code generation"
    )
    
    enable_api_access = models.BooleanField(
        default=False,
        help_text="Enable API access for integrations"
    )
    
    enable_advanced_templates = models.BooleanField(
        default=False,
        help_text="Enable advanced code generation templates"
    )
    
    # Usage statistics
    current_projects = models.PositiveIntegerField(
        default=0,
        help_text="Current number of active projects"
    )
    
    total_diagrams = models.PositiveIntegerField(
        default=0,
        help_text="Total number of diagrams across all projects"
    )
    
    total_generations = models.PositiveIntegerField(
        default=0,
        help_text="Total number of code generations performed"
    )
    
    storage_used_mb = models.PositiveIntegerField(
        default=0,
        help_text="Current storage usage in MB"
    )
    
    # Subscription and billing information
    subscription_plan = models.CharField(
        max_length=50,
        default='FREE',
        help_text="Current subscription plan"
    )
    
    billing_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email for billing notifications"
    )
    
    subscription_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When current subscription expires"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workspaces'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_workspaces'
    )
    
    class Meta:
        db_table = 'projects_workspace'
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['workspace_type', 'status']),
            models.Index(fields=['slug']),
            models.Index(fields=['subscription_plan']),
            models.Index(fields=['created_at']),
        ]
        
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_projects__gte=1) & models.Q(max_projects__lte=1000),
                name='valid_max_projects_range'
            ),
            models.CheckConstraint(
                check=models.Q(max_members_per_project__gte=1) & models.Q(max_members_per_project__lte=100),
                name='valid_max_members_range'
            ),
            models.CheckConstraint(
                check=models.Q(storage_used_mb__gte=0) & models.Q(storage_used_mb__lte=models.F('max_storage_mb')),
                name='valid_storage_usage'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.workspace_type})"
    
    def save(self, *args, **kwargs):
        """Override save to set appropriate limits based on workspace type."""
        if not self.pk:
            self._set_type_defaults()
        super().save(*args, **kwargs)
    
    def _set_type_defaults(self):
        """Set default limits based on workspace type."""
        type_defaults = {
            'PERSONAL': {
                'max_projects': 5,
                'max_members_per_project': 3,
                'max_diagrams_per_project': 20,
                'max_storage_mb': 500,
                'enable_api_access': False,
                'enable_advanced_templates': False,
            },
            'TEAM': {
                'max_projects': 20,
                'max_members_per_project': 15,
                'max_diagrams_per_project': 100,
                'max_storage_mb': 5000,
                'enable_api_access': True,
                'enable_advanced_templates': True,
            },
            'ORGANIZATION': {
                'max_projects': 100,
                'max_members_per_project': 50,
                'max_diagrams_per_project': 500,
                'max_storage_mb': 25000,
                'enable_api_access': True,
                'enable_advanced_templates': True,
            },
            'ENTERPRISE': {
                'max_projects': 1000,
                'max_members_per_project': 100,
                'max_diagrams_per_project': 1000,
                'max_storage_mb': 100000,
                'enable_api_access': True,
                'enable_advanced_templates': True,
            },
        }
        
        defaults = type_defaults.get(self.workspace_type, type_defaults['PERSONAL'])
        for field, value in defaults.items():
            if not getattr(self, field):
                setattr(self, field, value)
    
    def can_create_project(self) -> bool:
        """Check if workspace can create new project."""
        return self.current_projects < self.max_projects and self.status == 'ACTIVE'
    
    def can_add_storage(self, mb_required: int) -> bool:
        """Check if workspace has enough storage capacity."""
        return (self.storage_used_mb + mb_required) <= self.max_storage_mb
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if specific feature is enabled for workspace."""
        feature_map = {
            'real_time_collaboration': self.enable_real_time_collaboration,
            'version_control': self.enable_version_control,
            'code_generation': self.enable_code_generation,
            'api_access': self.enable_api_access,
            'advanced_templates': self.enable_advanced_templates,
        }
        return feature_map.get(feature, False)
    
    def get_usage_percentage(self) -> dict:
        """Get usage percentages for various limits."""
        return {
            'projects': (self.current_projects / self.max_projects) * 100 if self.max_projects > 0 else 0,
            'storage': (self.storage_used_mb / self.max_storage_mb) * 100 if self.max_storage_mb > 0 else 0,
        }
    
    def is_over_limit(self) -> dict:
        """Check if workspace is over any limits."""
        return {
            'projects': self.current_projects >= self.max_projects,
            'storage': self.storage_used_mb >= self.max_storage_mb,
        }
    
    def increment_project_count(self):
        """Increment current project count."""
        self.current_projects = models.F('current_projects') + 1
        self.save(update_fields=['current_projects'])
    
    def decrement_project_count(self):
        """Decrement current project count."""
        if self.current_projects > 0:
            self.current_projects = models.F('current_projects') - 1
            self.save(update_fields=['current_projects'])
    
    def increment_diagram_count(self):
        """Increment total diagram count."""
        self.total_diagrams = models.F('total_diagrams') + 1
        self.save(update_fields=['total_diagrams'])
    
    def increment_generation_count(self):
        """Increment total generation count."""
        self.total_generations = models.F('total_generations') + 1
        self.save(update_fields=['total_generations'])
    
    def update_storage_usage(self, mb_delta: int):
        """Update storage usage (can be positive or negative)."""
        new_usage = max(0, self.storage_used_mb + mb_delta)
        self.storage_used_mb = min(new_usage, self.max_storage_mb)
        self.save(update_fields=['storage_used_mb'])
    
    def upgrade_workspace_type(self, new_type: str, upgraded_by: User):
        """Upgrade workspace to higher tier."""
        if new_type in dict(self.WORKSPACE_TYPE_CHOICES):
            old_type = self.workspace_type
            self.workspace_type = new_type
            self._set_type_defaults()
            self.updated_by = upgraded_by
            self.save()
    
    def suspend_workspace(self, suspended_by: User):
        """Suspend workspace access."""
        self.status = 'SUSPENDED'
        self.updated_by = suspended_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def activate_workspace(self, activated_by: User):
        """Activate suspended workspace."""
        self.status = 'ACTIVE'
        self.updated_by = activated_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def archive_workspace(self, archived_by: User):
        """Archive workspace for long-term storage."""
        self.status = 'ARCHIVED'
        self.updated_by = archived_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def get_active_projects(self):
        """Get all active projects in workspace."""
        return self.projects.filter(status='ACTIVE')
    
    def get_workspace_members(self):
        """Get all unique members across all projects in workspace."""
        from .project_member import ProjectMember
        
        return User.objects.filter(
            project_memberships__project__workspace=self,
            project_memberships__status='ACTIVE'
        ).distinct()
    
    def get_workspace_statistics(self) -> dict:
        """Get comprehensive workspace statistics."""
        usage_percentages = self.get_usage_percentage()
        over_limits = self.is_over_limit()
        
        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'type': self.workspace_type,
            'status': self.status,
            'subscription_plan': self.subscription_plan,
            'owner': {
                'id': self.owner.id,
                'username': self.owner.username,
                'email': self.owner.email
            },
            'limits': {
                'max_projects': self.max_projects,
                'max_members_per_project': self.max_members_per_project,
                'max_diagrams_per_project': self.max_diagrams_per_project,
                'max_storage_mb': self.max_storage_mb,
            },
            'current_usage': {
                'projects': self.current_projects,
                'diagrams': self.total_diagrams,
                'generations': self.total_generations,
                'storage_mb': self.storage_used_mb,
            },
            'usage_percentages': usage_percentages,
            'over_limits': over_limits,
            'features': {
                'real_time_collaboration': self.enable_real_time_collaboration,
                'version_control': self.enable_version_control,
                'code_generation': self.enable_code_generation,
                'api_access': self.enable_api_access,
                'advanced_templates': self.enable_advanced_templates,
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
