"""
ProjectMember serializers for project membership management.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import ProjectMember, Project

User = get_user_model()


class ProjectMemberListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing project members.
    """
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = [
            'id', 'user_username', 'user_email', 'project_name',
            'role', 'role_display', 'status', 'status_display',
            'joined_at', 'last_activity_at', 'collaboration_sessions'
        ]
        read_only_fields = fields


class ProjectMemberCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding new project members.
    """
    
    user_email = serializers.EmailField(write_only=True)
    
    class Meta:
        model = ProjectMember
        fields = ['user_email', 'role', 'permissions']
    
    def validate_user_email(self, value):
        """Validate and get user by email."""
        try:
            user = User.objects.get(email=value)
            self.validated_user = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")
    
    def validate_role(self, value):
        """Validate role assignment."""
        valid_roles = ['VIEWER', 'EDITOR', 'MAINTAINER', 'ADMIN']
        if value not in valid_roles:
            raise serializers.ValidationError(f"Role must be one of: {', '.join(valid_roles)}")
        
        return value
    
    def validate(self, attrs):
        """Validate membership creation."""
        project = self.context.get('project')
        user = getattr(self, 'validated_user', None)
        
        if project and user:
            # Check if user is already a member
            if ProjectMember.objects.filter(project=project, user=user).exists():
                raise serializers.ValidationError("User is already a member of this project")
            
            # Check project member limits
            if project.is_at_member_limit():
                raise serializers.ValidationError("Project has reached maximum member limit")
        
        return attrs
    
    def create(self, validated_data):
        """Create new project member."""
        project = self.context['project']
        user = self.validated_user
        
        validated_data.pop('user_email', None)
        return ProjectMember.objects.create(
            project=project,
            user=user,
            **validated_data
        )


class ProjectMemberSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for project members.
    """
    
    user = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Activity information
    activity_statistics = serializers.SerializerMethodField()
    recent_contributions = serializers.SerializerMethodField()
    
    # Permission information
    effective_permissions = serializers.SerializerMethodField()
    
    # Invitation information
    invitation_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectMember
        fields = [
            'id', 'user', 'project', 'role', 'role_display',
            'status', 'status_display', 'permissions', 'effective_permissions',
            'joined_at', 'last_activity_at', 'collaboration_sessions',
            'activity_statistics', 'recent_contributions',
            'invitation_info', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'joined_at', 'last_activity_at', 'collaboration_sessions',
            'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_user(self, obj) -> dict:
        """Get user information."""
        if obj.user:
            return {
                'id': obj.user.id,
                'username': obj.user.username,
                'email': obj.user.email,
                'full_name': obj.user.get_full_name() if hasattr(obj.user, 'get_full_name') else '',
                'is_active': obj.user.is_active
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_project(self, obj) -> dict:
        """Get project information."""
        if obj.project:
            return {
                'id': str(obj.project.id),
                'name': obj.project.name,
                'description': obj.project.description,
                'status': obj.project.status
            }
        return None
    
    @extend_schema_field(serializers.DictField())
    def get_activity_statistics(self, obj) -> dict:
        """Get member activity statistics."""
        return obj.get_activity_statistics()
    
    @extend_schema_field(serializers.ListField())
    def get_recent_contributions(self, obj) -> list:
        """Get recent contributions."""
        return obj.get_recent_contributions()
    
    @extend_schema_field(serializers.DictField())
    def get_effective_permissions(self, obj) -> dict:
        """Get effective permissions for the member."""
        return obj.get_effective_permissions()
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_invitation_info(self, obj) -> dict:
        """Get invitation information if applicable."""
        if obj.status == 'PENDING':
            return {
                'invited_at': obj.created_at.isoformat(),
                'invited_by': obj.invited_by.username if obj.invited_by else None,
                'invitation_expires_at': obj.invitation_expires_at.isoformat() if obj.invitation_expires_at else None,
                'has_expired': obj.has_invitation_expired()
            }
        return None


class ProjectMemberUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating project member information.
    """
    
    class Meta:
        model = ProjectMember
        fields = ['role', 'permissions']
    
    def validate_role(self, value):
        """Validate role update."""
        instance = self.instance
        user = self.context['request'].user
        
        # Check if user can update this member's role
        if not instance.project.can_user_manage_members(user):
            raise serializers.ValidationError("You don't have permission to update member roles")
        
        # Prevent downgrading the last admin
        if (instance.role == 'ADMIN' and value != 'ADMIN' and 
            instance.project.get_admin_count() <= 1):
            raise serializers.ValidationError("Cannot remove the last admin from the project")
        
        return value


class ProjectMemberInvitationSerializer(serializers.Serializer):
    """
    Serializer for handling member invitations.
    """
    
    action = serializers.ChoiceField(choices=['ACCEPT', 'DECLINE'])
    
    def validate(self, attrs):
        """Validate invitation action."""
        member = self.context.get('member')
        
        if not member:
            raise serializers.ValidationError("No member context provided")
        
        if member.status != 'PENDING':
            raise serializers.ValidationError("This invitation is no longer pending")
        
        if member.has_invitation_expired():
            raise serializers.ValidationError("This invitation has expired")
        
        return attrs


class ProjectMemberBulkActionSerializer(serializers.Serializer):
    """
    Serializer for bulk member actions.
    """
    
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )
    action = serializers.ChoiceField(choices=['REMOVE', 'UPDATE_ROLE', 'DEACTIVATE', 'ACTIVATE'])
    role = serializers.ChoiceField(
        choices=['VIEWER', 'EDITOR', 'MAINTAINER', 'ADMIN'],
        required=False
    )
    
    def validate(self, attrs):
        """Validate bulk action."""
        action = attrs.get('action')
        role = attrs.get('role')
        
        if action == 'UPDATE_ROLE' and not role:
            raise serializers.ValidationError("Role is required when action is UPDATE_ROLE")
        
        # Validate member_ids exist and user has permission
        project = self.context.get('project')
        user = self.context['request'].user
        
        if not project.can_user_manage_members(user):
            raise serializers.ValidationError("You don't have permission to perform bulk member actions")
        
        member_ids = attrs.get('member_ids', [])
        existing_members = ProjectMember.objects.filter(
            project=project,
            id__in=member_ids
        )
        
        if existing_members.count() != len(member_ids):
            raise serializers.ValidationError("Some member IDs are invalid")
        
        # Prevent removing all admins
        if action == 'REMOVE':
            admin_members = existing_members.filter(role='ADMIN')
            remaining_admins = project.projectmember_set.filter(
                role='ADMIN'
            ).exclude(id__in=member_ids).count()
            
            if admin_members.exists() and remaining_admins == 0:
                raise serializers.ValidationError("Cannot remove all admins from the project")
        
        return attrs
