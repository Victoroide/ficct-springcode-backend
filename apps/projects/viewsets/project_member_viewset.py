"""
ProjectMember ViewSet for project membership management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from datetime import timedelta

from base.mixins.enterprise_transaction_mixins import EnterpriseTransactionMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from apps.audit.services.audit_service import AuditService
from base.swagger.enterprise_documentation import get_error_responses
from ..models import ProjectMember, Project
from ..serializers import (
    ProjectMemberSerializer,
    ProjectMemberCreateSerializer,
    ProjectMemberListSerializer,
    ProjectMemberUpdateSerializer,
    ProjectMemberInvitationSerializer,
    ProjectMemberBulkActionSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=["Projects Management - Members"],
        summary="List Project Members",
        description="Retrieve paginated list of project members with advanced filtering and role-based permissions.",
        parameters=[
            OpenApiParameter("project", OpenApiTypes.UUID, description="Filter by project ID"),
            OpenApiParameter("role", OpenApiTypes.STR, description="Filter by member role (OWNER, ADMIN, MEMBER, VIEWER)"),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by member status (ACTIVE, PENDING, INACTIVE)"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in user names and emails"),
        ],
        responses={
            200: ProjectMemberListSerializer(many=True),
            **get_error_responses(['401', '403'])
        }
    ),
    create=extend_schema(
        tags=["Projects Management - Members"],
        summary="Add Project Member",
        description="Add new member to project with enterprise validation and audit logging.",
        request=ProjectMemberCreateSerializer,
        responses={
            201: ProjectMemberSerializer,
            **get_error_responses(['400', '401', '403'])
        }
    ),
    retrieve=extend_schema(
        tags=["Projects Management - Members"],
        summary="Get Member Details",
        description="Retrieve comprehensive project member information including permissions and activity.",
        responses={
            200: ProjectMemberSerializer,
            **get_error_responses(['401', '403', '404'])
        }
    ),
    update=extend_schema(
        tags=["Projects Management - Members"],
        summary="Update Project Member",
        description="Update project member role and permissions with atomic transactions and audit logging.",
        request=ProjectMemberUpdateSerializer,
        responses={
            200: ProjectMemberSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    partial_update=extend_schema(
        tags=["Projects Management - Members"],
        summary="Partially Update Project Member",
        description="Partially update project member information with validation and audit logging.",
        request=ProjectMemberUpdateSerializer,
        responses={
            200: ProjectMemberSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    destroy=extend_schema(
        tags=["Projects Management - Members"],
        summary="Remove Project Member",
        description="Remove member from project with validation checks and audit trail preservation.",
        responses={
            204: {'description': 'Member successfully removed'},
            **get_error_responses(['401', '403', '404'])
        }
    )
)
class ProjectMemberViewSet(EnterpriseTransactionMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing project members.
    
    Provides CRUD operations and membership management functionality.
    """
    
    queryset = ProjectMember.objects.all()
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'role', 'status']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    ordering_fields = ['joined_at', 'last_activity_at', 'contribution_count', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == 'create':
            return ProjectMemberCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectMemberUpdateSerializer
        elif self.action == 'list':
            return ProjectMemberListSerializer
        return ProjectMemberSerializer
    
    def get_queryset(self):
        """Get queryset with enterprise-grade filtering and permissions."""
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return ProjectMember.objects.none()
            
        user = self.request.user
        
        if user.is_staff:
            return ProjectMember.objects.select_related(
                'user', 'project', 'invited_by'
            ).prefetch_related(
                'project__uml_diagrams'
            )
        
        # Users can see members of projects they own or are members of
        return ProjectMember.objects.select_related(
            'user', 'project', 'invited_by'
        ).prefetch_related(
            'project__uml_diagrams'
        ).filter(
            Q(project__owner=user) |
            Q(project__project_members__user=user, project__project_members__status='ACTIVE')
        ).distinct()
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create project member with enterprise validation and audit logging."""
        try:
            project_id = self.request.data.get('project')
            
            if not project_id:
                raise ValidationError({
                    'error': 'PROJECT_ID_REQUIRED',
                    'message': 'Project ID is required to add member'
                })
            
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise ValidationError({
                    'error': 'PROJECT_NOT_FOUND',
                    'message': 'Project not found'
                })
            
            # Validate permissions
            if not self.request.user.is_staff and project.owner != self.request.user:
                raise PermissionDenied({
                    'error': 'MEMBER_ADD_PERMISSION_DENIED',
                    'message': 'You do not have permission to add members to this project'
                })
            
            # Create the member
            member = serializer.save()
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='ADD_PROJECT_MEMBER',
                resource_type='PROJECT_MEMBER',
                resource_id=member.id,
                details={
                    'project_name': project.name,
                    'member_user_email': member.user.email,
                    'role': member.role,
                    'status': member.status
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'ADD_PROJECT_MEMBER', 'PROJECT_MEMBER')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update project member with enterprise validation and audit logging."""
        try:
            instance = self.get_object()
            
            # Validate permissions
            if not self.request.user.is_staff and instance.project.owner != self.request.user:
                raise PermissionDenied({
                    'error': 'MEMBER_UPDATE_PERMISSION_DENIED',
                    'message': 'You do not have permission to update this member'
                })
            
            # Store original values for audit
            original_role = instance.role
            original_status = instance.status
            
            # Update the member
            updated_member = serializer.save()
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE_PROJECT_MEMBER',
                resource_type='PROJECT_MEMBER',
                resource_id=instance.id,
                details={
                    'project_name': instance.project.name,
                    'member_user_email': instance.user.email,
                    'original_role': original_role,
                    'new_role': updated_member.role,
                    'original_status': original_status,
                    'new_status': updated_member.status
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE_PROJECT_MEMBER', 'PROJECT_MEMBER')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Remove project member with enterprise validation and audit logging."""
        try:
            # Validate permissions
            if not self.request.user.is_staff and instance.project.owner != self.request.user:
                raise PermissionDenied({
                    'error': 'MEMBER_REMOVE_PERMISSION_DENIED',
                    'message': 'You do not have permission to remove this member'
                })
            
            # Prevent removing project owner
            if instance.project.owner == instance.user:
                raise ValidationError({
                    'error': 'CANNOT_REMOVE_OWNER',
                    'message': 'Cannot remove project owner from member list'
                })
            
            # Store member data for audit
            member_data = {
                'project_name': instance.project.name,
                'member_user_email': instance.user.email,
                'role': instance.role,
                'status': instance.status,
                'removal_timestamp': timezone.now().isoformat()
            }
            
            # Perform deletion
            super().perform_destroy(instance)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='REMOVE_PROJECT_MEMBER',
                resource_type='PROJECT_MEMBER',
                resource_id=instance.id,
                details=member_data
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'REMOVE_PROJECT_MEMBER', 'PROJECT_MEMBER')
            raise
    
    @extend_schema(
        tags=["Projects Management - Members"],
        summary="Handle Member Invitation",
        description="Accept or decline project invitation with enterprise validation and audit logging.",
        request=ProjectMemberInvitationSerializer,
        responses={
            200: {
                'description': 'Invitation handled successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'message': 'Invitation accepted successfully',
                            'member': {
                                'id': 'uuid-string',
                                'role': 'MEMBER',
                                'status': 'ACTIVE'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def handle_invitation(self, request, pk=None):
        """Handle project invitation with enterprise validation and audit logging."""
        try:
            member = self.get_object()
            
            # Only the invited user can handle their invitation
            if member.user != request.user:
                raise PermissionDenied({
                    'error': 'INVITATION_PERMISSION_DENIED',
                    'message': 'You can only handle your own invitations'
                })
            
            # Validate invitation status
            if member.status != 'PENDING':
                raise ValidationError({
                    'error': 'INVITATION_NOT_PENDING',
                    'message': 'This invitation is no longer pending'
                })
            
            serializer = ProjectMemberInvitationSerializer(
                data=request.data,
                context={'member': member, 'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            action = serializer.validated_data['action']
            
            if action == 'ACCEPT':
                member.status = 'ACTIVE'
                member.joined_at = timezone.now()
                member.save(update_fields=['status', 'joined_at'])
                message = "Invitation accepted successfully"
                audit_action = 'ACCEPT_PROJECT_INVITATION'
            else:  # DECLINE
                member.status = 'DECLINED'
                member.save(update_fields=['status'])
                message = "Invitation declined"
                audit_action = 'DECLINE_PROJECT_INVITATION'
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action=audit_action,
                resource_type='PROJECT_MEMBER',
                resource_id=member.id,
                details={
                    'project_name': member.project.name,
                    'member_role': member.role,
                    'invitation_action': action
                }
            )
            
            response_serializer = self.get_serializer(member)
            return Response({
                'success': True,
                'data': {
                    'message': message,
                    'member': response_serializer.data
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'HANDLE_PROJECT_INVITATION', 'PROJECT_MEMBER')
            raise
    
    @extend_schema(
        summary="Update member activity",
        description="Update member's last activity timestamp.",
        tags=["Project Members"],
        responses={
            200: {"description": "Activity updated"},
            403: {"description": "Permission denied"}
        }
    )
    @action(detail=True, methods=['post'])
    def update_activity(self, request, pk=None):
        """Update member activity timestamp."""
        member = self.get_object()
        
        # Only the member themselves can update their activity
        if member.user != request.user:
            return Response(
                {"error": "You can only update your own activity"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member.update_activity()
        
        return Response({
            "message": "Activity updated",
            "last_activity_at": member.last_activity_at.isoformat()
        })
    
    @extend_schema(
        summary="Get member activity history",
        description="Get detailed activity history for a project member.",
        tags=["Project Members"],
        parameters=[
            OpenApiParameter("days", OpenApiTypes.INT, description="Number of days to include (default: 30)"),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "activity_summary": {"type": "object"},
                    "contributions": {"type": "array"},
                    "statistics": {"type": "object"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def activity_history(self, request, pk=None):
        """Get member activity history."""
        member = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        if not member.project.can_user_view(request.user):
            return Response(
                {"error": "You don't have permission to view member activity"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        activity_data = {
            "activity_summary": member.get_activity_statistics(days=days),
            "contributions": member.get_recent_contributions(limit=50),
            "statistics": {
                "total_contributions": member.contribution_count,
                "member_since": member.joined_at.isoformat() if member.joined_at else None,
                "last_active": member.last_activity_at.isoformat() if member.last_activity_at else None,
                "role": member.role,
                "status": member.status
            }
        }
        
        return Response(activity_data)
    
    @extend_schema(
        tags=["Projects Management - Members"],
        summary="Bulk Member Actions",
        description="Perform bulk operations on multiple project members with enterprise validation and audit logging.",
        request=ProjectMemberBulkActionSerializer,
        responses={
            200: {
                'description': 'Bulk action results',
                'content': {
                    'application/json': {
                        'example': {
                            'success_count': 3,
                            'error_count': 1,
                            'errors': ['Error processing member john: Permission denied'],
                            'message': 'Bulk action UPDATE_ROLE completed. 3 successful, 1 errors.'
                        }
                    }
                }
            },
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on project members with enterprise validation and audit logging."""
        try:
            project_id = request.data.get('project')
            
            if not project_id:
                raise ValidationError({
                    'error': 'PROJECT_ID_REQUIRED',
                    'message': 'Project ID is required for bulk operations'
                })
            
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                raise ValidationError({
                    'error': 'PROJECT_NOT_FOUND',
                    'message': 'Project not found'
                })
            
            # Validate permissions
            if not request.user.is_staff and project.owner != request.user:
                raise PermissionDenied({
                    'error': 'BULK_ACTION_PERMISSION_DENIED',
                    'message': 'You do not have permission to perform bulk actions on this project'
                })
            
            serializer = ProjectMemberBulkActionSerializer(
                data=request.data,
                context={'project': project, 'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            member_ids = serializer.validated_data['member_ids']
            action = serializer.validated_data['action']
            role = serializer.validated_data.get('role')
            
            members = ProjectMember.objects.filter(
                project=project,
                id__in=member_ids
            )
            
            success_count = 0
            error_count = 0
            errors = []
            processed_members = []
            
            for member in members:
                try:
                    # Prevent bulk actions on project owner
                    if member.project.owner == member.user and action == 'REMOVE':
                        errors.append(f"Cannot remove project owner {member.user.username}")
                        error_count += 1
                        continue
                    
                    original_data = {
                        'user_email': member.user.email,
                        'original_role': member.role,
                        'original_status': member.status
                    }
                    
                    if action == 'REMOVE':
                        member.delete()
                    elif action == 'UPDATE_ROLE':
                        member.role = role
                        member.save(update_fields=['role'])
                    elif action == 'DEACTIVATE':
                        member.status = 'INACTIVE'
                        member.save(update_fields=['status'])
                    elif action == 'ACTIVATE':
                        member.status = 'ACTIVE'
                        member.save(update_fields=['status'])
                    
                    processed_members.append({
                        **original_data,
                        'action': action,
                        'member_id': str(member.id) if action != 'REMOVE' else None
                    })
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"Error processing member {member.user.username}: {str(e)}")
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='BULK_PROJECT_MEMBER_ACTION',
                resource_type='PROJECT_MEMBER',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'bulk_action': action,
                    'success_count': success_count,
                    'error_count': error_count,
                    'processed_members': processed_members
                }
            )
            
            return Response({
                'success': True,
                'data': {
                    'success_count': success_count,
                    'error_count': error_count,
                    'errors': errors,
                    'message': f"Bulk action '{action}' completed. {success_count} successful, {error_count} errors."
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'BULK_PROJECT_MEMBER_ACTION', 'PROJECT_MEMBER')
            raise
    
    @extend_schema(
        summary="Get member permissions",
        description="Get detailed permissions for a project member.",
        tags=["Project Members"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "effective_permissions": {"type": "object"},
                    "role_permissions": {"type": "object"},
                    "custom_permissions": {"type": "object"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get member permissions breakdown."""
        member = self.get_object()
        
        if not member.project.can_user_view(request.user):
            return Response(
                {"error": "You don't have permission to view member permissions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        permissions_data = {
            "effective_permissions": member.get_effective_permissions(),
            "role_permissions": member.get_role_permissions(),
            "custom_permissions": member.permissions or {},
            "role": member.role,
            "status": member.status,
            "can_modify_permissions": member.project.can_user_manage_members(request.user)
        }
        
        return Response(permissions_data)
    
    @extend_schema(
        summary="Get membership statistics",
        description="Get comprehensive membership statistics.",
        tags=["Project Members"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_members": {"type": "integer"},
                    "active_members": {"type": "integer"},
                    "pending_invitations": {"type": "integer"},
                    "role_distribution": {"type": "object"},
                    "recent_joins": {"type": "array"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get membership statistics for user's projects."""
        user_projects = Project.objects.filter(owner=request.user)
        
        total_members = 0
        active_members = 0
        pending_invitations = 0
        role_counts = {}
        recent_joins = []
        
        for project in user_projects:
            project_members = project.projectmember_set.all()
            
            total_members += project_members.count()
            active_members += project_members.filter(status='ACTIVE').count()
            pending_invitations += project_members.filter(status='PENDING').count()
            
            # Count roles
            for member in project_members:
                role_counts[member.role] = role_counts.get(member.role, 0) + 1
            
            # Recent joins
            recent_project_joins = project_members.filter(
                status='ACTIVE',
                joined_at__isnull=False
            ).order_by('-joined_at')[:5]
            
            for member in recent_project_joins:
                recent_joins.append({
                    "user": member.user.username,
                    "project": project.name,
                    "role": member.role,
                    "joined_at": member.joined_at.isoformat()
                })
        
        # Sort recent joins and limit
        recent_joins.sort(key=lambda x: x['joined_at'], reverse=True)
        recent_joins = recent_joins[:10]
        
        stats = {
            "total_members": total_members,
            "active_members": active_members,
            "pending_invitations": pending_invitations,
            "role_distribution": role_counts,
            "recent_joins": recent_joins,
            "projects_with_members": len([p for p in user_projects if p.get_member_count() > 0])
        }
        
        return Response(stats)
    
    @extend_schema(
        summary="Resend invitation",
        description="Resend invitation to a pending project member.",
        tags=["Project Members"],
        responses={
            200: {"description": "Invitation resent"},
            400: {"description": "Cannot resend invitation"},
            403: {"description": "Permission denied"}
        }
    )
    @action(detail=True, methods=['post'])
    def resend_invitation(self, request, pk=None):
        """Resend invitation to a pending member."""
        member = self.get_object()
        
        if not member.project.can_user_manage_members(request.user):
            return Response(
                {"error": "You don't have permission to resend invitations"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if member.status != 'PENDING':
            return Response(
                {"error": "Can only resend invitations to pending members"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if member.has_invitation_expired():
            # Reset invitation expiration
            from datetime import timedelta
            member.invitation_expires_at = timezone.now() + timedelta(days=7)
            member.save()
        
        # Send invitation email (implement email service)
        # send_project_invitation_email(member)
        
        return Response({
            "message": f"Invitation resent to {member.user.email}",
            "expires_at": member.invitation_expires_at.isoformat() if member.invitation_expires_at else None
        })
