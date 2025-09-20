"""
GenerationRequest ViewSet for SpringBoot code generation request management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from base.swagger.enterprise_documentation import (
    CRUD_DOCUMENTATION, 
    get_custom_action_documentation,
    get_error_responses
)
from apps.audit.services import AuditService
from ..models import GenerationRequest
from ..serializers import GenerationRequestSerializer, GenerationRequestCreateSerializer
from ..services import CodeGeneratorService


@extend_schema_view(
    list=extend_schema(
        tags=["Code Generation"],
        summary="List Code Generation Requests",
        description="Retrieve a paginated list of SpringBoot code generation requests with advanced filtering, ordering, and search capabilities.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by generation status (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED)"
            ),
            OpenApiParameter(
                name='diagram',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by UML diagram ID"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in project name, description, group ID, and artifact ID"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: created_at, updated_at, status, progress_percentage (prefix with '-' for descending)"
            ),
            OpenApiParameter(
                name='created_by',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by creator user ID"
            ),
        ],
        responses=CRUD_DOCUMENTATION['list']['responses']
    ),
    create=extend_schema(
        tags=["Code Generation"],
        summary="Create Code Generation Request",
        description="Create a new SpringBoot code generation request from UML diagram with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['create']['responses']
    ),
    retrieve=extend_schema(
        tags=["Code Generation"],
        summary="Retrieve Code Generation Request",
        description="Retrieve detailed information about a specific code generation request including progress and configuration.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    ),
    update=extend_schema(
        tags=["Code Generation"],
        summary="Update Code Generation Request",
        description="Update generation request configuration and settings with validation and audit logging. Use PATCH for partial updates.",
        responses=CRUD_DOCUMENTATION['update']['responses']
    ),
    partial_update=extend_schema(
        tags=["Code Generation"],
        summary="Partially Update Code Generation Request",
        description="Partially update generation request configuration with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['partial_update']['responses']
    ),
    destroy=extend_schema(
        tags=["Code Generation"],
        summary="Delete Code Generation Request",
        description="Soft delete a code generation request with audit logging. The request will be marked as deleted but preserved for audit purposes.",
        responses=CRUD_DOCUMENTATION['destroy']['responses']
    )
)
class GenerationRequestViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for SpringBoot Code Generation Request management with atomic transactions,
    comprehensive status tracking, soft delete support, and audit logging.
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'diagram', 'requested_by']
    search_fields = ['project_name', 'description', 'config__group_id', 'config__artifact_id']
    ordering_fields = ['created_at', 'updated_at', 'status', 'progress_percentage']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Enhanced queryset with optimized database queries and soft delete support.
        """
        if getattr(self, 'swagger_fake_view', False):
            return GenerationRequest.objects.none()
            
        queryset = GenerationRequest.objects.select_related(
            'diagram',
            'requested_by',
            'project'
        ).prefetch_related(
            'diagram__project',
            'generated_projects'
        )
        
        # Filter based on user permissions
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                diagram__project__workspace__owner=self.request.user
            )
        
        # Apply soft delete filter - only show active requests by default
        if self.action != 'list' or self.request.query_params.get('include_deleted') != 'true':
            queryset = queryset.exclude(status='DELETED')
        
        return queryset
    
    def get_serializer_class(self):
        """
        Dynamic serializer class selection based on action.
        """
        if self.action == 'create':
            return GenerationRequestCreateSerializer
        return GenerationRequestSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Enhanced creation with validation and audit logging.
        """
        try:
            # Validate diagram access and generation constraints
            diagram = serializer.validated_data.get('diagram')
            
            # Check if user has access to the diagram
            if not diagram.project.workspace.owner == self.request.user:
                raise ValidationError({
                    'error': 'DIAGRAM_ACCESS_DENIED',
                    'message': 'You do not have access to this diagram',
                    'details': {'diagram_id': diagram.id}
                })
            
            # Check for existing pending/in-progress requests
            existing_active = GenerationRequest.objects.filter(
                diagram=diagram,
                status__in=['PENDING', 'IN_PROGRESS'],
                created_by=self.request.user
            ).exists()
            
            if existing_active:
                raise ValidationError({
                    'error': 'ACTIVE_REQUEST_EXISTS',
                    'message': 'An active generation request already exists for this diagram',
                    'details': {'diagram_id': diagram.id}
                })
            
            generation_request = serializer.save(
                created_by=self.request.user,
                updated_by=self.request.user,
                status='PENDING'
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'project_name': generation_request.project_name,
                    'diagram_id': diagram.id,
                    'config': generation_request.config
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE', 'GENERATION_REQUEST')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """
        Enhanced update with status validation and audit logging.
        """
        try:
            # Validate status transitions
            instance = serializer.instance
            new_status = serializer.validated_data.get('status', instance.status)
            
            # Define valid status transitions
            valid_transitions = {
                'PENDING': ['IN_PROGRESS', 'CANCELLED'],
                'IN_PROGRESS': ['COMPLETED', 'FAILED', 'CANCELLED'],
                'FAILED': ['PENDING'],  # Allow retry
                'COMPLETED': [],  # Completed requests cannot be modified
                'CANCELLED': ['PENDING']  # Allow restart
            }
            
            if (new_status != instance.status and 
                new_status not in valid_transitions.get(instance.status, [])):
                raise ValidationError({
                    'error': 'INVALID_STATUS_TRANSITION',
                    'message': f'Cannot transition from {instance.status} to {new_status}',
                    'details': {
                        'current_status': instance.status,
                        'requested_status': new_status,
                        'valid_transitions': valid_transitions.get(instance.status, [])
                    }
                })
            
            original_data = {
                'status': instance.status,
                'project_name': instance.project_name,
                'config': instance.config
            }
            
            generation_request = serializer.save(updated_by=self.request.user)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'original_data': original_data,
                    'updated_data': serializer.validated_data,
                    'diagram_id': generation_request.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE', 'GENERATION_REQUEST')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Soft delete implementation with cleanup and audit logging.
        """
        try:
            # Cancel if in progress
            if instance.status == 'IN_PROGRESS':
                instance.cancel_generation()
            
            # Soft delete
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.updated_by = self.request.user
            instance.save(update_fields=['status', 'deleted_at', 'updated_by'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE',
                resource_type='GENERATION_REQUEST',
                resource_id=instance.id,
                details={
                    'project_name': instance.project_name,
                    'diagram_id': instance.diagram.id,
                    'was_status': instance.status
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Start Code Generation",
        description="Start the SpringBoot code generation process for this request with comprehensive validation and tracking.",
        responses={
            200: {
                'description': 'Generation started successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Generation started successfully',
                            'data': {
                                'request_id': 123,
                                'status': 'IN_PROGRESS',
                                'started_at': '2024-01-15T10:30:00Z',
                                'estimated_completion': '2024-01-15T10:35:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404', '500'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def start_generation(self, request, pk=None):
        """Start the SpringBoot code generation process with enterprise validation."""
        try:
            generation_request = self.get_object()
            
            if generation_request.status not in ['PENDING', 'FAILED']:
                raise ValidationError({
                    'error': 'INVALID_STATUS_FOR_START',
                    'message': 'Generation can only be started for pending or failed requests',
                    'details': {'current_status': generation_request.status}
                })
            
            # Additional validation checks
            if not generation_request.diagram:
                raise ValidationError({
                    'error': 'NO_DIAGRAM_ATTACHED',
                    'message': 'Cannot start generation without a UML diagram',
                    'details': {'request_id': generation_request.id}
                })
            
            # Check diagram elements
            if not generation_request.diagram.elements.exists():
                raise ValidationError({
                    'error': 'EMPTY_DIAGRAM',
                    'message': 'Cannot generate code from an empty diagram',
                    'details': {'diagram_id': generation_request.diagram.id}
                })
            
            # Initialize code generator service
            generator_service = CodeGeneratorService()
            
            # Update status and timestamps
            generation_request.status = 'IN_PROGRESS'
            generation_request.started_at = timezone.now()
            generation_request.progress_percentage = 0
            generation_request.current_step = 'Initializing generation'
            generation_request.updated_by = request.user
            generation_request.save(update_fields=[
                'status', 'started_at', 'progress_percentage', 
                'current_step', 'updated_by'
            ])
            
            # Start generation process (async in production)
            generator_service.generate_springboot_project(
                generation_request.diagram,
                generation_request.config,
                generation_request
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='START_GENERATION',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'project_name': generation_request.project_name,
                    'diagram_id': generation_request.diagram.id,
                    'started_at': generation_request.started_at.isoformat()
                }
            )
            
            return Response({
                'success': True,
                'message': 'Generation started successfully',
                'data': {
                    'request_id': generation_request.id,
                    'status': generation_request.status,
                    'started_at': generation_request.started_at.isoformat(),
                    'estimated_completion': generation_request.estimated_completion_at.isoformat() if generation_request.estimated_completion_at else None,
                    'progress_percentage': generation_request.progress_percentage
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Update request status on failure
            if 'generation_request' in locals():
                generation_request.status = 'FAILED'
                generation_request.error_message = str(e)
                generation_request.updated_by = request.user
                generation_request.save(update_fields=['status', 'error_message', 'updated_by'])
            
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'START_GENERATION', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Cancel Code Generation",
        description="Cancel an in-progress code generation request with audit logging and cleanup.",
        responses={
            200: {
                'description': 'Generation cancelled successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Generation cancelled successfully',
                            'data': {
                                'request_id': 123,
                                'status': 'CANCELLED',
                                'cancelled_at': '2024-01-15T10:32:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def cancel_generation(self, request, pk=None):
        """Cancel an in-progress generation request with enterprise validation."""
        try:
            generation_request = self.get_object()
            
            if generation_request.status not in ['IN_PROGRESS', 'PENDING']:
                raise ValidationError({
                    'error': 'INVALID_STATUS_FOR_CANCEL',
                    'message': 'Only pending or in-progress generations can be cancelled',
                    'details': {'current_status': generation_request.status}
                })
            
            # Cancel the generation
            generation_request.status = 'CANCELLED'
            generation_request.cancelled_at = timezone.now()
            generation_request.updated_by = request.user
            generation_request.save(update_fields=['status', 'cancelled_at', 'updated_by'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='CANCEL_GENERATION',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'project_name': generation_request.project_name,
                    'cancelled_at': generation_request.cancelled_at.isoformat(),
                    'progress_at_cancel': generation_request.progress_percentage
                }
            )
            
            return Response({
                'success': True,
                'message': 'Generation cancelled successfully',
                'data': {
                    'request_id': generation_request.id,
                    'status': generation_request.status,
                    'cancelled_at': generation_request.cancelled_at.isoformat(),
                    'progress_at_cancel': generation_request.progress_percentage
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'CANCEL_GENERATION', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Get Generation Progress",
        description="Retrieve real-time progress information and detailed status for code generation with comprehensive tracking.",
        responses={
            200: {
                'description': 'Progress information retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'status': 'IN_PROGRESS',
                                'progress_percentage': 65,
                                'current_step': 'Generating service classes',
                                'estimated_completion': '2024-01-15T10:35:00Z',
                                'files_generated': 12,
                                'total_files_expected': 18,
                                'elapsed_time_seconds': 180,
                                'errors': [],
                                'warnings': []
                            }
                        }
                    }
                }
            },
            **get_error_responses(['404'])
        }
    )
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get comprehensive generation progress information with enterprise tracking."""
        try:
            generation_request = self.get_object()
            
            # Calculate elapsed time
            elapsed_seconds = 0
            if generation_request.started_at:
                elapsed_seconds = int((timezone.now() - generation_request.started_at).total_seconds())
            
            progress_data = {
                'status': generation_request.status,
                'progress_percentage': generation_request.progress_percentage,
                'current_step': generation_request.current_step,
                'estimated_completion': generation_request.estimated_completion_at.isoformat() if generation_request.estimated_completion_at else None,
                'files_generated': generation_request.files_generated,
                'total_files_expected': generation_request.total_files_expected,
                'elapsed_time_seconds': elapsed_seconds,
                'started_at': generation_request.started_at.isoformat() if generation_request.started_at else None,
                'errors': generation_request.error_details.get('errors', []) if generation_request.error_details else [],
                'warnings': generation_request.error_details.get('warnings', []) if generation_request.error_details else []
            }
            
            return Response({
                'success': True,
                'data': progress_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'GET_PROGRESS', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Retry Failed Generation",
        description="Retry a failed code generation request with the same configuration and audit logging.",
        responses={
            200: {
                'description': 'Generation retry initiated successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Generation retry initiated successfully',
                            'data': {
                                'request_id': 123,
                                'status': 'PENDING',
                                'retry_count': 2,
                                'reset_at': '2024-01-15T10:40:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed generation request with enterprise validation."""
        try:
            generation_request = self.get_object()
            
            if generation_request.status not in ['FAILED', 'CANCELLED']:
                raise ValidationError({
                    'error': 'INVALID_STATUS_FOR_RETRY',
                    'message': 'Only failed or cancelled generations can be retried',
                    'details': {'current_status': generation_request.status}
                })
            
            # Check retry limits
            max_retries = 3
            if generation_request.retry_count >= max_retries:
                raise ValidationError({
                    'error': 'MAX_RETRIES_EXCEEDED',
                    'message': f'Maximum retry limit ({max_retries}) exceeded',
                    'details': {
                        'current_retries': generation_request.retry_count,
                        'max_retries': max_retries
                    }
                })
            
            # Reset generation state
            generation_request.retry_count += 1
            generation_request.status = 'PENDING'
            generation_request.progress_percentage = 0
            generation_request.current_step = 'Ready to retry'
            generation_request.error_message = None
            generation_request.error_details = {}
            generation_request.started_at = None
            generation_request.completed_at = None
            generation_request.cancelled_at = None
            generation_request.updated_by = request.user
            generation_request.save()
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='RETRY_GENERATION',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'project_name': generation_request.project_name,
                    'retry_count': generation_request.retry_count,
                    'reset_at': timezone.now().isoformat()
                }
            )
            
            return Response({
                'success': True,
                'message': 'Generation retry initiated successfully',
                'data': {
                    'request_id': generation_request.id,
                    'status': generation_request.status,
                    'retry_count': generation_request.retry_count,
                    'reset_at': timezone.now().isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'RETRY_GENERATION', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Download Generated Project",
        description="Download the generated SpringBoot project as a ZIP archive with access logging and validation.",
        responses={
            200: {
                'description': 'Download information provided successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'download_url': 'https://cdn.example.com/projects/abc123.zip',
                                'expires_at': '2024-01-15T18:00:00Z',
                                'file_size_bytes': 2048576,
                                'file_size_mb': 2.0,
                                'download_count': 3
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download the generated project ZIP file with enterprise validation."""
        try:
            generation_request = self.get_object()
            
            if generation_request.status != 'COMPLETED':
                raise ValidationError({
                    'error': 'GENERATION_NOT_COMPLETED',
                    'message': 'Generation must be completed before download',
                    'details': {'current_status': generation_request.status}
                })
            
            if not generation_request.download_url:
                raise ValidationError({
                    'error': 'DOWNLOAD_URL_NOT_AVAILABLE',
                    'message': 'Download URL is not available for this request',
                    'details': {'request_id': generation_request.id}
                })
            
            # Check download URL expiration
            if (generation_request.download_expires_at and 
                timezone.now() > generation_request.download_expires_at):
                raise ValidationError({
                    'error': 'DOWNLOAD_EXPIRED',
                    'message': 'Download link has expired',
                    'details': {
                        'expired_at': generation_request.download_expires_at.isoformat()
                    }
                })
            
            # Update download count
            generation_request.download_count += 1
            generation_request.last_downloaded_at = timezone.now()
            generation_request.save(update_fields=['download_count', 'last_downloaded_at'])
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='DOWNLOAD_PROJECT',
                resource_type='GENERATION_REQUEST',
                resource_id=generation_request.id,
                details={
                    'project_name': generation_request.project_name,
                    'download_count': generation_request.download_count,
                    'downloaded_at': generation_request.last_downloaded_at.isoformat()
                }
            )
            
            return Response({
                'success': True,
                'data': {
                    'download_url': generation_request.get_download_url(),
                    'expires_at': generation_request.download_expires_at.isoformat() if generation_request.download_expires_at else None,
                    'file_size_bytes': generation_request.file_size_bytes,
                    'file_size_mb': round(generation_request.file_size_bytes / (1024 * 1024), 2) if generation_request.file_size_bytes else 0,
                    'download_count': generation_request.download_count,
                    'project_name': generation_request.project_name
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'DOWNLOAD_PROJECT', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Get Generation Statistics",
        description="Retrieve comprehensive statistics for code generation requests with detailed metrics and analytics.",
        responses={
            200: {
                'description': 'Statistics retrieved successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'data': {
                                'total_requests': 150,
                                'completed_requests': 125,
                                'failed_requests': 15,
                                'in_progress_requests': 5,
                                'pending_requests': 5,
                                'cancelled_requests': 0,
                                'success_rate_percentage': 83.3,
                                'average_generation_time_seconds': 285.6,
                                'total_files_generated': 2750,
                                'total_size_generated_mb': 156.7,
                                'most_common_errors': ['DIAGRAM_PARSING_ERROR', 'INVALID_RELATIONSHIPS']
                            }
                        }
                    }
                }
            },
            **get_error_responses(['403'])
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comprehensive generation statistics with enterprise analytics."""
        try:
            user_requests = self.get_queryset()
            
            # Basic counts
            total_requests = user_requests.count()
            completed_requests = user_requests.filter(status='COMPLETED').count()
            failed_requests = user_requests.filter(status='FAILED').count()
            in_progress_requests = user_requests.filter(status='IN_PROGRESS').count()
            pending_requests = user_requests.filter(status='PENDING').count()
            cancelled_requests = user_requests.filter(status='CANCELLED').count()
            
            # Success rate calculation
            success_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
            
            # Average generation time for completed requests
            completed_with_times = user_requests.filter(
                status='COMPLETED',
                started_at__isnull=False,
                completed_at__isnull=False
            )
            
            average_time = 0
            if completed_with_times.exists():
                total_time = sum([
                    (req.completed_at - req.started_at).total_seconds() 
                    for req in completed_with_times
                ])
                average_time = total_time / completed_with_times.count()
            
            # Aggregate file and size statistics
            completed_requests_data = user_requests.filter(status='COMPLETED')
            total_files = sum(req.files_generated for req in completed_requests_data if req.files_generated)
            total_size_bytes = sum(req.file_size_bytes for req in completed_requests_data if req.file_size_bytes)
            total_size_mb = round(total_size_bytes / (1024 * 1024), 2) if total_size_bytes else 0
            
            # Most common errors
            failed_requests_with_errors = user_requests.filter(
                status='FAILED',
                error_details__isnull=False
            )
            error_types = {}
            for req in failed_requests_with_errors:
                if req.error_details and 'error_type' in req.error_details:
                    error_type = req.error_details['error_type']
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            most_common_errors = [
                error for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)
            ][:5]
            
            stats = {
                'total_requests': total_requests,
                'completed_requests': completed_requests,
                'failed_requests': failed_requests,
                'in_progress_requests': in_progress_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': cancelled_requests,
                'success_rate_percentage': round(success_rate, 1),
                'average_generation_time_seconds': round(average_time, 1),
                'total_files_generated': total_files,
                'total_size_generated_mb': total_size_mb,
                'most_common_errors': most_common_errors,
                'generated_at': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'data': stats
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'GET_STATISTICS', 'GENERATION_REQUEST')
            raise
    
    @extend_schema(
        tags=["Code Generation"],
        summary="Clone Generation Request",
        description="Create a new generation request based on an existing one with configuration inheritance and audit logging.",
        request=OpenApiParameter(
            'clone_data',
            location=OpenApiParameter.QUERY,
            description="Optional data for clone customization",
            required=False,
            type=OpenApiTypes.OBJECT,
        ),
        responses={
            201: {
                'description': 'Generation request cloned successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Generation request cloned successfully',
                            'data': {
                                'cloned_request_id': 456,
                                'source_request_id': 123,
                                'project_name': 'Original Project (Copy)',
                                'status': 'PENDING',
                                'created_at': '2024-01-15T10:45:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing generation request with enterprise validation."""
        try:
            source_request = self.get_object()
            
            # Validate source request accessibility
            if not source_request.diagram.project.workspace.owner == request.user and not request.user.is_staff:
                raise ValidationError({
                    'error': 'SOURCE_REQUEST_ACCESS_DENIED',
                    'message': 'You do not have access to clone this generation request',
                    'details': {'source_request_id': source_request.id}
                })
            
            # Get clone customization data
            clone_data = request.data or {}
            project_name = clone_data.get('project_name', f"{source_request.project_name} (Copy)")
            description = clone_data.get('description', f"Cloned from: {source_request.project_name}")
            
            # Create cloned request
            cloned_request = GenerationRequest.objects.create(
                diagram=source_request.diagram,
                project_name=project_name,
                description=description,
                config=source_request.config.copy() if source_request.config else {},
                template_overrides=source_request.template_overrides.copy() if source_request.template_overrides else {},
                created_by=request.user,
                updated_by=request.user,
                status='PENDING'
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='CLONE_REQUEST',
                resource_type='GENERATION_REQUEST',
                resource_id=cloned_request.id,
                details={
                    'source_request_id': source_request.id,
                    'source_project_name': source_request.project_name,
                    'cloned_project_name': cloned_request.project_name,
                    'diagram_id': source_request.diagram.id
                }
            )
            
            return Response({
                'success': True,
                'message': 'Generation request cloned successfully',
                'data': {
                    'cloned_request_id': cloned_request.id,
                    'source_request_id': source_request.id,
                    'project_name': cloned_request.project_name,
                    'status': cloned_request.status,
                    'created_at': cloned_request.created_at.isoformat(),
                    'diagram_id': cloned_request.diagram.id
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'CLONE_REQUEST', 'GENERATION_REQUEST')
            raise
