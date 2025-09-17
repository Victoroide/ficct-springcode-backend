"""
ProjectTemplate serializers for project template management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import ProjectTemplate, Workspace

User = get_user_model()


class ProjectTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing project templates.
    """
    
    author_username = serializers.CharField(source='author.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    usage_count_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectTemplate
        fields = [
            'id', 'name', 'description', 'category', 'category_display',
            'template_type', 'template_type_display', 'is_public', 'is_featured',
            'author_username', 'usage_count', 'usage_count_display', 'rating_average',
            'created_at', 'updated_at', 'last_used_at'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.CharField())
    def get_usage_count_display(self, obj) -> str:
        """Get human-readable usage count."""
        count = obj.usage_count
        if count == 0:
            return "Not used"
        elif count == 1:
            return "Used once"
        elif count < 100:
            return f"Used {count} times"
        elif count < 1000:
            return f"Used {count//100}00+ times"
        else:
            return f"Used {count//1000}k+ times"


class ProjectTemplateCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new project templates.
    """
    
    class Meta:
        model = ProjectTemplate
        fields = [
            'name', 'description', 'category', 'template_type', 'is_public',
            'springboot_config', 'uml_template_data', 'code_generation_settings',
            'tags', 'technologies'
        ]
    
    def validate_name(self, value):
        """Validate template name."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Template name must be at least 3 characters long")
        
        if len(value) > 100:
            raise serializers.ValidationError("Template name must not exceed 100 characters")
        
        # Check for duplicate names by the same author
        user = self.context['request'].user
        existing = ProjectTemplate.objects.filter(
            name__iexact=value.strip(),
            author=user,
            is_deleted=False
        ).exists()
        
        if existing:
            raise serializers.ValidationError("You already have a template with this name")
        
        return value.strip()
    
    def validate_category(self, value):
        """Validate template category."""
        valid_categories = [
            'WEB_APPLICATION', 'MICROSERVICE', 'REST_API', 'CRUD_APPLICATION',
            'ENTERPRISE_APPLICATION', 'STARTER_TEMPLATE', 'CUSTOM'
        ]
        if value not in valid_categories:
            raise serializers.ValidationError(f"category must be one of: {', '.join(valid_categories)}")
        
        return value
    
    def validate_template_type(self, value):
        """Validate template type."""
        valid_types = ['BASIC', 'ADVANCED', 'ENTERPRISE', 'CUSTOM']
        if value not in valid_types:
            raise serializers.ValidationError(f"template_type must be one of: {', '.join(valid_types)}")
        
        return value
    
    def validate_springboot_config(self, value):
        """Validate SpringBoot configuration."""
        if value:
            required_fields = ['group_id', 'artifact_id', 'java_version', 'springboot_version']
            
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"Missing required SpringBoot config field: {field}")
            
            # Validate group_id format
            group_id = value.get('group_id', '')
            if not all(part.replace('_', '').replace('-', '').isalnum() for part in group_id.split('.')):
                raise serializers.ValidationError(
                    "group_id must contain only alphanumeric characters, dots, hyphens, and underscores"
                )
        
        return value
    
    def validate_uml_template_data(self, value):
        """Validate UML template data structure."""
        if value:
            # Basic structure validation
            if not isinstance(value, dict):
                raise serializers.ValidationError("uml_template_data must be a valid JSON object")
            
            # Check for required sections
            required_sections = ['classes', 'relationships']
            for section in required_sections:
                if section not in value:
                    raise serializers.ValidationError(f"Missing required UML section: {section}")
        
        return value


class ProjectTemplateSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for project templates.
    """
    
    author = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    
    # Usage statistics
    usage_statistics = serializers.SerializerMethodField()
    
    # Access information
    access_info = serializers.SerializerMethodField()
    
    # Template validation
    is_valid_template = serializers.SerializerMethodField()
    validation_errors = serializers.SerializerMethodField()
    
    # User permissions
    user_permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectTemplate
        fields = [
            'id', 'name', 'description', 'category', 'category_display',
            'template_type', 'template_type_display', 'status', 'author',
            'springboot_config', 'uml_template_data', 'code_generation_settings',
            'tags', 'technologies', 'usage_count',
            'usage_statistics', 'access_info', 'is_valid_template', 'validation_errors',
            'user_permissions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'usage_count', 'rating_average', 'rating_count',
            'created_at', 'updated_at', 'last_used_at', 'published_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_author(self, obj) -> dict:
        """Get author information."""
        if obj.author:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'email': obj.author.email,
                'full_name': obj.author.get_full_name() if hasattr(obj.author, 'get_full_name') else ''
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_usage_statistics(self, obj) -> dict:
        """Get comprehensive usage statistics."""
        return obj.get_usage_statistics()
    
    @extend_schema_field(serializers.DictField())
    def get_access_info(self, obj) -> dict:
        """Get template access information."""
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        return {
            'is_accessible': obj.is_accessible_by_user(user) if user else obj.is_public,
            'access_reason': obj.get_access_reason(user) if user else ('public' if obj.is_public else 'private'),
            'requires_subscription': obj.requires_subscription(),
            'compatible_workspaces': obj.get_compatible_workspace_types()
        }
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_valid_template(self, obj) -> bool:
        """Check if template configuration is valid."""
        try:
            obj.validate_template()
            return True
        except Exception:
            return False
    
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_validation_errors(self, obj) -> list:
        """Get template validation errors."""
        try:
            obj.validate_template()
            return []
        except Exception as e:
            return [str(e)]
    
    @extend_schema_field(serializers.DictField())
    def get_user_permissions(self, obj) -> dict:
        """Get current user's permissions for this template."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        return {
            'can_view': obj.is_accessible_by_user(user),
            'can_edit': obj.author == user or user.is_staff,
            'can_delete': obj.author == user or user.is_staff,
            'can_clone': obj.is_accessible_by_user(user),
            'can_rate': user != obj.author and obj.is_accessible_by_user(user),
            'is_author': obj.author == user
        }


class ProjectTemplateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating project templates.
    """
    
    class Meta:
        model = ProjectTemplate
        fields = [
            'name', 'description', 'category', 'template_type', 'status',
            'springboot_config', 'uml_template_data', 'code_generation_settings',
            'tags', 'technologies'
        ]
    
    def validate(self, attrs):
        """Validate update permissions."""
        user = self.context['request'].user
        instance = self.instance
        
        if instance.author != user and not user.is_staff:
            raise serializers.ValidationError("You don't have permission to update this template")
        
        return attrs


class ProjectTemplateCloneSerializer(serializers.Serializer):
    """
    Serializer for cloning project templates.
    """
    
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_public = serializers.BooleanField(default=False)
    customize_config = serializers.BooleanField(default=False)
    custom_springboot_config = serializers.JSONField(required=False, allow_null=True)
    
    def validate_name(self, value):
        """Validate cloned template name."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Template name must be at least 3 characters long")
        
        # Check for duplicates by current user
        user = self.context['request'].user
        existing = ProjectTemplate.objects.filter(
            name__iexact=value.strip(),
            author=user,
            is_deleted=False
        ).exists()
        
        if existing:
            raise serializers.ValidationError("You already have a template with this name")
        
        return value.strip()
    
    def validate_custom_springboot_config(self, value):
        """Validate custom SpringBoot configuration."""
        if value:
            # Use same validation as create serializer
            create_serializer = ProjectTemplateCreateSerializer()
            return create_serializer.validate_springboot_config(value)
        
        return value


class ProjectTemplateRatingSerializer(serializers.Serializer):
    """
    Serializer for rating project templates.
    """
    
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate rating submission."""
        template = self.context.get('template')
        user = self.context['request'].user
        
        if template:
            if template.author == user:
                raise serializers.ValidationError("Cannot rate your own template")
            
            if not template.is_accessible_by_user(user):
                raise serializers.ValidationError("You don't have access to rate this template")
        
        return attrs


class ProjectTemplateSearchSerializer(serializers.Serializer):
    """
    Serializer for template search parameters.
    """
    
    query = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category = serializers.ChoiceField(
        choices=[
            'WEB_APPLICATION', 'MICROSERVICE', 'REST_API', 'CRUD_APPLICATION',
            'ENTERPRISE_APPLICATION', 'STARTER_TEMPLATE', 'CUSTOM'
        ],
        required=False
    )
    template_type = serializers.ChoiceField(
        choices=['BASIC', 'ADVANCED', 'ENTERPRISE', 'CUSTOM'],
        required=False
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True
    )
    java_version = serializers.CharField(max_length=10, required=False)
    springboot_version = serializers.CharField(max_length=20, required=False)
    is_public = serializers.BooleanField(required=False)
    min_rating = serializers.FloatField(min_value=1.0, max_value=5.0, required=False)
    sort_by = serializers.ChoiceField(
        choices=['name', 'created_at', 'usage_count', 'rating_average', 'last_used_at'],
        default='created_at'
    )
    sort_order = serializers.ChoiceField(choices=['asc', 'desc'], default='desc')


class ProjectTemplateStatisticsSerializer(serializers.Serializer):
    """
    Serializer for template statistics.
    """
    
    period = serializers.ChoiceField(choices=['day', 'week', 'month', 'year'], default='month')
    include_usage = serializers.BooleanField(default=True)
    include_ratings = serializers.BooleanField(default=True)
    include_clones = serializers.BooleanField(default=True)
    
    def validate_period(self, value):
        """Validate statistics period."""
        valid_periods = ['day', 'week', 'month', 'year']
        if value not in valid_periods:
            raise serializers.ValidationError(f"Period must be one of: {', '.join(valid_periods)}")
        
        return value
