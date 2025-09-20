"""
GeneratedProject serializers for SpringBoot generated project management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import GeneratedProject

User = get_user_model()


class GeneratedProjectListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing generated projects.
    """
    
    generation_request_name = serializers.CharField(source='generation_request.project_name', read_only=True)
    created_by_username = serializers.CharField(source='generation_request.created_by.username', read_only=True)
    file_count_display = serializers.SerializerMethodField()
    size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedProject
        fields = [
            'id', 'project_name', 'generation_request_name',
            'created_by_username', 'total_files', 'file_count_display',
            'zip_file_size', 'size_display', 'download_count',
            'generated_at', 'status'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.CharField())
    def get_file_count_display(self, obj) -> str:
        """Get human-readable file count."""
        count = obj.total_files
        if count == 0:
            return "No files"
        elif count == 1:
            return "1 file"
        else:
            return f"{count} files"
    
    @extend_schema_field(serializers.CharField())
    def get_size_display(self, obj) -> str:
        """Get human-readable file size."""
        if not obj.zip_file_size:
            return "0 B"
        
        size = obj.zip_file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class GeneratedProjectSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for generated projects.
    """
    
    generation_request = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    
    # File and size information
    file_count_display = serializers.SerializerMethodField()
    size_display = serializers.SerializerMethodField()
    
    # Download information
    download_url = serializers.SerializerMethodField()
    is_downloadable = serializers.SerializerMethodField()
    expires_in_hours = serializers.SerializerMethodField()
    
    # Project statistics
    project_statistics = serializers.SerializerMethodField()
    
    # File breakdown
    file_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedProject
        fields = [
            'id', 'project_name', 'project_description',
            'generation_request', 'created_by',
            'total_files', 'file_count_display', 'zip_file_size', 'size_display',
            'zip_file_path', 'download_url', 'is_downloadable', 'expires_in_hours',
            'download_count', 'last_accessed',
            'generated_at', 'status', 'is_archived', 'archived_at', 'restored_at',
            'file_structure', 'file_breakdown', 'project_statistics'
        ]
        read_only_fields = [
            'id', 'total_files', 'zip_file_size', 'zip_file_path',
            'download_count', 'last_accessed', 'status',
            'generated_at', 'last_accessed', 'is_archived', 'archived_at', 'restored_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_generation_request(self, obj) -> dict:
        """Get generation request information."""
        if obj.generation_request:
            return {
                'id': str(obj.generation_request.id),
                'project_name': obj.generation_request.project_name,
                'diagram_name': obj.generation_request.diagram.name if obj.generation_request.diagram else None,
                'config': obj.generation_request.config
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_created_by(self, obj) -> dict:
        """Get created by user information."""
        if obj.generation_request and obj.generation_request.created_by:
            user = obj.generation_request.created_by
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name() if hasattr(user, 'get_full_name') else ''
            }
        return None
    
    @extend_schema_field(serializers.CharField())
    def get_file_count_display(self, obj) -> str:
        """Get human-readable file count."""
        return GeneratedProjectListSerializer().get_file_count_display(obj)
    
    @extend_schema_field(serializers.CharField())
    def get_size_display(self, obj) -> str:
        """Get human-readable file size."""
        return GeneratedProjectListSerializer().get_size_display(obj)
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_download_url(self, obj) -> str:
        """Get secure download URL if available."""
        if obj.is_downloadable():
            return obj.get_download_url()
        return None
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_downloadable(self, obj) -> bool:
        """Check if project is downloadable."""
        return obj.is_downloadable()
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_expires_in_hours(self, obj) -> float:
        """Get hours until expiration."""
        if obj.expires_at:
            from django.utils import timezone
            now = timezone.now()
            
            if obj.expires_at > now:
                delta = obj.expires_at - now
                hours = delta.total_seconds() / 3600
                return round(hours, 1)
            else:
                return 0
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_project_statistics(self, obj) -> dict:
        """Get comprehensive project statistics."""
        return obj.get_project_statistics()
    
    @extend_schema_field(serializers.DictField())
    def get_file_breakdown(self, obj) -> dict:
        """Get file breakdown by type."""
        return obj.get_file_breakdown()


class GeneratedProjectCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating generated projects (used internally).
    """
    
    class Meta:
        model = GeneratedProject
        fields = [
            'generation_request', 'project_name', 'description', 'version',
            'file_count', 'total_size', 'archive_path', 'metadata',
            'file_structure', 'expires_at'
        ]
    
    def validate_project_name(self, value):
        """Validate project name."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Project name must be at least 3 characters long")
        
        if len(value) > 100:
            raise serializers.ValidationError("Project name must not exceed 100 characters")
        
        return value.strip()
    
    def validate_file_count(self, value):
        """Validate file count."""
        if value < 0:
            raise serializers.ValidationError("File count cannot be negative")
        
        return value
    
    def validate_total_size(self, value):
        """Validate total size."""
        if value < 0:
            raise serializers.ValidationError("Total size cannot be negative")
        
        # Check maximum size limit (e.g., 100MB)
        max_size = 100 * 1024 * 1024  # 100MB in bytes
        if value > max_size:
            raise serializers.ValidationError(f"Project size exceeds maximum limit of {max_size / (1024*1024):.0f}MB")
        
        return value


class GeneratedProjectUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating generated projects.
    """
    
    class Meta:
        model = GeneratedProject
        fields = ['project_description', 'file_structure']
    
    def validate(self, attrs):
        """Validate that project can be updated."""
        instance = self.instance
        
        if instance and instance.is_archived:
            raise serializers.ValidationError("Cannot update archived project")
        
        return attrs
