from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.utils import timezone
from django.conf import settings
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
from ..models import CollaborationSession
from ..serializers import (
    CollaborationSessionListSerializer,
    CollaborationSessionDetailSerializer,
    CollaborationSessionCreateSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=['Collaboration'],
        summary="List Collaboration Sessions",
        description="Retrieve a paginated list of collaboration sessions with advanced filtering, ordering, and search capabilities.",
        parameters=[
            OpenApiParameter(
                name='diagram',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by diagram ID"
            ),
            OpenApiParameter(
                name='session_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by session type (design, review, workshop)"
            ),
            OpenApiParameter(
                name='is_active',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by active status"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in session names and descriptions"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: created_at, updated_at, started_at, ended_at (prefix with '-' for descending)"
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by status (ACTIVE, DELETED)"
            ),
        ],
        responses=CRUD_DOCUMENTATION['list']['responses']
    ),
    create=extend_schema(
        tags=['Collaboration'],
        summary="Create Collaboration Session",
        description="Create a new collaboration session for real-time diagram editing with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['create']['responses']
    ),
    retrieve=extend_schema(
        tags=['Collaboration'],
        summary="Retrieve Collaboration Session",
        description="Retrieve detailed information about a specific collaboration session including participant data and statistics.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    ),
    update=extend_schema(
        tags=['Collaboration'],
        summary="Update Collaboration Session",
        description="Update collaboration session properties with validation and audit logging. Use PATCH for partial updates.",
        responses=CRUD_DOCUMENTATION['update']['responses']
    ),
    partial_update=extend_schema(
        tags=['Collaboration'],
        summary="Partially Update Collaboration Session",
        description="Partially update collaboration session properties with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['partial_update']['responses']
    ),
    destroy=extend_schema(
        tags=['Collaboration'],
        summary="Delete Collaboration Session",
        description="Soft delete a collaboration session with audit logging. The session will be marked as deleted but preserved for audit purposes.",
        responses=CRUD_DOCUMENTATION['destroy']['responses']
    )
)
class CollaborationSessionViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['diagram', 'host_user', 'status']
    ordering_fields = ['created_at', 'updated_at', 'ended_at']
    ordering = ['-created_at']
    search_fields = ['diagram__name', 'host_user__username']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CollaborationSession.objects.none()
            
        queryset = CollaborationSession.objects.filter(
            diagram__project__workspace__owner=self.request.user
        ).select_related(
            'diagram', 
            'project',
            'host_user'
        ).prefetch_related(
            'participants',
            'participants__user',
            'change_events'
        )
        
        # Apply soft delete filter - only show active sessions by default
        if self.action != 'list' or self.request.query_params.get('status') != 'DELETED':
            queryset = queryset.exclude(status='DELETED')
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CollaborationSessionListSerializer
        elif self.action == 'create':
            return CollaborationSessionCreateSerializer
        return CollaborationSessionDetailSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        try:
            # Validate diagram access and concurrent session limits
            diagram = serializer.validated_data.get('diagram')
            
            # Check for existing active sessions on the same diagram
            active_sessions = CollaborationSession.objects.filter(
                diagram=diagram,
                is_active=True,
                status='ACTIVE'
            ).count()
            
            # Limit concurrent sessions per diagram (configurable)
            max_concurrent_sessions = getattr(settings, 'MAX_CONCURRENT_COLLABORATION_SESSIONS', 3)
            if active_sessions >= max_concurrent_sessions:
                raise ValidationError({
                    'error': 'MAX_SESSIONS_EXCEEDED',
                    'message': f'Maximum of {max_concurrent_sessions} concurrent sessions allowed per diagram',
                    'details': {'current_sessions': active_sessions}
                })
            
            session = serializer.save(
                host_user=self.request.user,
                started_at=timezone.now(),
                is_active=True
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE',
                resource_type='COLLABORATION_SESSION',
                resource_id=session.id,
                details={
                    'session_name': session.name,
                    'session_type': session.session_type,
                    'diagram_id': session.diagram.id,
                    'started_at': session.started_at.isoformat()
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE', 'COLLABORATION_SESSION')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        try:
            original_data = {
                'name': serializer.instance.name,
                'description': serializer.instance.description,
                'session_type': serializer.instance.session_type,
                'is_active': serializer.instance.is_active
            }
            
            session = serializer.save()
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE',
                resource_type='COLLABORATION_SESSION',
                resource_id=session.id,
                details={
                    'original_data': original_data,
                    'updated_data': serializer.validated_data,
                    'diagram_id': session.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE', 'COLLABORATION_SESSION')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        try:
            # End session if active
            if instance.is_active:
                instance.end_session()
            
            # Soft delete
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['status', 'deleted_at'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE',
                resource_type='COLLABORATION_SESSION',
                resource_id=instance.id,
                details={
                    'session_name': instance.name,
                    'session_type': instance.session_type,
                    'diagram_id': instance.diagram.id,
                    'duration_minutes': instance.get_session_duration().total_seconds() / 60 if instance.ended_at else None
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE', 'COLLABORATION_SESSION')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="End Session",
        description="End an active collaboration session and update all participants.",
        responses={
            200: {
                'description': 'Session ended successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Session ended successfully',
                            'data': {
                                'session_id': 123,
                                'ended_at': '2024-01-15T10:30:00Z',
                                'duration_minutes': 45,
                                'participants_count': 3,
                                'changes_count': 27
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
    def end_session(self, request, pk=None):
        try:
            session = self.get_object()
            
            if not session.is_active:
                raise ValidationError({
                    'error': 'SESSION_NOT_ACTIVE',
                    'message': 'Session is already ended',
                    'details': {'current_status': session.is_active}
                })
            
            session.end_session()
            
            # Get session statistics for response
            stats = {
                'session_id': session.id,
                'ended_at': session.ended_at.isoformat(),
                'duration_minutes': session.get_session_duration().total_seconds() / 60,
                'participants_count': session.participants.count(),
                'changes_count': session.change_events.count()
            }
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='END_SESSION',
                resource_type='COLLABORATION_SESSION',
                resource_id=session.id,
                details=stats
            )
            
            return Response({
                'success': True,
                'message': 'Session ended successfully',
                'data': stats
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'END_SESSION', 'COLLABORATION_SESSION')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Session Statistics",
        description="Get detailed statistics about a collaboration session including participant activity and change metrics.",
        responses={
            200: {
                'description': 'Session statistics',
                'content': {
                    'application/json': {
                        'example': {
                            'session_info': {
                                'id': 123,
                                'name': 'User Story Mapping Session',
                                'duration_minutes': 45,
                                'is_active': True
                            },
                            'participants': {
                                'total': 3,
                                'active': 2,
                                'roles': {'owner': 1, 'editor': 2}
                            },
                            'activity': {
                                'total_changes': 27,
                                'elements_created': 8,
                                'elements_modified': 12,
                                'elements_deleted': 2
                            },
                            'performance': {
                                'avg_response_time': 250,
                                'peak_concurrent_users': 3
                            }
                        }
                    }
                }
            },
            **get_error_responses(['404'])
        }
    )
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        try:
            session = self.get_object()
            stats = session.get_session_statistics()
            
            # Audit logging for data access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW',
                resource_type='COLLABORATION_SESSION_STATS',
                resource_id=session.id,
                details={
                    'diagram_id': session.diagram.id,
                    'stats_requested': True
                }
            )
            
            return Response({
                'success': True,
                'data': stats,
                'message': 'Session statistics retrieved successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW', 'COLLABORATION_SESSION_STATS')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Join Session",
        description="Join an active collaboration session as a participant with role assignment.",
        parameters=[
            OpenApiParameter(
                name='role',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Participant role (viewer, editor, moderator)",
                default='editor'
            )
        ],
        responses={
            200: {
                'description': 'Successfully joined session',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Joined session successfully',
                            'data': {
                                'participant_id': 456,
                                'role': 'editor',
                                'session_id': 123,
                                'joined_at': '2024-01-15T10:30:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '404', '409'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def join_session(self, request, pk=None):
        try:
            session = self.get_object()
            role = request.query_params.get('role', 'editor')
            
            if not session.is_active:
                raise ValidationError({
                    'error': 'SESSION_NOT_ACTIVE',
                    'message': 'Cannot join an inactive session',
                    'details': {'session_status': session.is_active}
                })
            
            # Check if user is already a participant
            existing_participant = session.participants.filter(user=request.user).first()
            if existing_participant:
                raise ValidationError({
                    'error': 'ALREADY_PARTICIPANT',
                    'message': 'User is already a participant in this session',
                    'details': {'participant_id': existing_participant.id}
                })
            
            # Create participant
            from ..models import SessionParticipant
            participant = SessionParticipant.objects.create(
                session=session,
                user=request.user,
                role=role,
                joined_at=timezone.now()
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='JOIN_SESSION',
                resource_type='COLLABORATION_SESSION',
                resource_id=session.id,
                details={
                    'participant_id': participant.id,
                    'role': role,
                    'diagram_id': session.diagram.id
                }
            )
            
            return Response({
                'success': True,
                'message': 'Joined session successfully',
                'data': {
                    'participant_id': participant.id,
                    'role': participant.role,
                    'session_id': session.id,
                    'joined_at': participant.joined_at.isoformat()
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'JOIN_SESSION', 'COLLABORATION_SESSION')
            raise
