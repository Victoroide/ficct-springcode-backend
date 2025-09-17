from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
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
from ..models import SessionParticipant
from ..serializers import (
    SessionParticipantListSerializer,
    SessionParticipantDetailSerializer,
    SessionParticipantCreateSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=['Collaboration'],
        summary="List Session Participants",
        description="Retrieve a paginated list of collaboration session participants with advanced filtering and search capabilities.",
        parameters=[
            OpenApiParameter(
                name='session',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by session ID"
            ),
            OpenApiParameter(
                name='user',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by user ID"
            ),
            OpenApiParameter(
                name='role',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by participant role (viewer, editor, moderator, owner)"
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
                description="Search in user names and roles"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: joined_at, left_at, role (prefix with '-' for descending)"
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
        summary="Add Session Participant",
        description="Add a new participant to a collaboration session with role assignment and validation.",
        responses=CRUD_DOCUMENTATION['create']['responses']
    ),
    retrieve=extend_schema(
        tags=['Collaboration'],
        summary="Retrieve Session Participant",
        description="Retrieve detailed information about a specific session participant including activity metrics.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    ),
    update=extend_schema(
        tags=['Collaboration'],
        summary="Update Session Participant",
        description="Update participant properties such as role and status with validation and audit logging. Use PATCH for partial updates.",
        responses=CRUD_DOCUMENTATION['update']['responses']
    ),
    partial_update=extend_schema(
        tags=['Collaboration'],
        summary="Partially Update Session Participant",
        description="Partially update participant properties with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['partial_update']['responses']
    ),
    destroy=extend_schema(
        tags=['Collaboration'],
        summary="Remove Session Participant",
        description="Remove a participant from the session with audit logging. The participant will be marked as deleted but preserved for audit purposes.",
        responses=CRUD_DOCUMENTATION['destroy']['responses']
    )
)
class SessionParticipantViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for Session Participant management with atomic transactions,
    real-time presence tracking, role-based access control, and comprehensive audit logging.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['session', 'user', 'role', 'is_active']
    ordering_fields = ['joined_at', 'left_at', 'role']
    ordering = ['-joined_at']
    search_fields = ['user__username', 'user__email', 'role']
    
    def get_queryset(self):
        """
        Enhanced queryset with optimized database queries and soft delete support.
        """
        if getattr(self, 'swagger_fake_view', False):
            return SessionParticipant.objects.none()
            
        queryset = SessionParticipant.objects.filter(
            session__diagram__project__workspace__owner=self.request.user
        ).select_related(
            'session', 
            'user',
            'created_by',
            'updated_by'
        ).prefetch_related(
            'session__diagram',
            'user__profile'
        )
        
        # Apply soft delete filter - only show active participants by default
        if self.action != 'list' or self.request.query_params.get('status') != 'DELETED':
            queryset = queryset.exclude(status='DELETED')
        
        return queryset
    
    def get_serializer_class(self):
        """
        Dynamic serializer class selection based on action.
        """
        if self.action == 'list':
            return SessionParticipantListSerializer
        elif self.action == 'create':
            return SessionParticipantCreateSerializer
        return SessionParticipantDetailSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Enhanced creation with role validation and audit logging.
        """
        try:
            session = serializer.validated_data.get('session')
            user = serializer.validated_data.get('user')
            role = serializer.validated_data.get('role', 'editor')
            
            # Validate session is active
            if not session.is_active:
                raise ValidationError({
                    'error': 'SESSION_NOT_ACTIVE',
                    'message': 'Cannot add participants to an inactive session',
                    'details': {'session_id': session.id}
                })
            
            # Check if user is already a participant
            existing_participant = SessionParticipant.objects.filter(
                session=session,
                user=user,
                status='ACTIVE'
            ).first()
            
            if existing_participant:
                raise ValidationError({
                    'error': 'USER_ALREADY_PARTICIPANT',
                    'message': 'User is already a participant in this session',
                    'details': {'participant_id': existing_participant.id}
                })
            
            # Validate role permissions
            if role == 'owner' and session.created_by != self.request.user:
                raise ValidationError({
                    'error': 'INSUFFICIENT_PERMISSIONS',
                    'message': 'Only session creator can assign owner role',
                    'details': {'requested_role': role}
                })
            
            participant = serializer.save(
                created_by=self.request.user,
                updated_by=self.request.user,
                joined_at=timezone.now(),
                is_active=True
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE',
                resource_type='SESSION_PARTICIPANT',
                resource_id=participant.id,
                details={
                    'session_id': session.id,
                    'participant_user_id': user.id,
                    'role': role,
                    'diagram_id': session.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE', 'SESSION_PARTICIPANT')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """
        Enhanced update with role change validation and audit logging.
        """
        try:
            original_data = {
                'role': serializer.instance.role,
                'is_active': serializer.instance.is_active
            }
            
            # Validate role change permissions
            new_role = serializer.validated_data.get('role', serializer.instance.role)
            if (new_role == 'owner' and 
                serializer.instance.session.created_by != self.request.user):
                raise ValidationError({
                    'error': 'INSUFFICIENT_PERMISSIONS',
                    'message': 'Only session creator can assign owner role',
                    'details': {'requested_role': new_role}
                })
            
            participant = serializer.save(updated_by=self.request.user)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE',
                resource_type='SESSION_PARTICIPANT',
                resource_id=participant.id,
                details={
                    'original_data': original_data,
                    'updated_data': serializer.validated_data,
                    'session_id': participant.session.id,
                    'participant_user_id': participant.user.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE', 'SESSION_PARTICIPANT')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Soft delete implementation with session cleanup and audit logging.
        """
        try:
            # Mark participant as left
            if instance.is_active:
                instance.left_at = timezone.now()
                instance.is_active = False
            
            # Soft delete
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.updated_by = self.request.user
            instance.save(update_fields=['status', 'deleted_at', 'updated_by', 'left_at', 'is_active'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE',
                resource_type='SESSION_PARTICIPANT',
                resource_id=instance.id,
                details={
                    'session_id': instance.session.id,
                    'participant_user_id': instance.user.id,
                    'role': instance.role,
                    'session_duration': (instance.left_at - instance.joined_at).total_seconds() / 60 if instance.left_at else None
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE', 'SESSION_PARTICIPANT')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Leave Session",
        description="Remove participant from active session and update their status.",
        responses={
            200: {
                'description': 'Successfully left session',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Left session successfully',
                            'data': {
                                'participant_id': 456,
                                'session_id': 123,
                                'left_at': '2024-01-15T10:45:00Z',
                                'session_duration_minutes': 45
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
    def leave_session(self, request, pk=None):
        """
        Remove participant from active session with comprehensive cleanup.
        """
        try:
            participant = self.get_object()
            
            if not participant.is_active:
                raise ValidationError({
                    'error': 'PARTICIPANT_NOT_ACTIVE',
                    'message': 'Participant has already left the session',
                    'details': {'current_status': participant.is_active}
                })
            
            participant.leave_session()
            
            # Calculate session duration
            duration_minutes = (participant.left_at - participant.joined_at).total_seconds() / 60
            
            response_data = {
                'participant_id': participant.id,
                'session_id': participant.session.id,
                'left_at': participant.left_at.isoformat(),
                'session_duration_minutes': round(duration_minutes, 2)
            }
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='LEAVE_SESSION',
                resource_type='SESSION_PARTICIPANT',
                resource_id=participant.id,
                details=response_data
            )
            
            return Response({
                'success': True,
                'message': 'Left session successfully',
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'LEAVE_SESSION', 'SESSION_PARTICIPANT')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Update Cursor Position",
        description="Update participant's cursor position for real-time collaboration awareness.",
        parameters=[
            OpenApiParameter(
                name='cursor_position',
                type=OpenApiTypes.OBJECT,
                location=OpenApiParameter.QUERY,
                description="Cursor position data with x, y coordinates and element context"
            )
        ],
        responses={
            200: {
                'description': 'Cursor position updated',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Cursor position updated successfully',
                            'data': {
                                'participant_id': 456,
                                'cursor_position': {
                                    'x': 250,
                                    'y': 150,
                                    'element_id': 789,
                                    'timestamp': '2024-01-15T10:30:00Z'
                                }
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
    def update_cursor(self, request, pk=None):
        """
        Update participant's cursor position for real-time collaboration.
        """
        try:
            participant = self.get_object()
            cursor_position = request.data.get('cursor_position')
            
            if not participant.is_active:
                raise ValidationError({
                    'error': 'PARTICIPANT_NOT_ACTIVE',
                    'message': 'Cannot update cursor for inactive participant',
                    'details': {'participant_status': participant.is_active}
                })
            
            if not cursor_position or not isinstance(cursor_position, dict):
                raise ValidationError({
                    'error': 'INVALID_CURSOR_DATA',
                    'message': 'Valid cursor position data is required',
                    'details': {'received_data': cursor_position}
                })
            
            # Validate cursor position data
            required_fields = ['x', 'y']
            missing_fields = [field for field in required_fields if field not in cursor_position]
            if missing_fields:
                raise ValidationError({
                    'error': 'MISSING_CURSOR_FIELDS',
                    'message': 'Missing required cursor position fields',
                    'details': {'missing_fields': missing_fields}
                })
            
            # Add timestamp to cursor data
            cursor_position['timestamp'] = timezone.now().isoformat()
            
            participant.update_cursor_position(cursor_position)
            
            # Audit logging (minimal for performance)
            AuditService.log_user_action(
                user=request.user,
                action='UPDATE_CURSOR',
                resource_type='SESSION_PARTICIPANT',
                resource_id=participant.id,
                details={
                    'session_id': participant.session.id,
                    'cursor_x': cursor_position['x'],
                    'cursor_y': cursor_position['y']
                }
            )
            
            return Response({
                'success': True,
                'message': 'Cursor position updated successfully',
                'data': {
                    'participant_id': participant.id,
                    'cursor_position': cursor_position
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'UPDATE_CURSOR', 'SESSION_PARTICIPANT')
            raise
    
    @extend_schema(
        tags=['Collaboration'],
        summary="Update Participant Role",
        description="Update participant's role in the collaboration session with proper permission validation.",
        parameters=[
            OpenApiParameter(
                name='role',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="New role for the participant (viewer, editor, moderator, owner)",
                required=True
            )
        ],
        responses={
            200: {
                'description': 'Role updated successfully',
                'content': {
                    'application/json': {
                        'example': {
                            'success': True,
                            'message': 'Role updated successfully',
                            'data': {
                                'participant_id': 456,
                                'old_role': 'viewer',
                                'new_role': 'editor',
                                'updated_at': '2024-01-15T10:30:00Z'
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def update_role(self, request, pk=None):
        """
        Update participant role with proper permission validation.
        """
        try:
            participant = self.get_object()
            new_role = request.query_params.get('role')
            
            if not new_role:
                raise ValidationError({
                    'error': 'ROLE_REQUIRED',
                    'message': 'Role parameter is required',
                    'details': {'available_roles': ['viewer', 'editor', 'moderator', 'owner']}
                })
            
            valid_roles = ['viewer', 'editor', 'moderator', 'owner']
            if new_role not in valid_roles:
                raise ValidationError({
                    'error': 'INVALID_ROLE',
                    'message': 'Invalid role specified',
                    'details': {'available_roles': valid_roles}
                })
            
            # Permission validation
            if (new_role == 'owner' and 
                participant.session.created_by != request.user):
                raise ValidationError({
                    'error': 'INSUFFICIENT_PERMISSIONS',
                    'message': 'Only session creator can assign owner role',
                    'details': {'requested_role': new_role}
                })
            
            old_role = participant.role
            participant.role = new_role
            participant.updated_by = request.user
            participant.save(update_fields=['role', 'updated_by'])
            
            response_data = {
                'participant_id': participant.id,
                'old_role': old_role,
                'new_role': new_role,
                'updated_at': timezone.now().isoformat()
            }
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='UPDATE_ROLE',
                resource_type='SESSION_PARTICIPANT',
                resource_id=participant.id,
                details=response_data
            )
            
            return Response({
                'success': True,
                'message': 'Role updated successfully',
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'UPDATE_ROLE', 'SESSION_PARTICIPANT')
            raise
