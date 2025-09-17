"""
GenerationRequest serializers for SpringBoot code generation requests.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import GenerationRequest
from apps.uml_diagrams.serializers import UMLDiagramSerializer

User = get_user_model()


class GenerationRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing generation requests.
    """
    
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    diagram_name = serializers.CharField(source='diagram.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    progress_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'project_name', 'generation_type', 'status', 'status_display', 
            'progress_percentage', 'progress_display',
            'requested_by_username', 'diagram_name',
            'created_at', 'started_at', 'completed_at',
            'generated_files_count', 'output_path'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.CharField())
    def get_progress_display(self, obj) -> str:
        """Get human-readable progress display."""
        if obj.status == 'COMPLETED':
            return f"✅ Completed ({obj.generated_files_count} files)"
        elif obj.status == 'FAILED':
            return f"❌ Failed"
        elif obj.status == 'PROCESSING':
            return f"🔄 {obj.progress_percentage}% - Processing..."
        elif obj.status == 'CANCELLED':
            return f"⏹️ Cancelled"
        else:
            return f"⏳ Pending"


class GenerationRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new generation requests.
    """
    
    class Meta:
        model = GenerationRequest
        fields = [
            'project', 'diagram', 'generation_type', 'generation_config',
            'selected_classes', 'template_overrides'
        ]
    
    def validate_generation_config(self, value):
        """Validate SpringBoot configuration."""
        required_fields = ['group_id', 'artifact_id', 'java_version']
        
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Missing required config field: {field}")
        
        # Validate group_id format
        group_id = value.get('group_id', '')
        if not all(part.replace('_', '').replace('-', '').isalnum() for part in group_id.split('.')):
            raise serializers.ValidationError(
                "group_id must contain only alphanumeric characters, dots, hyphens, and underscores"
            )
        
        # Validate artifact_id format
        artifact_id = value.get('artifact_id', '')
        if not artifact_id.replace('-', '').replace('_', '').isalnum():
            raise serializers.ValidationError(
                "artifact_id must contain only alphanumeric characters, hyphens, and underscores"
            )
        
        # Validate Java version
        java_version = value.get('java_version', '')
        valid_java_versions = ['8', '11', '17', '21']
        if java_version not in valid_java_versions:
            raise serializers.ValidationError(
                f"java_version must be one of: {', '.join(valid_java_versions)}"
            )
        
        return value


class GenerationRequestDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for generation requests.
    """
    
    diagram = UMLDiagramSerializer(read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    requested_by = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    generation_type_display = serializers.CharField(source='get_generation_type_display', read_only=True)
    progress_display = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    download_url_secure = serializers.SerializerMethodField()
    
    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'project', 'project_name', 'diagram', 'requested_by',
            'generation_type', 'generation_type_display', 'status', 'status_display',
            'generation_config', 'selected_classes', 'template_overrides', 'error_details',
            'progress_percentage', 'progress_display', 'progress_details',
            'generated_files_count', 'generation_metadata', 'output_path',
            'download_url', 'download_url_secure', 'download_expires_at',
            'duration_seconds', 'created_at', 'started_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'progress_percentage', 'progress_details',
            'generated_files_count', 'generation_metadata', 'output_path',
            'download_url', 'download_expires_at', 'created_at',
            'started_at', 'completed_at', 'error_details'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_requested_by(self, obj) -> dict:
        """Get requested by user information."""
        if obj.requested_by:
            return {
                'id': obj.requested_by.id,
                'username': obj.requested_by.username,
                'email': obj.requested_by.email,
                'full_name': obj.requested_by.get_full_name() if hasattr(obj.requested_by, 'get_full_name') else ''
            }
        return None
    
    @extend_schema_field(serializers.CharField())
    def get_progress_display(self, obj) -> str:
        """Get human-readable progress display."""
        if obj.status == 'COMPLETED':
            return f"✅ Completed - Generated {obj.generated_files_count} files"
        elif obj.status == 'FAILED':
            return f"❌ Failed - Check error details"
        elif obj.status == 'PROCESSING':
            return f"🔄 {obj.progress_percentage}% - Processing..."
        elif obj.status == 'CANCELLED':
            return f"⏹️ Cancelled - Generation was stopped"
        else:
            return f"⏳ Pending - Waiting to start"
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration_seconds(self, obj) -> float:
        """Get generation duration in seconds."""
        if obj.started_at and obj.completed_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        elif obj.started_at:
            from django.utils import timezone
            return (timezone.now() - obj.started_at).total_seconds()
        return None
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_download_url_secure(self, obj):
        """Get secure download URL if available."""
        if obj.status == 'COMPLETED' and obj.download_url:
            return obj.download_url
        return None


# Alias for backward compatibility
GenerationRequestSerializer = GenerationRequestDetailSerializer


class GenerationRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating generation request configuration.
    """
    
    class Meta:
        model = GenerationRequest
        fields = ['generation_config', 'selected_classes', 'template_overrides']
    
    def validate(self, attrs):
        """Validate that request can be updated."""
        instance = self.instance
        
        if instance and instance.status in ['PROCESSING', 'COMPLETED']:
            raise serializers.ValidationError(
                "Cannot update request that is in progress or completed"
            )
        
        return attrs
    
    def validate_generation_config(self, value):
        """Validate SpringBoot configuration updates."""
        # Use same validation as create serializer
        create_serializer = GenerationRequestCreateSerializer()
        return create_serializer.validate_generation_config(value)
