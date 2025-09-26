"""
Enterprise GeneratedProject ViewSet for SpringBoot project management.
Professional CRUD operations with atomic transactions, audit logging, and comprehensive validation.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction
import os
import csv
from datetime import timedelta

from ..models import GeneratedProject
from ..serializers import (
    GeneratedProjectSerializer,
    GeneratedProjectListSerializer,
    GeneratedProjectUpdateSerializer
)
from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from apps.audit.services.audit_service import AuditService
from base.swagger.enterprise_documentation import get_error_responses


@extend_schema_view(
    list=extend_schema(
        tags=["Code Generation - Projects"],
        summary="List Generated Projects",
        description="Retrieve a comprehensive list of generated SpringBoot projects with advanced filtering, search capabilities, and enterprise security.",
        parameters=[
            OpenApiParameter(
                name='generation_request',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by generation request ID"
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by project status (ACTIVE, ARCHIVED, EXPIRED)"
            ),
            OpenApiParameter(
                name='is_archived',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by archived status"
            ),
            OpenApiParameter(
                name='generated_by',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by creator user ID"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in project name, description, and metadata"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: generated_at, updated_at, project_name, download_count, total_size"
            ),
        ],
        responses={
            200: GeneratedProjectListSerializer(many=True),
            **get_error_responses(['400', '401', '403'])
        }
    ),
    retrieve=extend_schema(
        tags=["Code Generation - Projects"],
        summary="Get Generated Project Details",
        description="Retrieve comprehensive information about a specific generated project with metadata and analytics.",
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['401', '403', '404'])
        }
    ),
    update=extend_schema(
        tags=["Code Generation - Projects"],
        summary="Update Generated Project",
        description="Update generated project metadata and configuration with enterprise validation and audit logging.",
        request=GeneratedProjectUpdateSerializer,
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    partial_update=extend_schema(
        tags=["Code Generation - Projects"],
        summary="Partially Update Generated Project", 
        description="Perform partial updates on generated project metadata with field-level validation.",
        request=GeneratedProjectUpdateSerializer,
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    destroy=extend_schema(
        tags=["Code Generation - Projects"],
        summary="Delete Generated Project",
        description="Safely delete a generated project with file cleanup, audit logging, and soft delete capabilities.",
        responses={
            204: {'description': 'Project deleted successfully'},
            **get_error_responses(['401', '403', '404'])
        }
    )
)
class GeneratedProjectViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for managing generated SpringBoot projects.
    
    Provides comprehensive CRUD operations, download functionality, and project lifecycle management
    with enterprise-grade security, audit logging, and transaction management.
    """
    
    queryset = GeneratedProject.objects.all()
    serializer_class = GeneratedProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['generation_request', 'status', 'generated_by', 'is_archived']
    search_fields = ['project_name', 'description', 'metadata']
    ordering_fields = ['generated_at', 'updated_at', 'project_name', 'download_count', 'total_size']
    ordering = ['-generated_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action with comprehensive mapping."""
        serializer_map = {
            'list': GeneratedProjectListSerializer,
            'create': GeneratedProjectSerializer,
            'retrieve': GeneratedProjectSerializer,
            'update': GeneratedProjectUpdateSerializer,
            'partial_update': GeneratedProjectUpdateSerializer,
        }
        return serializer_map.get(self.action, GeneratedProjectSerializer)
    
    def get_queryset(self):
        """
        Filter queryset with enterprise security and performance optimizations.
        """
        base_queryset = GeneratedProject.objects.select_related(
            'generation_request',
            'generated_by'
        ).prefetch_related(
            'generation_request__requested_by'
        )
        
        # Staff users have access to all projects
        if self.request.user.is_staff:
            return base_queryset
        
        # Regular users can only access their own generated projects
        return base_queryset.filter(
            generation_request__requested_by=self.request.user
        ).exclude(
            # Exclude soft deleted items
            status='DELETED'
        )
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create project with enterprise validation and audit logging."""
        try:
            instance = serializer.save(generated_by=self.request.user)
            
            # Audit logging for creation
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE_GENERATED_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=instance.id,
                details={
                    'project_name': instance.project_name,
                    'generation_request_id': instance.generation_request.id if instance.generation_request else None,
                    'file_count': instance.file_count,
                    'total_size': instance.total_size
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE_GENERATED_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update project with validation and audit logging."""
        try:
            old_data = {
                'project_name': serializer.instance.project_name,
                'description': serializer.instance.description,
                'metadata': serializer.instance.metadata
            }
            
            instance = serializer.save()
            
            # Audit logging for update
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE_GENERATED_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=instance.id,
                details={
                    'old_data': old_data,
                    'new_data': {
                        'project_name': instance.project_name,
                        'description': instance.description,
                        'metadata': instance.metadata
                    }
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE_GENERATED_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Enterprise soft delete with file cleanup and comprehensive audit logging.
        """
        try:
            # Validate user permissions for deletion
            if not self.request.user.is_staff and instance.generation_request.requested_by != self.request.user:
                raise ValidationError({
                    'error': 'PERMISSION_DENIED',
                    'message': 'You do not have permission to delete this project'
                })
            
            # Store data for audit logging before deletion
            project_data = {
                'project_name': instance.project_name,
                'generation_request_id': instance.generation_request.id if instance.generation_request else None,
                'file_count': instance.file_count,
                'total_size': instance.total_size,
                'download_count': instance.download_count,
                'is_archived': instance.is_archived
            }
            
            # Clean up files when deleting project
            freed_space = 0
            if instance.archive_path and os.path.exists(instance.archive_path):
                try:
                    freed_space = os.path.getsize(instance.archive_path)
                    os.remove(instance.archive_path)
                except OSError as e:
                    # Log but don't fail deletion for file cleanup issues
                    AuditService.log_user_action(
                        user=self.request.user,
                        action='FILE_CLEANUP_WARNING',
                        resource_type='GENERATED_PROJECT',
                        resource_id=instance.id,
                        details={'error': str(e), 'archive_path': instance.archive_path}
                    )
            
            # Perform soft delete by updating status
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['status', 'deleted_at'])
            
            # Audit logging for deletion
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE_GENERATED_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=instance.id,
                details={
                    **project_data,
                    'freed_space': freed_space,
                    'deletion_timestamp': timezone.now().isoformat()
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE_GENERATED_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Download Project Archive",
        description="Download the generated SpringBoot project as a ZIP archive with enterprise security validation and comprehensive audit logging.",
        responses={
            200: {
                'description': 'Project ZIP archive file',
                'content': {
                    'application/zip': {
                        'example': 'Binary ZIP file download'
                    }
                }
            },
            **get_error_responses(['400', '401', '403', '404', '500'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download project archive with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate user permissions for download
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'DOWNLOAD_PERMISSION_DENIED',
                    'message': 'You do not have permission to download this project',
                    'details': {'project_id': project.id}
                })
            
            # Validate project downloadability
            if not project.is_downloadable():
                raise ValidationError({
                    'error': 'PROJECT_NOT_DOWNLOADABLE',
                    'message': 'Project is not available for download',
                    'details': {
                        'status': project.status,
                        'is_archived': project.is_archived,
                        'expires_at': project.expires_at.isoformat() if project.expires_at else None
                    }
                })
            
            # Validate archive file existence
            if not project.archive_path or not os.path.exists(project.archive_path):
                raise ValidationError({
                    'error': 'ARCHIVE_FILE_NOT_FOUND',
                    'message': 'Archive file not found on server',
                    'details': {'archive_path': project.archive_path}
                })
            
            # Update download statistics
            project.download_count += 1
            project.last_downloaded_at = timezone.now()
            project.save(update_fields=['download_count', 'last_downloaded_at'])
            
            # Audit logging for download
            AuditService.log_user_action(
                user=request.user,
                action='DOWNLOAD_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.project_name,
                    'file_size': os.path.getsize(project.archive_path),
                    'download_count': project.download_count,
                    'download_timestamp': timezone.now().isoformat()
                }
            )
            
            # Serve the file with proper headers
            with open(project.archive_path, 'rb') as archive_file:
                response = HttpResponse(
                    archive_file.read(),
                    content_type='application/zip'
                )
                filename = f"{project.project_name}_{project.id}.zip"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = os.path.getsize(project.archive_path)
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                
                return response
                
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'DOWNLOAD_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Get Project File Structure",
        description="Retrieve detailed file structure and contents analysis of the generated project with enterprise validation.",
        responses={
            200: {
                'description': 'Project file structure information',
                'content': {
                    'application/json': {
                        'example': {
                            'file_structure': {},
                            'file_count': 25,
                            'directory_count': 8,
                            'file_breakdown': {
                                'java': 15,
                                'xml': 3,
                                'properties': 2
                            },
                            'structure_analysis': {
                                'max_depth': 4,
                                'total_size': 1048576
                            }
                        }
                    }
                }
            },
            **get_error_responses(['401', '403', '404'])
        }
    )
    @action(detail=True, methods=['get'])
    def file_structure(self, request, pk=None):
        """Get detailed file structure information with comprehensive analysis."""
        try:
            project = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'ACCESS_DENIED',
                    'message': 'You do not have permission to view this project structure'
                })
            
            # Calculate directory count more efficiently
            directory_count = 0
            if project.file_structure:
                directory_count = sum(
                    1 for item in project.file_structure.values() 
                    if isinstance(item, dict) and item.get('type') == 'directory'
                )
            
            file_structure_data = {
                "file_structure": project.file_structure or {},
                "file_count": project.file_count or 0,
                "directory_count": directory_count,
                "file_breakdown": project.get_file_breakdown() if hasattr(project, 'get_file_breakdown') else {},
                "structure_analysis": {
                    "total_size": project.total_size or 0,
                    "last_analyzed": project.updated_at.isoformat() if project.updated_at else None,
                    "has_structure_data": bool(project.file_structure)
                }
            }
            
            # Audit logging for structure access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW_PROJECT_STRUCTURE',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.project_name,
                    'file_count': file_structure_data['file_count'],
                    'directory_count': directory_count
                }
            )
            
            return Response({
                'success': True,
                'data': file_structure_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW_PROJECT_STRUCTURE', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Archive Project",
        description="Archive a project to save storage space with enterprise validation and audit logging.",
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive project with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'ARCHIVE_PERMISSION_DENIED',
                    'message': 'You do not have permission to archive this project'
                })
            
            # Validate project state
            if project.is_archived:
                raise ValidationError({
                    'error': 'PROJECT_ALREADY_ARCHIVED',
                    'message': 'Project is already archived',
                    'details': {'archived_at': project.archived_at.isoformat() if hasattr(project, 'archived_at') and project.archived_at else None}
                })
            
            # Store pre-archive data for audit
            pre_archive_data = {
                'project_name': project.project_name,
                'total_size': project.total_size,
                'file_count': project.file_count,
                'download_count': project.download_count
            }
            
            # Execute archive operation
            if hasattr(project, 'archive'):
                project.archive()
            else:
                # Fallback archive implementation
                project.is_archived = True
                project.archived_at = timezone.now()
                project.save(update_fields=['is_archived', 'archived_at'])
            
            # Audit logging for archive operation
            AuditService.log_user_action(
                user=request.user,
                action='ARCHIVE_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    **pre_archive_data,
                    'archived_at': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(project)
            return Response({
                'success': True,
                'message': 'Project archived successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'ARCHIVE_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Restore Archived Project",
        description="Restore a previously archived project with enterprise validation and audit logging.",
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore archived project with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'RESTORE_PERMISSION_DENIED',
                    'message': 'You do not have permission to restore this project'
                })
            
            # Validate project state
            if not project.is_archived:
                raise ValidationError({
                    'error': 'PROJECT_NOT_ARCHIVED',
                    'message': 'Project is not in archived state',
                    'details': {'current_status': project.status, 'is_archived': project.is_archived}
                })
            
            # Store pre-restore data for audit
            pre_restore_data = {
                'project_name': project.project_name,
                'was_archived_at': project.archived_at.isoformat() if hasattr(project, 'archived_at') and project.archived_at else None,
                'total_size': project.total_size
            }
            
            # Execute restore operation
            if hasattr(project, 'restore'):
                project.restore()
            else:
                # Fallback restore implementation
                project.is_archived = False
                project.restored_at = timezone.now()
                project.save(update_fields=['is_archived', 'restored_at'])
            
            # Audit logging for restore operation
            AuditService.log_user_action(
                user=request.user,
                action='RESTORE_PROJECT',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    **pre_restore_data,
                    'restored_at': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(project)
            return Response({
                'success': True,
                'message': 'Project restored successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'RESTORE_PROJECT', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Get Project Statistics",
        description="Retrieve comprehensive statistics and analytics for generated projects with enterprise insights.",
        responses={
            200: {
                'description': 'Project statistics and analytics',
                'content': {
                    'application/json': {
                        'example': {
                            'total_projects': 45,
                            'archived_projects': 12,
                            'active_projects': 33,
                            'total_downloads': 127,
                            'total_size': 5242880000,
                            'analytics': {
                                'avg_project_size': 116508444,
                                'avg_downloads_per_project': 2.8
                            },
                            'most_downloaded': [],
                            'recent_projects': []
                        }
                    }
                }
            },
            **get_error_responses(['401', '403'])
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive project statistics with enterprise analytics."""
        try:
            user_projects = self.get_queryset()
            
            # Basic counts with optimized queries
            total_count = user_projects.count()
            archived_count = user_projects.filter(is_archived=True).count()
            active_count = total_count - archived_count
            
            # Aggregate calculations
            from django.db.models import Sum, Avg
            aggregates = user_projects.aggregate(
                total_downloads=Sum('download_count'),
                total_size=Sum('total_size'),
                avg_size=Avg('total_size'),
                avg_downloads=Avg('download_count')
            )
            
            stats = {
                "total_projects": total_count,
                "archived_projects": archived_count,
                "active_projects": active_count,
                "total_downloads": aggregates['total_downloads'] or 0,
                "total_size": aggregates['total_size'] or 0,
                "analytics": {
                    "avg_project_size": int(aggregates['avg_size'] or 0),
                    "avg_downloads_per_project": round(aggregates['avg_downloads'] or 0, 2),
                    "storage_efficiency": {
                        "archived_space_saved": user_projects.filter(is_archived=True).aggregate(
                            saved=Sum('total_size')
                        )['saved'] or 0
                    }
                }
            }
            
            # Most downloaded projects (top 5)
            most_downloaded = user_projects.filter(download_count__gt=0).order_by('-download_count')[:5]
            stats["most_downloaded"] = [
                {
                    "id": str(project.id),
                    "name": project.project_name,
                    "download_count": project.download_count,
                    "total_size": project.total_size or 0,
                    "last_downloaded": project.last_downloaded_at.isoformat() if project.last_downloaded_at else None
                }
                for project in most_downloaded
            ]
            
            # Recent projects (top 5)
            recent_projects = user_projects.order_by('-generated_at')[:5]
            stats["recent_projects"] = [
                {
                    "id": str(project.id),
                    "name": project.project_name,
                    "created_at": project.generated_at.isoformat(),
                    "file_count": project.file_count or 0,
                    "status": project.status,
                    "is_archived": project.is_archived
                }
                for project in recent_projects
            ]
            
            # Status distribution
            from django.db.models import Count, Case, When, CharField
            status_distribution = user_projects.values('status').annotate(
                count=Count('status')
            ).order_by('-count')
            
            stats["status_distribution"] = {
                item['status']: item['count'] for item in status_distribution
            }
            
            # Audit logging for statistics access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW_PROJECT_STATISTICS',
                resource_type='GENERATED_PROJECT',
                resource_id=None,
                details={
                    'total_projects_accessed': total_count,
                    'statistics_timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'data': stats
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW_PROJECT_STATISTICS', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Clean Up Expired Projects",
        description="Remove expired project archives with enterprise security, comprehensive audit logging, and batch processing capabilities (admin only).",
        responses={
            200: {
                'description': 'Cleanup operation completed',
                'content': {
                    'application/json': {
                        'example': {
                            'cleaned_count': 25,
                            'freed_space': 2147483648,
                            'processed_count': 28,
                            'errors': [],
                            'operation_summary': {
                                'start_time': '2024-01-15T10:00:00Z',
                                'end_time': '2024-01-15T10:05:30Z',
                                'duration_seconds': 330
                            }
                        }
                    }
                }
            },
            **get_error_responses(['401', '403'])
        }
    )
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired projects with enterprise security and comprehensive audit logging."""
        try:
            # Strict staff-only validation
            if not request.user.is_staff:
                raise ValidationError({
                    'error': 'CLEANUP_PERMISSION_DENIED',
                    'message': 'Project cleanup is restricted to staff members only',
                    'details': {'required_role': 'staff'}
                })
            
            operation_start = timezone.now()
            
            # Find expired projects with optimized query
            expired_projects = GeneratedProject.objects.select_related(
                'generation_request', 'generated_by'
            ).filter(
                expires_at__lt=operation_start,
                is_archived=False
            ).exclude(
                status='DELETED'
            )
            
            total_projects = expired_projects.count()
            cleaned_count = 0
            freed_space = 0
            errors = []
            processed_projects = []
            
            # Process each expired project
            for project in expired_projects:
                try:
                    project_data = {
                        'id': project.id,
                        'name': project.project_name,
                        'size': project.total_size or 0,
                        'owner': project.generation_request.requested_by.username if project.generation_request else 'Unknown'
                    }
                    
                    # Calculate freed space
                    if project.total_size:
                        freed_space += project.total_size
                    
                    # Remove archive file if exists
                    if project.archive_path and os.path.exists(project.archive_path):
                        try:
                            os.remove(project.archive_path)
                        except OSError as e:
                            errors.append(f"File removal failed for project {project.id}: {str(e)}")
                    
                    # Archive the project
                    project.is_archived = True
                    project.archived_at = operation_start
                    project.save(update_fields=['is_archived', 'archived_at'])
                    
                    cleaned_count += 1
                    processed_projects.append(project_data)
                    
                except Exception as e:
                    error_msg = f"Error processing project {project.id}: {str(e)}"
                    errors.append(error_msg)
                    
                    # Log individual project failure
                    AuditService.log_user_action(
                        user=request.user,
                        action='CLEANUP_PROJECT_FAILED',
                        resource_type='GENERATED_PROJECT',
                        resource_id=project.id,
                        details={'error': str(e), 'project_name': project.project_name}
                    )
            
            operation_end = timezone.now()
            duration = (operation_end - operation_start).total_seconds()
            
            # Comprehensive audit logging for cleanup operation
            AuditService.log_user_action(
                user=request.user,
                action='CLEANUP_EXPIRED_PROJECTS',
                resource_type='GENERATED_PROJECT',
                resource_id=None,
                details={
                    'operation_summary': {
                        'total_found': total_projects,
                        'successfully_cleaned': cleaned_count,
                        'errors_count': len(errors),
                        'freed_space_bytes': freed_space,
                        'duration_seconds': duration
                    },
                    'processed_projects': processed_projects[:10],  # Limit detail for large operations
                    'start_time': operation_start.isoformat(),
                    'end_time': operation_end.isoformat()
                }
            )
            
            return Response({
                'success': True,
                'message': f'Cleanup completed: {cleaned_count} projects processed',
                'data': {
                    'cleaned_count': cleaned_count,
                    'freed_space': freed_space,
                    'processed_count': total_projects,
                    'errors': errors,
                    'operation_summary': {
                        'start_time': operation_start.isoformat(),
                        'end_time': operation_end.isoformat(),
                        'duration_seconds': int(duration)
                    }
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'CLEANUP_EXPIRED_PROJECTS', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Extend Project Expiration",
        description="Extend the expiration date of a project with enterprise validation and comprehensive audit logging.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'days': {
                        'type': 'integer', 
                        'description': 'Number of days to extend (1-365)',
                        'minimum': 1,
                        'maximum': 365
                    }
                },
                'required': ['days'],
                'example': {'days': 30}
            }
        },
        responses={
            200: GeneratedProjectSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def extend_expiration(self, request, pk=None):
        """Extend project expiration with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'EXTEND_PERMISSION_DENIED',
                    'message': 'You do not have permission to extend this project expiration'
                })
            
            # Parse and validate days parameter
            days = request.data.get('days')
            if days is None:
                raise ValidationError({
                    'error': 'MISSING_DAYS_PARAMETER',
                    'message': 'Days parameter is required',
                    'details': {'valid_range': '1-365 days'}
                })
            
            try:
                days = int(days)
            except (ValueError, TypeError):
                raise ValidationError({
                    'error': 'INVALID_DAYS_TYPE',
                    'message': 'Days must be a valid integer'
                })
            
            if days < 1 or days > 365:
                raise ValidationError({
                    'error': 'INVALID_EXTENSION_PERIOD',
                    'message': 'Extension period must be between 1 and 365 days',
                    'details': {'provided': days, 'valid_range': '1-365'}
                })
            
            # Store old expiration for audit
            old_expiration = project.expires_at.isoformat() if project.expires_at else None
            
            # Calculate new expiration date
            if project.expires_at:
                new_expiration = project.expires_at + timedelta(days=days)
            else:
                new_expiration = timezone.now() + timedelta(days=days)
            
            # Update project expiration
            project.expires_at = new_expiration
            project.save(update_fields=['expires_at'])
            
            # Audit logging for expiration extension
            AuditService.log_user_action(
                user=request.user,
                action='EXTEND_PROJECT_EXPIRATION',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.project_name,
                    'extension_days': days,
                    'old_expiration': old_expiration,
                    'new_expiration': new_expiration.isoformat(),
                    'extended_at': timezone.now().isoformat()
                }
            )
            
            serializer = self.get_serializer(project)
            return Response({
                'success': True,
                'message': f'Project expiration extended by {days} days',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'EXTEND_PROJECT_EXPIRATION', 'GENERATED_PROJECT')
            raise
    
    @extend_schema(
        tags=["Code Generation - Projects"],
        summary="Get Project Metadata",
        description="Retrieve comprehensive project metadata including generation info, file details, and download statistics with enterprise validation.",
        responses={
            200: {
                'description': 'Comprehensive project metadata',
                'content': {
                    'application/json': {
                        'example': {
                            'metadata': {
                                'custom_field': 'value'
                            },
                            'generation_info': {
                                'generation_request_id': 123,
                                'generated_at': '2024-01-15T10:00:00Z',
                                'version': '1.0.0',
                                'generated_by': 'admin_user'
                            },
                            'file_info': {
                                'file_count': 25,
                                'total_size': 1048576,
                                'file_breakdown': {
                                    'java': 15,
                                    'xml': 3
                                }
                            },
                            'download_info': {
                                'download_count': 5,
                                'last_downloaded': '2024-01-15T15:30:00Z',
                                'is_downloadable': True,
                                'expires_at': '2024-02-15T10:00:00Z'
                            },
                            'lifecycle_info': {
                                'status': 'ACTIVE',
                                'is_archived': False,
                                'generated_at': '2024-01-15T10:00:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['401', '403', '404'])
        }
    )
    @action(detail=True, methods=['get'])
    def metadata(self, request, pk=None):
        """Get comprehensive project metadata with enterprise validation and audit logging."""
        try:
            project = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and project.generation_request.requested_by != request.user:
                raise ValidationError({
                    'error': 'METADATA_ACCESS_DENIED',
                    'message': 'You do not have permission to view this project metadata'
                })
            
            # Build comprehensive metadata response
            metadata = {
                "metadata": project.metadata or {},
                "generation_info": {
                    "generation_request_id": project.generation_request.id if project.generation_request else None,
                    "generated_at": project.generated_at.isoformat(),
                    "version": getattr(project, 'version', '1.0.0'),
                    "generated_by": project.generated_by.username if project.generated_by else 'System',
                    "generator_version": getattr(project, 'generator_version', None)
                },
                "file_info": {
                    "file_count": project.file_count or 0,
                    "total_size": project.total_size or 0,
                    "file_breakdown": project.get_file_breakdown() if hasattr(project, 'get_file_breakdown') else {},
                    "has_file_structure": bool(project.file_structure),
                    "archive_path": bool(project.archive_path and os.path.exists(project.archive_path)) if project.archive_path else False
                },
                "download_info": {
                    "download_count": project.download_count or 0,
                    "last_downloaded": project.last_downloaded_at.isoformat() if project.last_downloaded_at else None,
                    "is_downloadable": project.is_downloadable() if hasattr(project, 'is_downloadable') else True,
                    "expires_at": project.expires_at.isoformat() if project.expires_at else None,
                    "download_url_expires": project.expires_at < timezone.now() if project.expires_at else False
                },
                "lifecycle_info": {
                    "status": getattr(project, 'status', 'ACTIVE'),
                    "is_archived": project.is_archived,
                    "created_at": project.generated_at.isoformat(),
                    "updated_at": project.updated_at.isoformat() if project.updated_at else None,
                    "archived_at": project.archived_at.isoformat() if hasattr(project, 'archived_at') and project.archived_at else None
                }
            }
            
            # Audit logging for metadata access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW_PROJECT_METADATA',
                resource_type='GENERATED_PROJECT',
                resource_id=project.id,
                details={
                    'project_name': project.project_name,
                    'metadata_sections': list(metadata.keys()),
                    'access_timestamp': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'data': metadata
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW_PROJECT_METADATA', 'GENERATED_PROJECT')
            raise
