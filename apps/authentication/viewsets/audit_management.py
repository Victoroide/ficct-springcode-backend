"""
Enterprise Audit Log Management ViewSet
Read-only operations for audit log access with proper filtering and permissions.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from ..serializers import (
    AuditLogListSerializer,
    AuditLogDetailSerializer,
    AuditLogStatisticsSerializer,
)
# from ..permissions import IsOwnerOrAdmin

class IsOwnerOrAdmin:
    """Temporary permission class."""
    pass
from apps.audit.models import AuditLog

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=['Authentication'],
        summary='List Audit Logs',
        description='Get paginated list of audit logs with filtering options',
        responses={200: AuditLogListSerializer(many=True)}
    ),
    retrieve=extend_schema(
        tags=['Authentication'],
        summary='Get Audit Log Details',
        description='Retrieve detailed audit log information',
        responses={200: AuditLogDetailSerializer}
    ),
)
class AuditLogViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for audit log management with enterprise filtering and analytics.
    """
    queryset = AuditLog.objects.all()
    throttle_classes = [UserRateThrottle]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return AuditLogListSerializer
        elif self.action == 'statistics':
            return AuditLogStatsSerializer
        else:
            return AuditLogDetailSerializer
    
    def get_permissions(self):
        """Define permissions based on action."""
        if self.action in ['list', 'retrieve']:
            # Users can see their own logs, admins can see all
            permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        else:
            # Analytics require admin privileges
            permission_classes = [IsAuthenticated, IsAdminUser]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters."""
        user = self.request.user
        queryset = AuditLog.objects.all()
        
        # Non-admin users can only see their own logs
        if not (user.is_superuser or user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            queryset = queryset.filter(user=user)
        
        # Apply filters from query parameters
        return self._apply_filters(queryset)
    
    def _apply_filters(self, queryset):
        """Apply filtering based on query parameters."""
        params = self.request.query_params
        
        # Filter by user (admin only)
        user_id = params.get('user_id')
        if user_id and (self.request.user.is_superuser or 
                       self.request.user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action type
        action_type = params.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        # Filter by severity
        severity = params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by date range
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Filter by success/failure
        success = params.get('success')
        if success is not None:
            success_bool = success.lower() in ['true', '1', 'yes']
            if success_bool:
                queryset = queryset.filter(status_code__lt=400)
            else:
                queryset = queryset.filter(status_code__gte=400)
        
        # Search in details
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(details__icontains=search) |
                Q(error_message__icontains=search) |
                Q(ip_address__icontains=search)
            )
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['get'], url_path='statistics')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Audit Statistics',
        description='Get statistical overview of audit logs (Admin only)',
        responses={200: AuditLogStatisticsSerializer}
    )
    def statistics(self, request):
        """Get audit log statistics and analytics."""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        queryset = self.get_queryset().filter(timestamp__gte=start_date)
        
        # Basic counts
        total_logs = queryset.count()
        error_logs = queryset.filter(status_code__gte=400).count()
        success_logs = total_logs - error_logs
        
        # Activity by action type
        action_stats = queryset.values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Activity by severity
        severity_stats = queryset.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Activity by user (top 10)
        user_stats = queryset.values('user__corporate_email').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Daily activity trend
        from django.db.models import DateField
        from django.db.models.functions import Cast
        daily_stats = queryset.extra(
            select={'date': 'date(timestamp)'}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Security events (high severity)
        security_events = queryset.filter(
            severity=AuditLog.Severity.HIGH
        ).count()
        
        # Failed login attempts
        failed_logins = queryset.filter(
            action_type=AuditLog.ActionType.LOGIN_FAILED
        ).count()
        
        statistics = {
            'period_days': days,
            'total_events': total_logs,
            'success_events': success_logs,
            'error_events': error_logs,
            'security_events': security_events,
            'failed_logins': failed_logins,
            'success_rate': (success_logs / total_logs * 100) if total_logs > 0 else 0,
            'action_breakdown': list(action_stats),
            'severity_breakdown': list(severity_stats),
            'top_users': list(user_stats),
            'daily_trend': list(daily_stats),
        }
        
        serializer = self.get_serializer(statistics)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='security-events')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Security Events',
        description='Get high-severity security events (Admin only)',
        responses={200: AuditLogListSerializer(many=True)}
    )
    def security_events(self, request):
        """Get security-related events."""
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        security_logs = self.get_queryset().filter(
            timestamp__gte=start_date,
            severity__in=[AuditLog.Severity.HIGH, AuditLog.Severity.CRITICAL]
        ).order_by('-timestamp')
        
        serializer = AuditLogListSerializer(security_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='failed-logins')
    @extend_schema(
        tags=['Authentication'],
        summary='Get Failed Login Attempts',
        description='Get failed login attempts with IP analysis (Admin only)',
        responses={200: {'type': 'object'}}
    )
    def failed_logins(self, request):
        """Get failed login attempts with analysis."""
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        failed_attempts = self.get_queryset().filter(
            timestamp__gte=start_date,
            action_type=AuditLog.ActionType.LOGIN_FAILED
        )
        
        # Group by IP address
        ip_stats = failed_attempts.values('ip_address').annotate(
            attempt_count=Count('id')
        ).order_by('-attempt_count')
        
        # Group by user
        user_stats = failed_attempts.values('user__corporate_email').annotate(
            attempt_count=Count('id')
        ).order_by('-attempt_count')
        
        # Recent attempts
        recent_attempts = failed_attempts.order_by('-timestamp')[:20]
        
        analysis = {
            'total_failed_attempts': failed_attempts.count(),
            'unique_ips': failed_attempts.values('ip_address').distinct().count(),
            'unique_users': failed_attempts.values('user').distinct().count(),
            'top_ips': list(ip_stats[:10]),
            'top_users': list(user_stats[:10]),
            'recent_attempts': AuditLogListSerializer(recent_attempts, many=True).data
        }
        
        return Response(analysis)
    
    @action(detail=False, methods=['post'], url_path='export')
    @extend_schema(
        tags=['Authentication'],
        summary='Export Audit Logs',
        description='Export audit logs in various formats (Admin only)',
        responses={200: {'type': 'object', 'properties': {'download_url': {'type': 'string'}}}}
    )
    def export(self, request):
        """Export audit logs."""
        if not (request.user.is_superuser or 
                request.user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            return Response({
                'error': 'Insufficient permissions to export audit logs.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        export_format = request.data.get('format', 'csv')
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        
        queryset = self.get_queryset()
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Log the export action
        AuditLog.log_action(
            AuditLog.ActionType.DATA_EXPORT,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.MEDIUM,
            details={
                'export_format': export_format,
                'record_count': queryset.count(),
                'date_range': {'from': date_from, 'to': date_to}
            }
        )
        
        # In a real implementation, you would generate the file and return a download URL
        return Response({
            'status': 'success',
            'message': f'Export initiated for {queryset.count()} records',
            'format': export_format,
            'download_url': '/api/v1/downloads/audit-logs-export.csv'  # Mock URL
        })
    
    @action(detail=False, methods=['get'], url_path='user-activity/{user_id}')
    @extend_schema(
        tags=['Authentication'],
        summary='Get User Activity Timeline',
        description='Get detailed activity timeline for specific user (Admin only)',
        responses={200: AuditLogListSerializer(many=True)}
    )
    def user_activity(self, request, user_id=None):
        """Get activity timeline for specific user."""
        if not (request.user.is_superuser or 
                request.user.role in [User.UserRole.SUPER_ADMIN, User.UserRole.ADMIN]):
            return Response({
                'error': 'Insufficient permissions to view user activity.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        user_logs = AuditLog.objects.filter(
            user=target_user,
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        serializer = AuditLogListSerializer(user_logs, many=True)
        return Response({
            'user': {
                'id': target_user.id,
                'email': target_user.corporate_email,
                'role': target_user.role,
            },
            'activity_count': user_logs.count(),
            'period_days': days,
            'activities': serializer.data
        })
