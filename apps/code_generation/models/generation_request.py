"""
GenerationRequest model for tracking SpringBoot code generation jobs.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class GenerationRequest(models.Model):
    """
    SpringBoot code generation job tracking with comprehensive configuration.
    """
    
    class GenerationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    class GenerationType(models.TextChoices):
        FULL_PROJECT = 'FULL_PROJECT', 'Full SpringBoot Project'
        ENTITIES_ONLY = 'ENTITIES_ONLY', 'JPA Entities Only'
        REPOSITORIES_ONLY = 'REPOSITORIES_ONLY', 'Repositories Only'
        SERVICES_ONLY = 'SERVICES_ONLY', 'Services Only'
        CONTROLLERS_ONLY = 'CONTROLLERS_ONLY', 'Controllers Only'
        CUSTOM = 'CUSTOM', 'Custom Selection'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='generation_requests'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='generation_requests'
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='generation_requests'
    )
    generation_type = models.CharField(
        max_length=20,
        choices=GenerationType.choices,
        default=GenerationType.FULL_PROJECT
    )
    status = models.CharField(
        max_length=15,
        choices=GenerationStatus.choices,
        default=GenerationStatus.PENDING
    )
    generation_config = models.JSONField(
        default=dict,
        help_text="SpringBoot project generation configuration"
    )
    selected_classes = models.JSONField(
        default=list,
        help_text="Selected UML classes for generation"
    )
    template_overrides = models.JSONField(
        default=dict,
        help_text="Custom template configurations"
    )
    output_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Generated files storage path"
    )
    download_url = models.URLField(
        blank=True,
        help_text="Temporary download URL for generated project"
    )
    download_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Download link expiration"
    )
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    progress_details = models.JSONField(
        default=dict,
        help_text="Detailed progress information"
    )
    error_details = models.JSONField(
        default=dict,
        help_text="Error information if generation failed"
    )
    generated_files_count = models.PositiveIntegerField(default=0)
    generation_metadata = models.JSONField(
        default=dict,
        help_text="Additional generation metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'generation_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['requested_by', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['diagram', 'generation_type']),
        ]
    
    def __str__(self):
        return f"Generation {self.id} - {self.get_generation_type_display()}"
    
    def start_generation(self) -> None:
        """Mark generation as started."""
        self.status = self.GenerationStatus.PROCESSING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def complete_generation(self, output_path: str, files_count: int,
                          download_url: str = None) -> None:
        """Mark generation as completed."""
        self.status = self.GenerationStatus.COMPLETED
        self.completed_at = timezone.now()
        self.output_path = output_path
        self.generated_files_count = files_count
        self.progress_percentage = 100
        
        if download_url:
            self.download_url = download_url
            # Set download expiration to 24 hours
            self.download_expires_at = timezone.now() + timezone.timedelta(hours=24)
        
        self.save(update_fields=[
            'status', 'completed_at', 'output_path', 'generated_files_count',
            'progress_percentage', 'download_url', 'download_expires_at'
        ])
    
    def fail_generation(self, error_details: dict) -> None:
        """Mark generation as failed."""
        self.status = self.GenerationStatus.FAILED
        self.completed_at = timezone.now()
        self.error_details = error_details
        self.save(update_fields=['status', 'completed_at', 'error_details'])
    
    def cancel_generation(self) -> None:
        """Cancel pending or processing generation."""
        if self.status in [self.GenerationStatus.PENDING, self.GenerationStatus.PROCESSING]:
            self.status = self.GenerationStatus.CANCELLED
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
    
    def update_progress(self, percentage: int, details: dict = None) -> None:
        """Update generation progress."""
        self.progress_percentage = min(100, max(0, percentage))
        if details:
            self.progress_details.update(details)
        self.save(update_fields=['progress_percentage', 'progress_details'])
    
    def is_download_expired(self) -> bool:
        """Check if download link has expired."""
        return (self.download_expires_at and 
                timezone.now() > self.download_expires_at)
    
    def get_generation_duration(self) -> int:
        """Get generation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0
    
    def get_springboot_config(self) -> dict:
        """Get SpringBoot project configuration."""
        default_config = {
            'group_id': 'com.enterprise.generated',
            'artifact_id': self.project.name.lower().replace(' ', '-'),
            'version': '1.0.0',
            'java_version': '17',
            'spring_boot_version': '3.1.0',
            'packaging': 'jar',
            'dependencies': [
                'spring-boot-starter-web',
                'spring-boot-starter-data-jpa',
                'spring-boot-starter-validation',
                'spring-boot-starter-test',
                'h2',
                'postgresql'
            ],
            'features': {
                'swagger': True,
                'security': True,
                'auditing': True,
                'validation': True
            }
        }
        
        # Merge with custom configuration
        config = default_config.copy()
        config.update(self.generation_config)
        return config
    
    def get_selected_uml_classes(self) -> list:
        """Get UML classes selected for generation."""
        if self.selected_classes:
            # Filter diagram classes by selected IDs
            all_classes = self.diagram.get_classes()
            return [cls for cls in all_classes if cls.get('id') in self.selected_classes]
        else:
            # Return all classes if none specifically selected
            return self.diagram.get_classes()
    
    def estimate_generation_time(self) -> int:
        """Estimate generation time in seconds."""
        classes_count = len(self.get_selected_uml_classes())
        relationships_count = len(self.diagram.get_relationships())
        
        # Base time + time per class + time per relationship
        base_time = 5  # seconds
        time_per_class = 2  # seconds
        time_per_relationship = 1  # seconds
        
        estimated_time = base_time + (classes_count * time_per_class) + (relationships_count * time_per_relationship)
        
        # Add extra time for full project generation
        if self.generation_type == self.GenerationType.FULL_PROJECT:
            estimated_time += 10
        
        return estimated_time
    
    @classmethod
    def cleanup_expired_downloads(cls) -> int:
        """Clean up expired download links."""
        expired_count = cls.objects.filter(
            download_expires_at__lt=timezone.now(),
            download_url__isnull=False
        ).update(
            download_url='',
            download_expires_at=None
        )
        return expired_count
