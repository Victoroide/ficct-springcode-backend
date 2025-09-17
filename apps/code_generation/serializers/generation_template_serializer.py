"""
GenerationTemplate serializers for SpringBoot code generation templates.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import GenerationTemplate

User = get_user_model()


class GenerationTemplateCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new generation templates.
    """
    
    class Meta:
        model = GenerationTemplate
        fields = [
            'name', 'description', 'template_type', 'framework_version',
            'template_content', 'default_variables', 'required_variables',
            'output_filename_pattern', 'output_directory', 'file_extension'
        ]
    
    def validate_name(self, value):
        """Validate template name."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Template name must be at least 3 characters long")
        
        if len(value) > 100:
            raise serializers.ValidationError("Template name must not exceed 100 characters")
        
        return value.strip()
    
    def validate_template_type(self, value):
        """Validate template type."""
        valid_types = ['ENTITY', 'REPOSITORY', 'SERVICE', 'CONTROLLER', 'DTO', 'CONFIG', 'TEST', 'CUSTOM']
        if value not in valid_types:
            raise serializers.ValidationError(f"template_type must be one of: {', '.join(valid_types)}")
        
        return value
    
    def validate_template_content(self, value):
        """Validate template content."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Template content must be at least 10 characters long")
        
        # Basic Jinja2 syntax validation
        try:
            from jinja2 import Template
            Template(value)
        except Exception as e:
            raise serializers.ValidationError(f"Invalid Jinja2 template syntax: {str(e)}")
        
        return value
    
    def validate_required_variables(self, value):
        """Validate required variables."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Required variables must be a list")
        
        for var in value:
            if not isinstance(var, str):
                raise serializers.ValidationError("Each required variable must be a string")
        
        return value


class GenerationTemplateSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for generation templates.
    """
    
    created_by = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    
    # Usage statistics
    usage_statistics = serializers.SerializerMethodField()
    
    # Template validation info
    is_valid_template = serializers.SerializerMethodField()
    validation_errors = serializers.SerializerMethodField()
    
    # File information
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = GenerationTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'template_type_display',
            'template_content', 'content_preview', 'default_variables', 'required_variables',
            'output_filename_pattern', 'output_directory', 'file_extension', 'framework_version',
            'is_active', 'is_system_template', 'version',
            'is_valid_template', 'validation_errors',
            'created_by', 'status_display', 'created_at', 'updated_at', 'usage_statistics'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_created_by(self, obj):
        """Get created by user information."""
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'username': obj.created_by.username,
                'email': obj.created_by.email
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_usage_statistics(self, obj):
        """Get template usage statistics."""
        return {
            'usage_count': 0,  # TODO: Implement usage tracking
            'last_used_at': None,
            'avg_generation_time': 0.0,
            'success_rate': 100.0
        }
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_valid_template(self, obj):
        """Check if template is valid."""
        try:
            obj.validate_template()
            return True
        except Exception:
            return False
    
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_validation_errors(self, obj):
        """Get template validation errors."""
        try:
            obj.validate_template()
            return []
        except Exception as e:
            return [str(e)]
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_content_preview(self, obj):
        """Get preview of template content."""
        if obj.template_content:
            preview = obj.template_content[:500]
            if len(obj.template_content) > 500:
                preview += "..."
            return preview
        return None
    
    def get_is_active_display(self, obj):
        """Get human-readable active status."""
        return "Active" if obj.is_active else "Inactive"


class GenerationTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing generation templates.
    """
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    is_active_display = serializers.SerializerMethodField()
    
    class Meta:
        model = GenerationTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'template_type_display',
            'is_active', 'is_active_display', 'is_system_template', 'version',
            'framework_version', 'created_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.CharField())
    def get_is_active_display(self, obj):
        """Get human-readable active status."""
        return "Active" if obj.is_active else "Inactive"


class GenerationTemplateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating generation templates.
    """
    
    class Meta:
        model = GenerationTemplate
        fields = [
            'name', 'description', 'template_content', 'default_variables', 
            'required_variables', 'output_filename_pattern', 'output_directory',
            'file_extension', 'is_active'
        ]
    
    def validate(self, attrs):
        """Validate that template can be updated."""
        instance = self.instance
        
        if instance and instance.is_system_template:
            # Only allow is_active updates for system templates
            allowed_fields = {'is_active'}
            provided_fields = set(attrs.keys())
            if not provided_fields <= allowed_fields:
                raise serializers.ValidationError(
                    "System templates can only have their is_active field updated"
                )
        
        return attrs
    
    def validate_template_content(self, value):
        """Validate updated template content."""
        if value is not None:
            create_serializer = GenerationTemplateCreateSerializer()
            return create_serializer.validate_content(value)
        return value
