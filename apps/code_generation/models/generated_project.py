"""
GeneratedProject model for managing generated SpringBoot project metadata.
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid
import os

User = get_user_model()


class GeneratedProject(models.Model):
    """
    Generated SpringBoot project metadata and file management.
    """
    
    class ProjectStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVED = 'ARCHIVED', 'Archived'
        DELETED = 'DELETED', 'Deleted'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation_request = models.OneToOneField(
        'code_generation.GenerationRequest',
        on_delete=models.CASCADE,
        related_name='generated_project'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='generated_projects'
    )
    diagram = models.ForeignKey(
        'uml_diagrams.UMLDiagram',
        on_delete=models.CASCADE,
        related_name='generated_projects'
    )
    project_name = models.CharField(max_length=255)
    project_description = models.TextField(blank=True)
    springboot_config = models.JSONField(
        help_text="Complete SpringBoot project configuration"
    )
    file_structure = models.JSONField(
        default=dict,
        help_text="Generated project file structure and metadata"
    )
    storage_path = models.CharField(
        max_length=500,
        help_text="File system path to generated project"
    )
    zip_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to compressed project archive"
    )
    zip_file_size = models.BigIntegerField(default=0)
    total_files = models.PositiveIntegerField(default=0)
    total_lines_of_code = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=ProjectStatus.choices,
        default=ProjectStatus.ACTIVE
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='generated_projects'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    download_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'generated_projects'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['generated_by', 'generated_at']),
            models.Index(fields=['diagram', 'status']),
            models.Index(fields=['status', 'generated_at']),
        ]
    
    def __str__(self):
        return f"Generated Project: {self.project_name}"
    
    def get_file_structure_tree(self) -> dict:
        """Get hierarchical file structure representation."""
        return self.file_structure.get('tree', {})
    
    def get_generated_files_list(self) -> list:
        """Get flat list of all generated files."""
        return self.file_structure.get('files', [])
    
    def get_file_by_path(self, file_path: str) -> dict:
        """Get file information by path."""
        for file_info in self.get_generated_files_list():
            if file_info.get('path') == file_path:
                return file_info
        return None
    
    def read_file_content(self, file_path: str) -> str:
        """Read content of generated file."""
        try:
            full_path = os.path.join(self.storage_path, file_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    
    def get_project_statistics(self) -> dict:
        """Get comprehensive project statistics."""
        file_types = {}
        total_size = 0
        
        for file_info in self.get_generated_files_list():
            file_ext = file_info.get('extension', 'unknown')
            file_size = file_info.get('size', 0)
            
            if file_ext not in file_types:
                file_types[file_ext] = {'count': 0, 'size': 0, 'lines': 0}
            
            file_types[file_ext]['count'] += 1
            file_types[file_ext]['size'] += file_size
            file_types[file_ext]['lines'] += file_info.get('lines_of_code', 0)
            total_size += file_size
        
        return {
            'total_files': self.total_files,
            'total_size': total_size,
            'total_lines_of_code': self.total_lines_of_code,
            'file_types': file_types,
            'generated_classes': self.count_generated_classes(),
            'test_coverage': self.calculate_test_coverage()
        }
    
    def count_generated_classes(self) -> int:
        """Count number of generated Java classes."""
        java_files = [f for f in self.get_generated_files_list() 
                     if f.get('extension') == '.java' and 'test' not in f.get('path', '').lower()]
        return len(java_files)
    
    def calculate_test_coverage(self) -> float:
        """Calculate test coverage percentage."""
        main_classes = self.count_generated_classes()
        test_files = [f for f in self.get_generated_files_list() 
                     if f.get('extension') == '.java' and 'test' in f.get('path', '').lower()]
        
        if main_classes == 0:
            return 0.0
        
        return (len(test_files) / main_classes) * 100
    
    def create_zip_archive(self) -> str:
        """Create ZIP archive of generated project."""
        import zipfile
        import tempfile
        
        zip_filename = f"{self.project_name}_{self.id}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.storage_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, self.storage_path)
                        zipf.write(file_path, arc_path)
            
            # Update ZIP file info
            self.zip_file_path = zip_path
            self.zip_file_size = os.path.getsize(zip_path)
            self.save(update_fields=['zip_file_path', 'zip_file_size'])
            
            return zip_path
            
        except Exception as e:
            raise Exception(f"Failed to create ZIP archive: {str(e)}")
    
    def increment_download_count(self) -> None:
        """Increment download counter."""
        self.download_count += 1
        self.save(update_fields=['download_count', 'last_accessed'])
    
    def archive_project(self) -> None:
        """Archive the generated project."""
        self.status = self.ProjectStatus.ARCHIVED
        self.save(update_fields=['status'])
    
    def delete_project_files(self) -> bool:
        """Delete physical project files from storage."""
        import shutil
        
        try:
            if os.path.exists(self.storage_path):
                shutil.rmtree(self.storage_path)
            
            if self.zip_file_path and os.path.exists(self.zip_file_path):
                os.remove(self.zip_file_path)
            
            self.status = self.ProjectStatus.DELETED
            self.save(update_fields=['status'])
            
            return True
            
        except Exception:
            return False
    
    def get_springboot_info(self) -> dict:
        """Get SpringBoot project information."""
        config = self.springboot_config
        return {
            'group_id': config.get('group_id'),
            'artifact_id': config.get('artifact_id'),
            'version': config.get('version'),
            'java_version': config.get('java_version'),
            'spring_boot_version': config.get('spring_boot_version'),
            'packaging': config.get('packaging'),
            'dependencies': config.get('dependencies', []),
            'features_enabled': config.get('features', {})
        }
    
    def get_download_info(self) -> dict:
        """Get project download information."""
        return {
            'project_id': str(self.id),
            'project_name': self.project_name,
            'zip_file_size': self.zip_file_size,
            'total_files': self.total_files,
            'download_count': self.download_count,
            'generated_at': self.generated_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat()
        }
    
    @classmethod
    def cleanup_old_projects(cls, days_old: int = 30) -> int:
        """Clean up old generated projects."""
        from django.utils import timezone
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        old_projects = cls.objects.filter(
            generated_at__lt=cutoff_date,
            status=cls.ProjectStatus.ACTIVE
        )
        
        cleaned_count = 0
        for project in old_projects:
            if project.delete_project_files():
                cleaned_count += 1
        
        return cleaned_count
