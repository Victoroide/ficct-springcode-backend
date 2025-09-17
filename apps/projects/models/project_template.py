"""
ProjectTemplate model for managing reusable project templates and configurations.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator, MaxLengthValidator

User = get_user_model()


class ProjectTemplate(models.Model):
    """
    Project template model for creating reusable project configurations.
    """
    
    TEMPLATE_TYPE_CHOICES = [
        ('SYSTEM', 'System Template'),
        ('ORGANIZATION', 'Organization Template'),
        ('USER', 'User Template'),
        ('COMMUNITY', 'Community Template'),
    ]
    
    TEMPLATE_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('DEPRECATED', 'Deprecated'),
        ('ARCHIVED', 'Archived'),
    ]
    
    TEMPLATE_CATEGORY_CHOICES = [
        ('WEB_APPLICATION', 'Web Application'),
        ('MICROSERVICE', 'Microservice'),
        ('REST_API', 'REST API'),
        ('ENTERPRISE_APP', 'Enterprise Application'),
        ('PROTOTYPE', 'Prototype'),
        ('EDUCATIONAL', 'Educational'),
        ('CUSTOM', 'Custom'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(3), MaxLengthValidator(255)],
        help_text="Template name (3-255 characters)"
    )
    
    slug = models.SlugField(
        max_length=100,
        help_text="URL-friendly template identifier"
    )
    
    description = models.TextField(
        max_length=2000,
        help_text="Detailed template description and use cases"
    )
    
    short_description = models.CharField(
        max_length=500,
        help_text="Brief template description for listings"
    )
    
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        default='USER',
        help_text="Template type and visibility scope"
    )
    
    status = models.CharField(
        max_length=20,
        choices=TEMPLATE_STATUS_CHOICES,
        default='DRAFT',
        help_text="Current template status"
    )
    
    category = models.CharField(
        max_length=30,
        choices=TEMPLATE_CATEGORY_CHOICES,
        default='CUSTOM',
        help_text="Template category for organization"
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='authored_templates',
        help_text="Template author"
    )
    
    workspace = models.ForeignKey(
        'projects.Workspace',
        on_delete=models.CASCADE,
        related_name='templates',
        null=True,
        blank=True,
        help_text="Workspace that owns this template (for organization templates)"
    )
    
    # Template configuration
    project_config = models.JSONField(
        default=dict,
        help_text="Default project configuration for this template"
    )
    
    springboot_config = models.JSONField(
        default=dict,
        help_text="Default SpringBoot configuration for this template"
    )
    
    uml_template_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Initial UML diagram template data"
    )
    
    code_generation_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Code generation configuration and preferences"
    )
    
    # Template metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Template tags for categorization and search"
    )
    
    technologies = models.JSONField(
        default=list,
        blank=True,
        help_text="Technologies and frameworks used in this template"
    )
    
    prerequisites = models.JSONField(
        default=list,
        blank=True,
        help_text="Prerequisites and requirements for using template"
    )
    
    # Usage and popularity metrics
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times template has been used"
    )
    
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of likes/favorites"
    )
    
    downloads_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of downloads/exports"
    )
    
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="Average user rating (0.00-5.00)"
    )
    
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of ratings received"
    )
    
    # Template versioning
    version = models.CharField(
        max_length=20,
        default='1.0.0',
        help_text="Template version (semantic versioning)"
    )
    
    parent_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_templates',
        help_text="Parent template if this is a derived version"
    )
    
    # Template content and structure
    readme_content = models.TextField(
        blank=True,
        null=True,
        help_text="Template documentation in Markdown"
    )
    
    changelog = models.TextField(
        blank=True,
        null=True,
        help_text="Version changelog and update history"
    )
    
    # Access control
    is_public = models.BooleanField(
        default=False,
        help_text="Whether template is publicly accessible"
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text="Whether template is featured in listings"
    )
    
    requires_approval = models.BooleanField(
        default=False,
        help_text="Whether template usage requires approval"
    )
    
    # Publishing information
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When template was published"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time template was used to create project"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_project_templates'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_templates'
    )
    
    class Meta:
        db_table = 'projects_project_template'
        verbose_name = 'Project Template'
        verbose_name_plural = 'Project Templates'
        ordering = ['-is_featured', '-usage_count', '-created_at']
        
        indexes = [
            models.Index(fields=['template_type', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['workspace', 'status']),
            models.Index(fields=['is_public', 'status']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['usage_count']),
            models.Index(fields=['rating_average']),
            models.Index(fields=['created_at']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['slug', 'author'],
                name='unique_template_slug_per_author'
            ),
            models.CheckConstraint(
                check=models.Q(rating_average__gte=0.00) & models.Q(rating_average__lte=5.00),
                name='valid_rating_range'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version} ({self.category})"
    
    def save(self, *args, **kwargs):
        """Override save to handle automatic field updates."""
        if not self.pk:
            # Set default configurations for new templates
            if not self.project_config:
                self.project_config = self.get_default_project_config()
            if not self.springboot_config:
                self.springboot_config = self.get_default_springboot_config()
        
        super().save(*args, **kwargs)
    
    def get_default_project_config(self) -> dict:
        """Get default project configuration."""
        return {
            'enable_real_time_collaboration': True,
            'enable_version_control': True,
            'auto_save_interval': 30,
            'max_collaborators': 10,
            'default_visibility': 'PRIVATE',
            'enable_notifications': True,
        }
    
    def get_default_springboot_config(self) -> dict:
        """Get default SpringBoot configuration."""
        base_config = {
            'group_id': 'com.example',
            'version': '1.0.0',
            'java_version': '17',
            'spring_boot_version': '3.2.0',
            'packaging': 'jar',
            'server_port': 8080,
            'database_type': 'h2',
            'enable_swagger': True,
            'enable_actuator': True,
            'enable_security': False,
        }
        
        # Customize based on category
        category_configs = {
            'WEB_APPLICATION': {
                'dependencies': ['web', 'jpa', 'h2', 'thymeleaf', 'validation'],
                'enable_security': True,
            },
            'MICROSERVICE': {
                'dependencies': ['web', 'jpa', 'postgresql', 'actuator', 'eureka-client'],
                'server_port': 8081,
                'enable_actuator': True,
            },
            'REST_API': {
                'dependencies': ['web', 'jpa', 'postgresql', 'swagger', 'validation'],
                'enable_swagger': True,
            },
            'ENTERPRISE_APP': {
                'dependencies': ['web', 'jpa', 'postgresql', 'security', 'actuator', 'swagger'],
                'enable_security': True,
                'enable_actuator': True,
            },
        }
        
        category_config = category_configs.get(self.category, {})
        base_config.update(category_config)
        
        return base_config
    
    def is_accessible_by(self, user: User, workspace: 'Workspace' = None) -> bool:
        """Check if template is accessible by given user."""
        # Template author always has access
        if self.author == user:
            return True
        
        # Public templates are accessible to all
        if self.is_public and self.status == 'ACTIVE':
            return True
        
        # Organization templates accessible to workspace members
        if self.template_type == 'ORGANIZATION' and self.workspace:
            if workspace and workspace == self.workspace:
                return True
            # Check if user is member of template's workspace
            if user.project_memberships.filter(
                project__workspace=self.workspace,
                status='ACTIVE'
            ).exists():
                return True
        
        # System templates accessible to all authenticated users
        if self.template_type == 'SYSTEM' and user.is_authenticated:
            return True
        
        return False
    
    def can_edit(self, user: User) -> bool:
        """Check if user can edit this template."""
        # Template author can always edit
        if self.author == user:
            return True
        
        # Organization admins can edit organization templates
        if self.template_type == 'ORGANIZATION' and self.workspace:
            if user == self.workspace.owner:
                return True
        
        # System admins can edit system templates
        if self.template_type == 'SYSTEM' and user.is_staff:
            return True
        
        return False
    
    def publish_template(self, published_by: User):
        """Publish template for public use."""
        if self.can_edit(published_by):
            self.status = 'ACTIVE'
            self.published_at = models.functions.Now()
            self.updated_by = published_by
            self.save(update_fields=['status', 'published_at', 'updated_by', 'updated_at'])
    
    def deprecate_template(self, deprecated_by: User):
        """Mark template as deprecated."""
        if self.can_edit(deprecated_by):
            self.status = 'DEPRECATED'
            self.updated_by = deprecated_by
            self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def archive_template(self, archived_by: User):
        """Archive template."""
        if self.can_edit(archived_by):
            self.status = 'ARCHIVED'
            self.updated_by = archived_by
            self.save(update_fields=['status', 'updated_by', 'updated_at'])
    
    def increment_usage_count(self):
        """Increment usage count when template is used."""
        self.usage_count = models.F('usage_count') + 1
        self.last_used_at = models.functions.Now()
        self.save(update_fields=['usage_count', 'last_used_at'])
    
    def increment_downloads_count(self):
        """Increment downloads count."""
        self.downloads_count = models.F('downloads_count') + 1
        self.save(update_fields=['downloads_count'])
    
    def add_like(self):
        """Add like to template."""
        self.likes_count = models.F('likes_count') + 1
        self.save(update_fields=['likes_count'])
    
    def remove_like(self):
        """Remove like from template."""
        if self.likes_count > 0:
            self.likes_count = models.F('likes_count') - 1
            self.save(update_fields=['likes_count'])
    
    def update_rating(self, new_rating: float):
        """Update average rating with new rating."""
        if 0.0 <= new_rating <= 5.0:
            total_rating = float(self.rating_average) * self.rating_count + new_rating
            self.rating_count += 1
            self.rating_average = total_rating / self.rating_count
            self.save(update_fields=['rating_average', 'rating_count'])
    
    def create_project_from_template(self, project_name: str, owner: User, 
                                   workspace: 'Workspace') -> 'Project':
        """Create new project from this template."""
        from .project import Project
        
        # Increment usage count
        self.increment_usage_count()
        
        # Prepare project data from template
        project_data = {
            'name': project_name,
            'description': f"Project created from template: {self.name}",
            'owner': owner,
            'workspace': workspace,
            'settings': self.project_config.copy(),
            'springboot_config': self.springboot_config.copy(),
            'created_by': owner,
        }
        
        # Create project
        project = Project.objects.create(**project_data)
        
        # If template has UML data, create initial diagram
        if self.uml_template_data:
            # This would integrate with UML diagram creation
            pass
        
        return project
    
    def clone_template(self, new_name: str, cloned_by: User) -> 'ProjectTemplate':
        """Create a copy of this template."""
        cloned_template = ProjectTemplate.objects.create(
            name=new_name,
            slug=f"{new_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
            description=f"Cloned from: {self.name}\n\n{self.description}",
            short_description=f"Clone of {self.name}",
            template_type='USER',
            category=self.category,
            author=cloned_by,
            project_config=self.project_config.copy(),
            springboot_config=self.springboot_config.copy(),
            uml_template_data=self.uml_template_data.copy(),
            code_generation_settings=self.code_generation_settings.copy(),
            tags=self.tags.copy(),
            technologies=self.technologies.copy(),
            parent_template=self,
            created_by=cloned_by,
        )
        
        return cloned_template
    
    def get_derived_templates(self):
        """Get all templates derived from this one."""
        return self.derived_templates.filter(status__in=['ACTIVE', 'DRAFT'])
    
    def get_template_statistics(self) -> dict:
        """Get comprehensive template statistics."""
        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'version': self.version,
            'category': self.category,
            'template_type': self.template_type,
            'status': self.status,
            'author': {
                'id': self.author.id,
                'username': self.author.username,
                'email': self.author.email
            },
            'usage_stats': {
                'usage_count': self.usage_count,
                'likes_count': self.likes_count,
                'downloads_count': self.downloads_count,
                'rating_average': float(self.rating_average),
                'rating_count': self.rating_count,
            },
            'visibility': {
                'is_public': self.is_public,
                'is_featured': self.is_featured,
                'requires_approval': self.requires_approval,
            },
            'metadata': {
                'tags': self.tags,
                'technologies': self.technologies,
                'prerequisites': self.prerequisites,
            },
            'dates': {
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'published_at': self.published_at.isoformat() if self.published_at else None,
                'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            }
        }
