"""
Enterprise Session Management ViewSet
CRUD operations for user session management with enterprise security features.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils import timezone
from datetime import timedelta

from ..serializers import (
    SessionListSerializer,
    SessionDetailSerializer,
)
# from ..services import AuthenticationService
# from ..permissions import IsOwnerOrAdmin

class IsOwnerOrAdmin:
    """Temporary permission class."""
    pass
from apps.audit.models import AuditLog

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=['Authentication'],
        summary='List User Sessions',
        description='Get list of active sessions for authenticated user',
        responses={200: SessionListSerializer(many=True)}
    ),
    retrieve=extend_schema(
        tags=['Authentication'],
        summary='Get Session Details',
        description='Retrieve detailed session information',
        responses={200: SessionDetailSerializer}
    ),
    destroy=extend_schema(
        tags=['Authentication'],
        summary='Revoke Session',
        description='Revoke a specific user session',
        responses={204: None}
    ),
)
class SessionManagementViewSet(ModelViewSet):
    """
    ViewSet for managing user sessions with enterprise security features.
    """
    queryset = Session.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    throttle_classes = [UserRateThrottle]
    http_method_names = ['get', 'delete', 'post']  # No PUT/PATCH for sessions
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return SessionListSerializer
        elif self.action == 'create_session':
            return SessionCreateSerializer
        else:
            return SessionDetailSerializer
    
    def get_queryset(self):
        """Return sessions for authenticated user or admin view."""
        user = self.request.user
        if user.is_superuser or user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]:
            # Admin can see all sessions if user_id is provided
            user_id = self.request.query_params.get('user_id')
            if user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                    return AuthenticationService.get_user_sessions(target_user)
                except User.DoesNotExist:
                    return []
            else:
                return AuthenticationService.get_user_sessions(user)
        else:
            return AuthenticationService.get_user_sessions(user)
    
    def list(self, request, *args, **kwargs):
        """List user sessions with filtering options."""
        sessions = self.get_queryset()
        
        # Filter by active status
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            sessions = [s for s in sessions if s.get('is_active', False)]
        
        # Filter by device type
        device_type = request.query_params.get('device_type')
        if device_type:
            sessions = [s for s in sessions if s.get('device_type') == device_type]
        
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get detailed session information."""
        sessions = self.get_queryset()
        session = next((s for s in sessions if s.get('session_id') == pk), None)
        
        if not session:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(session)
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """Revoke a specific session."""
        user = request.user
        target_user = user
        
        # Admin can revoke sessions for other users
        if (user.is_superuser or user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            user_id = request.query_params.get('user_id')
            if user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        
        result = AuthenticationService.revoke_session(target_user, pk)
        
        if result.get('status') == 'success':
            AuditLog.log_action(
                AuditLog.ActionType.SESSION_REVOKED,
                request=request,
                user=target_user,
                severity=AuditLog.Severity.MEDIUM,
                details={
                    'session_id': pk,
                    'revoked_by': user.corporate_email,
                    'self_revoked': user == target_user
                }
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['delete'], url_path='revoke-all')
    @extend_schema(
        tags=['Authentication'],
        summary='Revoke All Sessions',
        description='Revoke all sessions for authenticated user',
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}, 'message': {'type': 'string'}}}}
    )
    def revoke_all(self, request):
        """Revoke all sessions for user."""
        user = request.user
        target_user = user
        
        # Admin can revoke all sessions for other users
        if (user.is_superuser or user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            user_id = request.query_params.get('user_id')
            if user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        
        result = AuthenticationService.revoke_all_sessions(target_user)
        
        AuditLog.log_action(
            AuditLog.ActionType.SESSION_REVOKED,
            request=request,
            user=target_user,
            severity=AuditLog.Severity.HIGH,
            details={
                'revoke_all': True,
                'revoked_by': user.corporate_email,
                'self_revoked': user == target_user
            }
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='active-count')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Active Sessions Count',
        description='Get count of active sessions for user',
        responses={200: {'type': 'object', 'properties': {'active_sessions': {'type': 'integer'}}}}
    )
    def active_count(self, request):
        """Get count of active sessions."""
        sessions = self.get_queryset()
        active_count = sum(1 for s in sessions if s.get('is_active', False))
        
        return Response({
            'active_sessions': active_count,
            'total_sessions': len(sessions)
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='security-analysis')
    @extend_schema(
        tags=['Authentication'],
        summary='Session Security Analysis',
        description='Get security analysis of user sessions',
        responses={200: {'type': 'object'}}
    )
    def security_analysis(self, request):
        """Provide security analysis of user sessions."""
        sessions = self.get_queryset()
        
        # Analyze session patterns
        analysis = {
            'total_sessions': len(sessions),
            'active_sessions': sum(1 for s in sessions if s.get('is_active', False)),
            'suspicious_sessions': 0,
            'locations': {},
            'devices': {},
            'recent_activity': []
        }
        
        for session in sessions:
            # Count locations
            location = session.get('location', 'Unknown')
            analysis['locations'][location] = analysis['locations'].get(location, 0) + 1
            
            # Count devices
            device = session.get('device_type', 'Unknown')
            analysis['devices'][device] = analysis['devices'].get(device, 0) + 1
            
            # Check for suspicious activity
            if session.get('suspicious_activity', False):
                analysis['suspicious_sessions'] += 1
            
            # Add to recent activity if within last 24 hours
            last_activity = session.get('last_activity')
            if last_activity:
                # Add to recent activity list
                analysis['recent_activity'].append({
                    'session_id': session.get('session_id'),
                    'activity_time': last_activity,
                    'location': location,
                    'device': device
                })
        
        # Sort recent activity by time
        analysis['recent_activity'].sort(
            key=lambda x: x['activity_time'], 
            reverse=True
        )
        analysis['recent_activity'] = analysis['recent_activity'][:10]  # Limit to 10 most recent
        
        return Response(analysis, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='mark-suspicious')
    @extend_schema(
        tags=['Authentication'],
        summary='Mark Session as Suspicious',
        description='Mark a session as suspicious and optionally revoke it',
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}}}}
    )
    def mark_suspicious(self, request, pk=None):
        """Mark session as suspicious."""
        revoke_session = request.data.get('revoke', False)
        reason = request.data.get('reason', 'Manual review')
        
        user = request.user
        target_user = user
        
        # Admin can mark sessions for other users
        if (user.is_superuser or user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            user_id = request.query_params.get('user_id')
            if user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        
        # Log suspicious activity
        AuditLog.log_action(
            AuditLog.ActionType.SUSPICIOUS_LOGIN,
            request=request,
            user=target_user,
            severity=AuditLog.Severity.HIGH,
            details={
                'session_id': pk,
                'reason': reason,
                'marked_by': user.corporate_email,
                'will_revoke': revoke_session
            }
        )
        
        result = {'status': 'success', 'message': 'Session marked as suspicious'}
        
        if revoke_session:
            revoke_result = AuthenticationService.revoke_session(target_user, pk)
            if revoke_result.get('status') == 'success':
                result['message'] += ' and revoked'
            else:
                result['message'] += ' but failed to revoke'
        
        return Response(result, status=status.HTTP_200_OK)
