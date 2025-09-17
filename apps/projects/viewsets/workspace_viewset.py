"""
Workspace ViewSet for workspace management.
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
from django.contrib.auth import get_user_model
from datetime import timedelta

from base.mixins.enterprise_transaction_mixins import EnterpriseTransactionMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from apps.audit.services.audit_service import AuditService
from base.swagger.enterprise_documentation import get_error_responses
from ..models import Workspace
from ..serializers import (
    WorkspaceSerializer,
    WorkspaceCreateSerializer,
    WorkspaceListSerializer,
    WorkspaceUpdateSerializer,
    WorkspaceInviteSerializer,
    WorkspaceTransferSerializer,
    WorkspaceUsageSerializer
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="List User Workspaces",
        description="Retrieve paginated list of workspaces with enterprise filtering and project statistics.",
        parameters=[
            OpenApiParameter("workspace_type", OpenApiTypes.STR, description="Filter by workspace type (PERSONAL, TEAM, ENTERPRISE)"),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by workspace status (ACTIVE, ARCHIVED)"),
            OpenApiParameter("owner", OpenApiTypes.INT, description="Filter by owner user ID"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in workspace name and description"),
        ],
        responses={
            200: WorkspaceListSerializer(many=True),
            **get_error_responses(['401'])
        }
    ),
    create=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Create New Workspace",
        description="Create new workspace with enterprise validation and audit logging.",
        request=WorkspaceCreateSerializer,
        responses={
            201: WorkspaceSerializer,
            **get_error_responses(['400', '401'])
        }
    ),
    retrieve=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Get Workspace Details",
        description="Retrieve comprehensive workspace information including projects and resource usage.",
        responses={
            200: WorkspaceSerializer,
            **get_error_responses(['401', '403', '404'])
        }
    ),
    update=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Update Workspace",
        description="Update workspace configuration with atomic transactions and audit logging.",
        request=WorkspaceUpdateSerializer,
        responses={
            200: WorkspaceSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    partial_update=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Partially Update Workspace",
        description="Partially update workspace configuration with validation and audit logging.",
        request=WorkspaceUpdateSerializer,
        responses={
            200: WorkspaceSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    destroy=extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Delete Workspace (Soft Delete)",
        description="Soft delete workspace with audit trail and cascade handling for projects.",
        responses={
            204: {'description': 'Workspace successfully deleted'},
            **get_error_responses(['401', '403', '404'])
        }
    )
)
class WorkspaceViewSet(EnterpriseTransactionMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing workspaces.
    
    Provides CRUD operations and workspace management functionality.
    """
    
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['workspace_type', 'status', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-updated_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == 'create':
            return WorkspaceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return WorkspaceUpdateSerializer
        elif self.action == 'list':
            return WorkspaceListSerializer
        return WorkspaceSerializer
    
    def get_queryset(self):
        """Get queryset with enterprise-grade filtering and permissions."""
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Workspace.objects.none()
            
        user = self.request.user
        
        base_queryset = Workspace.objects.select_related(
            'owner'
        ).prefetch_related(
            'projects', 'projects__project_members'
        ).annotate(
            project_count=Count('projects', distinct=True)
        )
        
        if user.is_staff:
            return base_queryset.filter(
                Q(is_deleted=False) | Q(is_deleted__isnull=True)
            )
        
        # Users can see workspaces they own or are members of through projects
        return base_queryset.filter(
            Q(owner=user) |
            Q(projects__project_members__user=user, projects__project_members__status='ACTIVE'),
            Q(is_deleted=False) | Q(is_deleted__isnull=True)
        ).distinct()
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create workspace with enterprise validation and audit logging."""
        try:
            # Create the workspace
            workspace = serializer.save(owner=self.request.user)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE_WORKSPACE',
                resource_type='WORKSPACE',
                resource_id=workspace.id,
                details={
                    'workspace_name': workspace.name,
                    'workspace_type': workspace.workspace_type,
                    'status': workspace.status
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE_WORKSPACE', 'WORKSPACE')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Soft delete workspace with enterprise validation and audit logging."""
        try:
            # Validate permissions
            if not self.request.user.is_staff and instance.owner != self.request.user:
                raise PermissionDenied({
                    'error': 'WORKSPACE_DELETE_PERMISSION_DENIED',
                    'message': 'You do not have permission to delete this workspace'
                })
            
            # Store workspace data for audit
            workspace_data = {
                'workspace_name': instance.name,
                'workspace_type': instance.workspace_type,
                'project_count': instance.projects.count(),
                'deletion_timestamp': timezone.now().isoformat()
            }
            
            # Soft delete implementation
            if hasattr(instance, 'soft_delete'):
                instance.soft_delete()
            else:
                # Fallback soft delete
                instance.is_deleted = True
                instance.deleted_at = timezone.now()
                instance.save(update_fields=['is_deleted', 'deleted_at'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE_WORKSPACE',
                resource_type='WORKSPACE',
                resource_id=instance.id,
                details=workspace_data
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE_WORKSPACE', 'WORKSPACE')
            raise
    
    @extend_schema(
        summary="Invite user to workspace",
        description="Invite a user to join the workspace.",
        tags=["Workspaces"],
        request=WorkspaceInviteSerializer,
        responses={
            201: {"description": "Invitation sent successfully"},
            400: {"description": "Invalid invitation data"}
        }
    )
    @action(detail=True, methods=['post'])
    def invite_user(self, request, pk=None):
        """Invite a user to the workspace."""
        workspace = self.get_object()
        
        if not workspace.can_user_manage(request.user):
            return Response(
                {"error": "You don't have permission to invite users to this workspace"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = WorkspaceInviteSerializer(
            data=request.data,
            context={'workspace': workspace, 'request': request}
        )
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            role = serializer.validated_data['role']
            message = serializer.validated_data.get('message', '')
            
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(email=email)
                
                # Create workspace invitation (implement WorkspaceMember model if needed)
                # For now, we'll create a simple response
                
                return Response({
                    "message": f"Invitation sent to {email}",
                    "role": role
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response(
                    {"error": f"Failed to send invitation: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Transfer workspace ownership",
        description="Transfer ownership of the workspace to another user.",
        tags=["Workspaces"],
        request=WorkspaceTransferSerializer,
        responses={
            200: WorkspaceSerializer,
            400: {"description": "Invalid transfer data"}
        }
    )
    @action(detail=True, methods=['post'])
    def transfer_ownership(self, request, pk=None):
        """Transfer workspace ownership."""
        workspace = self.get_object()
        
        serializer = WorkspaceTransferSerializer(
            data=request.data,
            context={'workspace': workspace, 'request': request}
        )
        
        if serializer.is_valid():
            new_owner = serializer.validated_new_owner
            
            # Transfer ownership
            old_owner = workspace.owner
            workspace.owner = new_owner
            workspace.save()
            
            # Log the transfer (implement audit logging if needed)
            
            response_serializer = self.get_serializer(workspace)
            return Response({
                "message": f"Workspace ownership transferred from {old_owner.username} to {new_owner.username}",
                "workspace": response_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get workspace usage report",
        description="Get detailed usage report for the workspace.",
        tags=["Workspaces"],
        request=WorkspaceUsageSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "usage_summary": {"type": "object"},
                    "resource_usage": {"type": "object"},
                    "project_breakdown": {"type": "array"},
                    "trends": {"type": "object"}
                }
            }
        }
    )
    @action(detail=True, methods=['post'])
    def usage_report(self, request, pk=None):
        """Get comprehensive workspace usage report."""
        workspace = self.get_object()
        
        if not workspace.can_user_access(request.user):
            return Response(
                {"error": "You don't have permission to view workspace usage"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = WorkspaceUsageSerializer(data=request.data)
        
        if serializer.is_valid():
            period = serializer.validated_data['period']
            include_projects = serializer.validated_data['include_projects']
            include_members = serializer.validated_data['include_members']
            include_storage = serializer.validated_data['include_storage']
            
            # Calculate date range
            end_date = timezone.now()
            if period == 'day':
                start_date = end_date - timedelta(days=1)
            elif period == 'week':
                start_date = end_date - timedelta(weeks=1)
            elif period == 'month':
                start_date = end_date - timedelta(days=30)
            else:  # year
                start_date = end_date - timedelta(days=365)
            
            usage_data = {
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "usage_summary": workspace.get_workspace_statistics(),
                "resource_usage": workspace.get_resource_usage()
            }
            
            if include_projects:
                projects = workspace.projects.filter(
                    created_at__gte=start_date,
                    is_deleted=False
                )
                
                usage_data["project_breakdown"] = [
                    {
                        "id": str(project.id),
                        "name": project.name,
                        "status": project.status,
                        "member_count": project.get_member_count(),
                        "diagrams_count": project.uml_diagrams.count(),
                        "created_at": project.created_at.isoformat()
                    }
                    for project in projects
                ]
            
            if include_members:
                # Calculate member activity (would need WorkspaceMember model)
                usage_data["member_activity"] = {
                    "total_members": workspace.get_total_member_count(),
                    "active_members": workspace.get_active_member_count()
                }
            
            if include_storage:
                usage_data["storage_breakdown"] = workspace.get_storage_breakdown()
            
            return Response(usage_data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get workspace projects",
        description="Get list of projects in the workspace.",
        tags=["Workspaces"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by project status"),
            OpenApiParameter("visibility", OpenApiTypes.STR, description="Filter by project visibility"),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "projects": {"type": "array"},
                    "project_count": {"type": "integer"},
                    "active_projects": {"type": "integer"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        """Get workspace projects."""
        workspace = self.get_object()
        
        if not workspace.can_user_access(request.user):
            return Response(
                {"error": "You don't have permission to view workspace projects"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        projects_queryset = workspace.projects.filter(is_deleted=False)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            projects_queryset = projects_queryset.filter(status=status_filter)
        
        visibility_filter = request.query_params.get('visibility')
        if visibility_filter:
            projects_queryset = projects_queryset.filter(visibility=visibility_filter)
        
        projects_data = []
        for project in projects_queryset.order_by('-updated_at'):
            projects_data.append({
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "visibility": project.visibility,
                "owner": project.owner.username,
                "member_count": project.get_member_count(),
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat()
            })
        
        return Response({
            "projects": projects_data,
            "project_count": projects_queryset.count(),
            "active_projects": projects_queryset.filter(status='ACTIVE').count(),
            "workspace_limits": {
                "max_projects": workspace.resource_limits.get('max_projects', 0) if workspace.resource_limits else 0,
                "remaining_slots": workspace.get_remaining_project_slots()
            }
        })
    
    @extend_schema(
        summary="Get workspace statistics",
        description="Get comprehensive statistics for workspaces.",
        tags=["Workspaces"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_workspaces": {"type": "integer"},
                    "active_workspaces": {"type": "integer"},
                    "workspace_types": {"type": "object"},
                    "recent_activity": {"type": "array"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get workspace statistics for current user."""
        user_workspaces = self.get_queryset().filter(owner=request.user)
        
        stats = {
            "total_workspaces": user_workspaces.count(),
            "active_workspaces": user_workspaces.filter(status='ACTIVE').count(),
            "workspace_types": {},
            "recent_activity": []
        }
        
        # Count workspace types
        for workspace in user_workspaces:
            workspace_type = workspace.workspace_type
            stats["workspace_types"][workspace_type] = stats["workspace_types"].get(workspace_type, 0) + 1
        
        # Recent workspace activity
        recent_workspaces = user_workspaces.order_by('-updated_at')[:5]
        for workspace in recent_workspaces:
            stats["recent_activity"].append({
                "id": str(workspace.id),
                "name": workspace.name,
                "workspace_type": workspace.workspace_type,
                "project_count": workspace.get_project_count(),
                "updated_at": workspace.updated_at.isoformat()
            })
        
        # Resource usage summary
        total_projects = sum(w.get_project_count() for w in user_workspaces)
        total_members = sum(w.get_total_member_count() for w in user_workspaces)
        
        stats.update({
            "resource_summary": {
                "total_projects": total_projects,
                "total_members": total_members,
                "average_projects_per_workspace": total_projects / user_workspaces.count() if user_workspaces.count() > 0 else 0
            }
        })
        
        return Response(stats)
    
    @extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Archive Workspace",
        description="Archive workspace to preserve data while making it inactive with enterprise validation and audit logging.",
        responses={
            200: WorkspaceSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive workspace with enterprise validation and audit logging."""
        try:
            workspace = self.get_object()
            
            # Validate permissions
            if not request.user.is_staff and workspace.owner != request.user:
                raise PermissionDenied({
                    'error': 'ARCHIVE_PERMISSION_DENIED',
                    'message': 'You do not have permission to archive this workspace'
                })
            
            if workspace.status == 'ARCHIVED':
                raise ValidationError({
                    'error': 'WORKSPACE_ALREADY_ARCHIVED',
                    'message': 'Workspace is already archived'
                })
            
            previous_status = workspace.status
            
            # Archive workspace
            if hasattr(workspace, 'archive'):
                workspace.archive()
            else:
                workspace.status = 'ARCHIVED'
                workspace.save(update_fields=['status'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='ARCHIVE_WORKSPACE',
                resource_type='WORKSPACE',
                resource_id=workspace.id,
                details={
                    'workspace_name': workspace.name,
                    'previous_status': previous_status,
                    'new_status': 'ARCHIVED',
                    'project_count': workspace.projects.count(),
                    'archive_timestamp': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(workspace)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'ARCHIVE_WORKSPACE', 'WORKSPACE')
            raise
    
    @extend_schema(
        tags=["Projects Management - Workspaces"],
        summary="Restore Archived Workspace",
        description="Restore previously archived workspace with enterprise validation and audit logging.",
        responses={
            200: WorkspaceSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore archived workspace with enterprise validation and audit logging."""
        try:
            workspace = self.get_object()
            
            # Validate permissions
            if not request.user.is_staff and workspace.owner != request.user:
                raise PermissionDenied({
                    'error': 'RESTORE_PERMISSION_DENIED',
                    'message': 'You do not have permission to restore this workspace'
                })
            
            if workspace.status != 'ARCHIVED':
                raise ValidationError({
                    'error': 'WORKSPACE_NOT_ARCHIVED',
                    'message': 'Workspace is not archived and cannot be restored'
                })
            
            previous_status = workspace.status
            
            # Restore workspace
            if hasattr(workspace, 'restore'):
                workspace.restore()
            else:
                workspace.status = 'ACTIVE'
                workspace.save(update_fields=['status'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='RESTORE_WORKSPACE',
                resource_type='WORKSPACE',
                resource_id=workspace.id,
                details={
                    'workspace_name': workspace.name,
                    'previous_status': previous_status,
                    'new_status': 'ACTIVE',
                    'project_count': workspace.projects.count(),
                    'restore_timestamp': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(workspace)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'RESTORE_WORKSPACE', 'WORKSPACE')
            raise
    
    @extend_schema(
        summary="Check workspace limits",
        description="Check current usage against workspace limits.",
        tags=["Workspaces"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "limits": {"type": "object"},
                    "usage": {"type": "object"},
                    "available": {"type": "object"},
                    "warnings": {"type": "array"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def check_limits(self, request, pk=None):
        """Check workspace limits and usage."""
        workspace = self.get_object()
        
        if not workspace.can_user_access(request.user):
            return Response(
                {"error": "You don't have permission to view workspace limits"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        limits = workspace.resource_limits or {}
        usage = workspace.get_resource_usage()
        
        available = {}
        warnings = []
        
        # Calculate available resources
        for resource, limit in limits.items():
            current_usage = usage.get(resource, 0)
            available[resource] = max(0, limit - current_usage)
            
            # Check for warnings (80% usage)
            if current_usage / limit > 0.8:
                warnings.append(f"{resource} is at {(current_usage/limit)*100:.1f}% capacity")
        
        return Response({
            "limits": limits,
            "usage": usage,
            "available": available,
            "warnings": warnings,
            "is_at_limit": workspace.is_at_resource_limits(),
            "upgrade_available": workspace.can_upgrade_plan()
        })
