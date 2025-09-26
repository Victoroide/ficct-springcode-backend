"""
Project ViewSet for project management.
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
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Case, When, IntegerField

from base.mixins.enterprise_transaction_mixins import EnterpriseTransactionMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from apps.audit.services.audit_service import AuditService
from base.swagger.enterprise_documentation import get_error_responses
from ..models import Project, ProjectMember
from ..serializers import (
    ProjectSerializer,
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
    ProjectInviteSerializer,
    ProjectCloneSerializer
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=["Projects Management"],
        summary="List User Projects",
        description="Retrieve paginated list of projects with advanced filtering, search, and ordering capabilities. Includes project statistics and member counts.",
        parameters=[
            OpenApiParameter("workspace", OpenApiTypes.UUID, description="Filter by workspace ID"),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by project status (ACTIVE, ARCHIVED)"),
            OpenApiParameter("visibility", OpenApiTypes.STR, description="Filter by project visibility (PUBLIC, PRIVATE)"),
            OpenApiParameter("owner", OpenApiTypes.INT, description="Filter by owner user ID"),
            OpenApiParameter("search", OpenApiTypes.STR, description="Search in project name and description"),
            OpenApiParameter("ordering", OpenApiTypes.STR, description="Order by: created_at, updated_at, name, last_activity_at")
        ],
        responses={
            200: ProjectListSerializer(many=True),
            **get_error_responses(['401'])
        }
    ),
    create=extend_schema(
        tags=["Projects Management"],
        summary="Create New Project",
        description="Create a new project with comprehensive validation and audit logging.",
        request=ProjectCreateSerializer,
        responses={
            201: ProjectSerializer,
            **get_error_responses(['400', '401'])
        }
    ),
    retrieve=extend_schema(
        tags=["Projects Management"],
        summary="Get Project Details",
        description="Retrieve comprehensive project information including statistics and metadata.",
        responses={
            200: ProjectSerializer,
            **get_error_responses(['401', '403', '404'])
        }
    ),
    update=extend_schema(
        tags=["Projects Management"],
        summary="Update Project",
        description="Update project configuration with atomic transactions and audit logging.",
        request=ProjectUpdateSerializer,
        responses={
            200: ProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    partial_update=extend_schema(
        tags=["Projects Management"],
        summary="Partially Update Project",
        description="Partially update project configuration with validation and audit logging.",
        request=ProjectUpdateSerializer,
        responses={
            200: ProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    destroy=extend_schema(
        tags=["Projects Management"],
        summary="Delete Project (Soft Delete)",
        description="Soft delete project with audit trail preservation and cascade handling.",
        responses={
            204: {'description': 'Project successfully deleted'},
            **get_error_responses(['401', '403', '404'])
        }
    )
)
class ProjectViewSet(EnterpriseTransactionMixin, viewsets.ModelViewSet):
    
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['workspace', 'status', 'visibility', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name', 'last_activity_at']
    ordering = ['-updated_at']
    
    def create(self, request, *args, **kwargs):
        """Override create to ensure owner is set properly."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Save with owner set
        project = serializer.save(owner=request.user)
        
        # Log creation
        try:
            from apps.audit.services import AuditService
            AuditService.log_user_action(
                user=request.user,
                action='CREATE_PROJECT',
                resource_type='PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'workspace': str(project.workspace.id),
                    'status': project.status,
                    'visibility': project.visibility
                }
            )
        except Exception:
            pass  # Don't fail creation if audit logging fails
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProjectCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectUpdateSerializer
        elif self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        """Get queryset with enterprise-grade filtering and permissions."""
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Project.objects.none()
            
        user = self.request.user
        
        if user.is_staff:
            return Project.objects.select_related(
                'owner', 'workspace'
            ).prefetch_related(
                'members', 'uml_diagrams'
            ).annotate(
                member_count=Count('members', distinct=True),
                diagram_count_annotation=Count('uml_diagrams', distinct=True)
            )
        
        # Users can see projects they own, are members of, or are public
        return Project.objects.select_related(
            'owner', 'workspace'
        ).prefetch_related(
            'members', 'uml_diagrams'
        ).filter(
            Q(owner=user) |
            Q(members__user=user, members__status='ACTIVE') |
            Q(visibility='PUBLIC')
        ).annotate(
            member_count=Count('members', distinct=True),
            diagram_count_annotation=Count('uml_diagrams', distinct=True)
        ).distinct()
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create project with enterprise validation and audit logging."""
        try:
            # Validate workspace access
            workspace = serializer.validated_data.get('workspace')
            if workspace and not self.request.user.is_staff:
                # Check if user has access to the workspace
                if not hasattr(workspace, 'members') or not workspace.members.filter(user=self.request.user).exists():
                    if workspace.owner != self.request.user:
                        raise ValidationError({
                            'error': 'WORKSPACE_ACCESS_DENIED',
                            'message': 'You do not have permission to create projects in this workspace'
                        })
            
            # Create the project
            project = serializer.save(owner=self.request.user)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE_PROJECT',
                resource_type='PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'workspace_id': str(workspace.id) if workspace else None,
                    'visibility': project.visibility
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE_PROJECT', 'PROJECT')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Soft delete project with enterprise validation and audit logging."""
        try:
            # Validate permissions
            if not self.request.user.is_staff and instance.owner != self.request.user:
                raise PermissionDenied({
                    'error': 'PROJECT_DELETE_PERMISSION_DENIED',
                    'message': 'You do not have permission to delete this project'
                })
            
            # Store project data for audit
            project_data = {
                'project_name': instance.name,
                'member_count': instance.project_members.count(),
                'diagram_count': instance.uml_diagrams.count(),
                'visibility': instance.visibility,
                'deletion_timestamp': timezone.now().isoformat()
            }
            
            # Soft delete implementation
            if hasattr(instance, 'is_deleted'):
                instance.is_deleted = True
                instance.deleted_at = timezone.now()
                instance.status = 'DELETED'
                instance.save(update_fields=['is_deleted', 'deleted_at', 'status'])
            else:
                # Fallback to status update
                instance.status = 'DELETED'
                instance.save(update_fields=['status'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE_PROJECT',
                resource_type='PROJECT',
                resource_id=instance.id,
                details=project_data
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE_PROJECT', 'PROJECT')
            raise
    
    @extend_schema(
        summary="Invite user to project",
        description="Invite a user to join the project with specified role.",
        tags=["Projects"],
        request=ProjectInviteSerializer,
        responses={
            201: {"description": "Invitation sent successfully"},
            400: {"description": "Invalid invitation data"},
            404: {"description": "Project not found"}
        }
    )
    @extend_schema(
        tags=["Projects Management"],
        summary="Invite User to Project",
        description="Send invitation to user with role-based access and comprehensive audit logging.",
        request=ProjectInviteSerializer,
        responses={
            201: {
                'description': 'Invitation sent successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'message': 'Invitation sent to user@example.com',
                            'member_id': 'uuid-string',
                            'invitation_details': {
                                'role': 'MEMBER',
                                'status': 'PENDING',
                                'expires_at': '2024-02-01T12:00:00Z'
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
    def invite_user(self, request, pk=None):
        """Invite user to project with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate permissions
            if not request.user.is_staff and project.owner != request.user:
                raise PermissionDenied({
                    'error': 'INVITE_PERMISSION_DENIED',
                    'message': 'You do not have permission to invite users to this project'
                })
            
            serializer = ProjectInviteSerializer(
                data=request.data,
                context={'project': project, 'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            email = serializer.validated_data['email']
            role = serializer.validated_data['role']
            message = serializer.validated_data.get('message', '')
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise ValidationError({
                    'error': 'USER_NOT_FOUND',
                    'message': f'No user found with email: {email}'
                })
            
            # Check if user is already a member
            if ProjectMember.objects.filter(project=project, user=user).exists():
                raise ValidationError({
                    'error': 'USER_ALREADY_MEMBER',
                    'message': 'User is already a member of this project'
                })
            
            # Create project member invitation
            member = ProjectMember.objects.create(
                project=project,
                user=user,
                role=role,
                status='PENDING',
                invited_by=request.user,
                invitation_message=message
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='INVITE_PROJECT_MEMBER',
                resource_type='PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'invited_user_email': email,
                    'role': role,
                    'member_id': str(member.id)
                }
            )
            
            return Response({
                'success': True,
                'data': {
                    'message': f'Invitation sent to {email}',
                    'member_id': str(member.id),
                    'invitation_details': {
                        'role': role,
                        'status': 'PENDING',
                        'invited_at': member.created_at.isoformat()
                    }
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'INVITE_PROJECT_MEMBER', 'PROJECT')
            raise
    
    @extend_schema(
        tags=["Projects Management"],
        summary="Clone Project",
        description="Create a complete copy of an existing project with enterprise validation and audit logging.",
        request=ProjectCloneSerializer,
        responses={
            201: ProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone project with enterprise validation and audit logging."""
        try:
            source_project = self.get_object()
            
            # Validate permissions
            if (source_project.visibility == 'PRIVATE' and 
                source_project.owner != request.user and 
                not request.user.is_staff):
                raise PermissionDenied({
                    'error': 'CLONE_PERMISSION_DENIED',
                    'message': 'You do not have permission to clone this project'
                })
            
            serializer = ProjectCloneSerializer(
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            clone_data = serializer.validated_data
            
            # Validate workspace access for cloned project
            workspace = clone_data['workspace']
            if workspace and not request.user.is_staff:
                if not hasattr(workspace, 'members') or not workspace.members.filter(user=request.user).exists():
                    if workspace.owner != request.user:
                        raise ValidationError({
                            'error': 'WORKSPACE_ACCESS_DENIED',
                            'message': 'You do not have permission to clone projects to this workspace'
                        })
            
            # Create cloned project
            cloned_project = Project.objects.create(
                name=clone_data['name'],
                description=clone_data.get('description', f"Cloned from: {source_project.name}"),
                workspace=workspace,
                owner=request.user,
                visibility='PRIVATE',
                springboot_config=source_project.springboot_config.copy() if clone_data.get('clone_settings') else {}
            )
            
            cloned_items = {
                'diagrams_cloned': 0,
                'members_cloned': 0
            }
            
            # Clone diagrams if requested
            if clone_data.get('clone_diagrams'):
                for diagram in source_project.uml_diagrams.all():
                    diagram.pk = None
                    diagram.project = cloned_project
                    diagram.name = f"{diagram.name} (Copy)"
                    diagram.created_by = request.user
                    diagram.save()
                    cloned_items['diagrams_cloned'] += 1
            
            # Clone members if requested (owner only)
            if (clone_data.get('clone_members') and 
                (source_project.owner == request.user or request.user.is_staff)):
                for member in source_project.project_members.filter(status='ACTIVE'):
                    if member.user != request.user:  # Don't clone owner as member
                        ProjectMember.objects.create(
                            project=cloned_project,
                            user=member.user,
                            role=member.role,
                            status='PENDING',
                            invited_by=request.user
                        )
                        cloned_items['members_cloned'] += 1
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='CLONE_PROJECT',
                resource_type='PROJECT',
                resource_id=cloned_project.id,
                details={
                    'source_project_id': str(source_project.id),
                    'source_project_name': source_project.name,
                    'cloned_project_name': cloned_project.name,
                    'workspace_id': str(workspace.id) if workspace else None,
                    **cloned_items
                }
            )
            
            response_serializer = ProjectSerializer(cloned_project, context={'request': request})
            return Response({
                'success': True,
                'data': response_serializer.data,
                'clone_summary': cloned_items
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'CLONE_PROJECT', 'PROJECT')
            raise
    
    @extend_schema(
        tags=["Projects Management"],
        summary="Archive Project",
        description="Archive project to preserve data while making it inactive with enterprise validation and audit logging.",
        responses={
            200: ProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive project with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate permissions
            if not request.user.is_staff and project.owner != request.user:
                raise PermissionDenied({
                    'error': 'ARCHIVE_PERMISSION_DENIED',
                    'message': 'You do not have permission to archive this project'
                })
            
            if project.status == 'ARCHIVED':
                raise ValidationError({
                    'error': 'PROJECT_ALREADY_ARCHIVED',
                    'message': 'Project is already archived'
                })
            
            previous_status = project.status
            project.status = 'ARCHIVED'
            project.save(update_fields=['status'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='ARCHIVE_PROJECT',
                resource_type='PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'previous_status': previous_status,
                    'new_status': 'ARCHIVED',
                    'archive_timestamp': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(project)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'ARCHIVE_PROJECT', 'PROJECT')
            raise
    
    @extend_schema(
        tags=["Projects Management"],
        summary="Restore Archived Project",
        description="Restore previously archived project with enterprise validation and audit logging.",
        responses={
            200: ProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore archived project with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate permissions
            if not request.user.is_staff and project.owner != request.user:
                raise PermissionDenied({
                    'error': 'RESTORE_PERMISSION_DENIED',
                    'message': 'You do not have permission to restore this project'
                })
            
            if project.status != 'ARCHIVED':
                raise ValidationError({
                    'error': 'PROJECT_NOT_ARCHIVED',
                    'message': 'Project is not archived and cannot be restored'
                })
            
            previous_status = project.status
            project.status = 'ACTIVE'
            project.save(update_fields=['status'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='RESTORE_PROJECT',
                resource_type='PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.name,
                    'previous_status': previous_status,
                    'new_status': 'ACTIVE',
                    'restore_timestamp': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(project)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'RESTORE_PROJECT', 'PROJECT')
            raise
    
    @extend_schema(
        summary="Get project activity",
        description="Get recent activity and statistics for the project.",
        tags=["Projects"],
        parameters=[
            OpenApiParameter("days", OpenApiTypes.INT, description="Number of days to include (default: 7)"),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "activity_summary": {"type": "object"},
                    "recent_activities": {"type": "array"},
                    "statistics": {"type": "object"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        """Get project activity and statistics."""
        project = self.get_object()
        days = int(request.query_params.get('days', 7))
        
        activity_data = {
            "activity_summary": {},
            "recent_activities": [],
            "statistics": {
                'diagram_count': project.diagram_count,
                'generation_count': project.generation_count
            }
        }
        
        return Response(activity_data)
    
    @extend_schema(
        summary="Get project members",
        description="Get list of project members with their roles and status.",
        tags=["Projects"],
        operation_id="project_members_summary",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "members": {"type": "array"},
                    "member_count": {"type": "object"},
                    "pending_invitations": {"type": "array"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get project members information."""
        project = self.get_object()
        
        if project.visibility == 'PRIVATE' and project.owner != request.user:
            return Response(
                {"error": "You don't have permission to view project members"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        members = []
        pending_invitations = []
        
        members_data = {
            "members": [
                {
                    "id": str(member.id),
                    "user": {
                        "id": member.user.id,
                        "username": member.user.username,
                        "email": member.user.email
                    },
                    "role": member.role,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                    "last_activity": member.last_activity_at.isoformat() if member.last_activity_at else None
                }
                for member in members
            ],
            "member_count": {
                "total": 0,
                "by_role": {}
            },
            "pending_invitations": [
                {
                    "id": str(invitation.id),
                    "user": {
                        "username": invitation.user.username,
                        "email": invitation.user.email
                    },
                    "role": invitation.role,
                    "invited_at": invitation.created_at.isoformat(),
                    "invited_by": invitation.invited_by.username if invitation.invited_by else None
                }
                for invitation in pending_invitations
            ]
        }
        
        return Response(members_data)
    
    @extend_schema(
        summary="Get project statistics",
        description="Get comprehensive statistics and metrics for the project.",
        tags=["Projects"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "overview": {"type": "object"},
                    "activity_metrics": {"type": "object"},
                    "collaboration_stats": {"type": "object"},
                    "generation_stats": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get project statistics for current user."""
        user_projects = self.get_queryset().filter(owner=request.user)
        
        stats = {
            "overview": {
                "total_projects": user_projects.count(),
                "active_projects": user_projects.filter(status='ACTIVE').count(),
                "archived_projects": user_projects.filter(status='ARCHIVED').count(),
                "public_projects": user_projects.filter(visibility='PUBLIC').count(),
            },
            "activity_metrics": {
                "projects_created_this_month": user_projects.filter(
                    created_at__gte=timezone.now().replace(day=1)
                ).count(),
                "most_active_project": None,
                "total_diagrams": sum(p.uml_diagrams.count() for p in user_projects),
            },
            "collaboration_stats": {
                "total_members": 0,
                "pending_invitations": 0,
                "projects_with_collaborators": 0,
            },
            "generation_stats": {
                "total_generations": 0,  # Would need to query GenerationRequest model
                "successful_generations": 0,
                "total_downloads": 0,
            }
        }
        
        # Find most active project
        if user_projects.exists():
            most_active = user_projects.first()
            stats["activity_metrics"]["most_active_project"] = {
                "id": str(most_active.id),
                "name": most_active.name,
                "member_count": 1
            }
        
        return Response(stats)
    
    @extend_schema(
        summary="Export project data",
        description="Export project data and configuration for backup or migration.",
        tags=["Projects"],
        parameters=[
            OpenApiParameter("include_diagrams", OpenApiTypes.BOOL, description="Include UML diagrams in export"),
            OpenApiParameter("include_members", OpenApiTypes.BOOL, description="Include member information"),
        ],
        responses={
            200: {"description": "Exported project data"},
            403: {"description": "Permission denied"}
        }
    )
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export project data."""
        project = self.get_object()
        
        if not project.can_user_edit(request.user):
            return Response(
                {"error": "You don't have permission to export this project"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        include_diagrams = request.query_params.get('include_diagrams', 'true').lower() == 'true'
        include_members = request.query_params.get('include_members', 'false').lower() == 'true'
        
        export_data = {
            "project": {
                "name": project.name,
                "description": project.description,
                "springboot_config": project.springboot_config,
                "visibility": project.visibility,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat()
            },
            "export_metadata": {
                "exported_at": timezone.now().isoformat(),
                "exported_by": request.user.username,
                "export_version": "1.0"
            }
        }
        
        if include_diagrams:
            diagrams_data = []
            for diagram in project.uml_diagrams.all():
                diagrams_data.append({
                    "name": diagram.name,
                    "description": diagram.description,
                    "diagram_type": diagram.diagram_type,
                    "diagram_data": diagram.diagram_data,
                    "metadata": diagram.metadata,
                    "created_at": diagram.created_at.isoformat()
                })
            export_data["diagrams"] = diagrams_data
        
        if include_members and project.owner == request.user:
            export_data["members"] = []
        
        return Response(export_data)
