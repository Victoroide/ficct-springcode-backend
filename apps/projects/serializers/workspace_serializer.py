"""
Workspace serializers for workspace management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import Workspace

User = get_user_model()


class WorkspaceListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing workspaces.
    """
    
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    workspace_type_display = serializers.CharField(source='get_workspace_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = [
            'id', 'name', 'description', 'workspace_type', 'workspace_type_display',
            'status', 'status_display', 'owner_username', 'project_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.IntegerField())
    def get_project_count(self, obj) -> int:
        """Get total project count."""
        return obj.get_project_count()


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new workspaces.
    """
    
    class Meta:
        model = Workspace
        fields = [
            'name', 'description', 'workspace_type', 'settings',
            'max_projects', 'max_members_per_project'
        ]
    
    def validate_name(self, value):
        """Validate workspace name."""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Workspace name must be at least 3 characters long")
        
        if len(value) > 100:
            raise serializers.ValidationError("Workspace name must not exceed 100 characters")
        
        # Check for duplicate names for the same user
        user = self.context['request'].user
        existing = Workspace.objects.filter(
            name__iexact=value.strip(),
            owner=user,
            is_deleted=False
        ).exists()
        
        if existing:
            raise serializers.ValidationError("You already have a workspace with this name")
        
        return value.strip()
    
    def validate_workspace_type(self, value):
        """Validate workspace type."""
        valid_types = ['PERSONAL', 'TEAM', 'ORGANIZATION', 'ENTERPRISE']
        if value not in valid_types:
            raise serializers.ValidationError(f"workspace_type must be one of: {', '.join(valid_types)}")
        
        return value
    
    def validate_resource_limits(self, value):
        """Validate resource limits configuration."""
        if value:
            required_fields = ['max_projects', 'max_members', 'storage_limit_gb']
            
            for field in required_fields:
                if field not in value or not isinstance(value[field], int) or value[field] < 0:
                    raise serializers.ValidationError(f"Invalid {field} in resource_limits")
            
            # Validate reasonable limits
            if value['max_projects'] > 1000:
                raise serializers.ValidationError("max_projects cannot exceed 1000")
            
            if value['max_members'] > 10000:
                raise serializers.ValidationError("max_members cannot exceed 10000")
            
            if value['storage_limit_gb'] > 1000:
                raise serializers.ValidationError("storage_limit_gb cannot exceed 1000GB")
        
        return value


class WorkspaceSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for workspaces.
    """
    
    owner = serializers.SerializerMethodField()
    workspace_type_display = serializers.CharField(source='get_workspace_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Project and member information
    project_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    active_projects = serializers.SerializerMethodField()
    
    # Resource usage
    resource_usage = serializers.SerializerMethodField()
    
    # Workspace statistics
    workspace_statistics = serializers.SerializerMethodField()
    
    # Permission checks
    user_permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = Workspace
        fields = [
            'id', 'name', 'description', 'workspace_type', 'workspace_type_display',
            'status', 'status_display', 'owner', 'settings',
            'max_projects', 'max_members_per_project', 'project_count', 'member_count',
            'active_projects', 'resource_usage', 'workspace_statistics', 'user_permissions', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_owner(self, obj) -> dict:
        """Get owner information."""
        if obj.owner:
            return {
                'id': obj.owner.id,
                'username': obj.owner.username,
                'email': obj.owner.email,
                'full_name': obj.owner.get_full_name() if hasattr(obj.owner, 'get_full_name') else ''
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_project_count(self, obj) -> dict:
        """Get project count breakdown."""
        return {
            'total': obj.get_project_count(),
            'active': obj.get_active_project_count(),
            'archived': obj.get_archived_project_count()
        }
    
    @extend_schema_field(serializers.IntegerField())
    def get_member_count(self, obj) -> int:
        """Get member count across all projects."""
        return obj.get_total_member_count()
    
    @extend_schema_field(serializers.ListField())
    def get_active_projects(self, obj) -> list:
        """Get list of active projects."""
        projects = obj.projects.filter(is_active=True, is_deleted=False)[:10]
        
        return [
            {
                'id': str(project.id),
                'name': project.name,
                'status': project.status,
                'member_count': project.get_member_count(),
                'updated_at': project.updated_at.isoformat()
            }
            for project in projects
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_resource_usage(self, obj) -> dict:
        """Get current resource usage."""
        return obj.get_resource_usage()
    
    @extend_schema_field(serializers.DictField())
    def get_workspace_statistics(self, obj) -> dict:
        """Get comprehensive workspace statistics."""
        return obj.get_workspace_statistics()
    
    @extend_schema_field(serializers.DictField())
    def get_user_permissions(self, obj) -> dict:
        """Get current user's permissions for this workspace."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        return {
            'can_view': obj.can_user_access(user),
            'can_edit': obj.can_user_manage(user),
            'can_delete': obj.owner == user,
            'can_create_projects': obj.can_user_create_project(user),
            'can_manage_members': obj.can_user_manage(user),
            'is_owner': obj.owner == user,
            'is_member': obj.is_user_member(user)
        }


class WorkspaceUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating workspaces.
    """
    
    class Meta:
        model = Workspace
        fields = [
            'name', 'description', 'settings',
            'max_projects', 'max_members_per_project'
        ]
    
    def validate(self, attrs):
        """Validate update permissions."""
        user = self.context['request'].user
        instance = self.instance
        
        if not instance.can_user_manage(user):
            raise serializers.ValidationError("You don't have permission to update this workspace")
        
        return attrs
    
    def validate_name(self, value):
        """Validate workspace name update."""
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("Workspace name must be at least 3 characters long")
        
        return value.strip() if value else value


class WorkspaceInviteSerializer(serializers.Serializer):
    """
    Serializer for workspace invitations.
    """
    
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['MEMBER', 'ADMIN'])
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_email(self, value):
        """Validate invitation email."""
        # Check if user exists
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")
        
        return value
    
    def validate(self, attrs):
        """Validate invitation data."""
        workspace = self.context.get('workspace')
        email = attrs.get('email')
        
        if workspace and email:
            # Check if user is already a member
            try:
                user = User.objects.get(email=email)
                if workspace.is_user_member(user):
                    raise serializers.ValidationError("User is already a member of this workspace")
            except User.DoesNotExist:
                pass
            
            # Check workspace member limits
            if workspace.is_at_member_limit():
                raise serializers.ValidationError("Workspace has reached maximum member limit")
        
        return attrs


class WorkspaceTransferSerializer(serializers.Serializer):
    """
    Serializer for workspace ownership transfer.
    """
    
    new_owner_email = serializers.EmailField()
    confirmation_message = serializers.CharField(max_length=200, required=False, allow_blank=True)
    
    def validate_new_owner_email(self, value):
        """Validate new owner email."""
        try:
            user = User.objects.get(email=value)
            self.validated_new_owner = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")
    
    def validate(self, attrs):
        """Validate ownership transfer."""
        workspace = self.context.get('workspace')
        new_owner = getattr(self, 'validated_new_owner', None)
        current_user = self.context['request'].user
        
        if workspace and new_owner:
            if workspace.owner != current_user:
                raise serializers.ValidationError("Only the workspace owner can transfer ownership")
            
            if new_owner == current_user:
                raise serializers.ValidationError("Cannot transfer ownership to yourself")
            
            # Check if new owner is a member of the workspace
            if not workspace.is_user_member(new_owner):
                raise serializers.ValidationError("New owner must be a member of the workspace")
        
        return attrs


class WorkspaceUsageSerializer(serializers.Serializer):
    """
    Serializer for workspace usage reports.
    """
    
    period = serializers.ChoiceField(choices=['day', 'week', 'month', 'year'], default='month')
    include_projects = serializers.BooleanField(default=True)
    include_members = serializers.BooleanField(default=True)
    include_storage = serializers.BooleanField(default=True)
    
    def validate_period(self, value):
        """Validate reporting period."""
        valid_periods = ['day', 'week', 'month', 'year']
        if value not in valid_periods:
            raise serializers.ValidationError(f"Period must be one of: {', '.join(valid_periods)}")
        
        return value
