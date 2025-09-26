"""
Project serializers for project management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import Project, Workspace

User = get_user_model()


class ProjectListSerializer(serializers.ModelSerializer):
    
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    visibility_display = serializers.CharField(source='get_visibility_display', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 'status_display',
            'visibility', 'visibility_display', 'owner_username', 'workspace_name',
            'member_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    @extend_schema_field(serializers.IntegerField())
    def get_member_count(self, obj) -> int:
        return obj.members.count() if hasattr(obj, 'members') else 0


class ProjectCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'workspace', 'visibility', 
            'springboot_config'
        ]
    
    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Project name must be at least 3 characters long")
        
        if len(value) > 100:
            raise serializers.ValidationError("Project name must not exceed 100 characters")
        
        # Check for duplicate names in workspace
        workspace = self.initial_data.get('workspace')
        if workspace:
            existing = Project.objects.filter(
                name__iexact=value.strip(),
                workspace_id=workspace
            ).exclude(status='DELETED').exists()
            
            if existing:
                raise serializers.ValidationError("A project with this name already exists in the workspace")
        
        return value.strip()
    
    def validate_workspace(self, value):
        user = self.context['request'].user
        
        # Check if user is workspace owner or has permission to create projects
        if value.owner != user and not user.is_staff:
            raise serializers.ValidationError("You don't have permission to create projects in this workspace")
        
        return value
    
    def validate_springboot_config(self, value):
        if value:
            required_fields = ['group_id', 'artifact_id', 'java_version']
            
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


class ProjectUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Project
        fields = [
            'name', 'description', 'visibility', 'springboot_config'
        ]
    
    def validate(self, attrs):
        user = self.context['request'].user
        instance = self.instance
        
        if not hasattr(instance, 'can_user_edit') or not instance.can_user_edit(user):
            raise serializers.ValidationError("You don't have permission to edit this project")
        
        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    
    owner = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    visibility_display = serializers.CharField(source='get_visibility_display', read_only=True)
    
    # Member and activity information
    member_count = serializers.SerializerMethodField()
    active_members = serializers.SerializerMethodField()
    recent_activity = serializers.SerializerMethodField()
    
    # Project statistics
    project_statistics = serializers.SerializerMethodField()
    
    # Permission checks
    user_permissions = serializers.SerializerMethodField()
    
    # Associated diagrams
    diagrams_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 'status_display',
            'visibility', 'visibility_display', 'owner', 'workspace',
            'springboot_config', 'member_count', 'active_members', 
            'recent_activity', 'diagrams_count', 'project_statistics', 
            'user_permissions', 'created_at', 'updated_at', 'last_activity_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_activity_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_owner(self, obj) -> dict:
        if obj.owner:
            return {
                'id': obj.owner.id,
                'username': obj.owner.username,
                'email': obj.owner.email,
                'full_name': obj.owner.get_full_name() if hasattr(obj.owner, 'get_full_name') else ''
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_workspace(self, obj) -> dict:
        if obj.workspace:
            return {
                'id': str(obj.workspace.id),
                'name': obj.workspace.name,
                'type': obj.workspace.workspace_type,
                'status': obj.workspace.status
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_member_count(self, obj) -> dict:
        return {
            'total': obj.members.count() if hasattr(obj, 'members') else 0,
            'active': 0,
            'pending': 0
        }
    
    @extend_schema_field(serializers.ListField())
    def get_active_members(self, obj) -> list:
        return []
    
    @extend_schema_field(serializers.DictField())
    def get_recent_activity(self, obj) -> dict:
        return {}
    
    @extend_schema_field(serializers.DictField())
    def get_project_statistics(self, obj) -> dict:
        return {
            'diagram_count': obj.diagram_count,
            'generation_count': obj.generation_count
        }
    
    @extend_schema_field(serializers.DictField())
    def get_user_permissions(self, obj) -> dict:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        
        user = request.user
        
        return {
            'can_view': True,
            'can_edit': obj.owner == user,
            'can_delete': obj.owner == user,
            'can_manage_members': obj.owner == user,
            'can_generate_code': True,
            'is_owner': obj.owner == user,
            'is_member': True
        }
    
    @extend_schema_field(serializers.IntegerField())
    def get_diagrams_count(self, obj) -> int:
        return obj.diagrams.count() if hasattr(obj, 'diagrams') else 0


class ProjectInviteSerializer(serializers.Serializer):
    
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['VIEWER', 'EDITOR', 'MAINTAINER'])
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_email(self, value):
        # Check if user exists
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")
        
        return value
    
    def validate(self, attrs):
        project = self.context.get('project')
        email = attrs.get('email')
        
        if project and email:
            # Check if user is already a member
            try:
                user = User.objects.get(email=email)
                if hasattr(project, 'is_user_member') and project.is_user_member(user):
                    raise serializers.ValidationError("User is already a member of this project")
            except User.DoesNotExist:
                pass
        
        return attrs


class ProjectCloneSerializer(serializers.Serializer):
    
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    workspace = serializers.PrimaryKeyRelatedField(queryset=Workspace.objects.all())
    clone_members = serializers.BooleanField(default=False)
    clone_diagrams = serializers.BooleanField(default=True)
    clone_settings = serializers.BooleanField(default=True)
    
    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Project name must be at least 3 characters long")
        
        return value.strip()
    
    def validate_workspace(self, value):
        user = self.context['request'].user
        
        if not value.can_user_create_project(user):
            raise serializers.ValidationError("You don't have permission to create projects in this workspace")
        
        return value
