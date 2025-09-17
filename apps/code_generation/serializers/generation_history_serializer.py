"""
GenerationHistory serializers for SpringBoot code generation history tracking.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import GenerationHistory

User = get_user_model()


class GenerationHistorySerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for generation history entries.
    """
    
    generation_request = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)
    
    # Timestamp formatting
    timestamp_display = serializers.SerializerMethodField()
    
    # Change analysis
    changes_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = GenerationHistory
        fields = [
            'id', 'generation_request', 'user', 'action_type', 'action_display',
            'action_details', 'changes_summary', 'execution_context', 
            'timestamp', 'timestamp_display', 'ip_address', 'user_agent'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.DictField())
    def get_generation_request(self, obj) -> dict:
        """Get generation request information."""
        if obj.generation_request:
            return {
                'id': str(obj.generation_request.id),
                'project_name': obj.generation_request.project_name,
                'status': obj.generation_request.status
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_user(self, obj) -> dict:
        """Get user information."""
        if obj.performed_by:
            return {
                'id': obj.performed_by.id,
                'username': obj.performed_by.username,
                'email': obj.performed_by.email
            }
        return None
    
    @extend_schema_field(serializers.CharField())
    def get_timestamp_display(self, obj) -> str:
        """Get human-readable timestamp."""
        from django.utils import timezone
        now = timezone.now()
        delta = now - obj.timestamp
        
        if delta.total_seconds() < 60:
            return "Just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.days < 7:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        else:
            return obj.timestamp.strftime('%Y-%m-%d %H:%M')
    
    @extend_schema_field(serializers.DictField())
    def get_changes_summary(self, obj) -> dict:
        """Get summary of changes made."""
        if not obj.action_details:
            return None
        
        summary = {}
        
        # Analyze different types of changes based on action
        if obj.action_type == 'GENERATION_STARTED':
            summary['type'] = 'creation'
            summary['description'] = f"Created new generation request: {obj.generation_request.project_name if obj.generation_request else 'Unknown'}"
        
        elif obj.action_type == 'CONFIG_UPDATED':
            summary['type'] = 'configuration_update'
            summary['description'] = "Updated SpringBoot configuration"
        
        elif obj.action_type == 'PROJECT_DELETED':
            summary['type'] = 'deletion'
            summary['description'] = "Deleted generation request"
        
        elif obj.action_type == 'GENERATION_COMPLETED':
            summary['type'] = 'generation_completion'
            files_count = obj.action_details.get('files_generated', 0)
            summary['description'] = f"Completed generation - {files_count} files created"
        
        elif obj.action_type == 'GENERATION_FAILED':
            summary['type'] = 'generation_failure'
            error = obj.action_details.get('error_message', 'Unknown error')[:50]
            summary['description'] = f"Generation failed: {error}"
        
        elif obj.action_type == 'GENERATION_CANCELLED':
            summary['type'] = 'generation_cancellation'
            summary['description'] = "Cancelled code generation"
        
        elif obj.action_type == 'PROJECT_DOWNLOADED':
            summary['type'] = 'download'
            download_count = obj.action_details.get('download_count', 0)
            summary['description'] = f"Downloaded project (#{download_count})"
        
        else:
            summary['type'] = 'other'
            summary['description'] = obj.action_type.replace('_', ' ').title()
        
        return summary


class GenerationHistoryListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing generation history.
    """
    
    generation_request_name = serializers.CharField(source='generation_request.project_name', read_only=True)
    username = serializers.CharField(source='performed_by.username', read_only=True)
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)
    timestamp_display = serializers.SerializerMethodField()
    
    class Meta:
        model = GenerationHistory
        fields = [
            'id', 'generation_request_name', 'username', 
            'action_type', 'action_display', 'timestamp', 'timestamp_display'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.CharField())
    def get_timestamp_display(self, obj) -> str:
        """Get human-readable timestamp."""
        # Reuse the method from the full serializer
        full_serializer = GenerationHistorySerializer()
        return full_serializer.get_timestamp_display(obj)


class GenerationHistoryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating generation history entries (internal use).
    """
    
    class Meta:
        model = GenerationHistory
        fields = [
            'generation_request', 'performed_by', 'action_type', 'action_details', 
            'execution_context', 'ip_address', 'user_agent'
        ]
    
    def validate_action_type(self, value):
        """Validate action type."""
        valid_actions = [choice[0] for choice in GenerationHistory.ActionType.choices]
        
        if value not in valid_actions:
            raise serializers.ValidationError(f"action_type must be one of: {', '.join(valid_actions)}")
        
        return value
