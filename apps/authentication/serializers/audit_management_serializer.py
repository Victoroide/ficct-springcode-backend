"""
Enterprise Audit Management Serializers
Serializers for audit log management and security reporting.
"""

from rest_framework import serializers
from apps.audit.models import AuditLog
from django.contrib.auth import get_user_model

User = get_user_model()


class AuditLogListSerializer(serializers.ModelSerializer):
    """Serializer for audit log list view."""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    action_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_email', 'action', 'action_display', 'resource_type',
            'resource_id', 'ip_address', 'user_agent', 'timestamp', 'success'
        ]
    
    def get_action_display(self, obj):
        """Get human-readable action description."""
        action_map = {
            'LOGIN': 'User Login',
            'LOGOUT': 'User Logout',
            'REGISTER': 'User Registration',
            'PASSWORD_CHANGE': 'Password Change',
            '2FA_SETUP': '2FA Setup',
            '2FA_DISABLE': '2FA Disable',
            'SESSION_REVOKE': 'Session Revoked',
            'PROFILE_UPDATE': 'Profile Update',
            'DOMAIN_CREATE': 'Domain Created',
            'DOMAIN_UPDATE': 'Domain Updated',
            'DOMAIN_DELETE': 'Domain Deleted',
            'USER_CREATE': 'User Created',
            'USER_UPDATE': 'User Updated',
            'USER_DELETE': 'User Deleted',
        }
        return action_map.get(obj.action, obj.action)


class AuditLogDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual audit log entry."""
    
    user_details = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    metadata_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user_details', 'action', 'action_display', 'resource_type',
            'resource_id', 'ip_address', 'user_agent', 'timestamp', 'success',
            'metadata', 'metadata_formatted'
        ]
    
    def get_user_details(self, obj):
        """Get user information for the audit log."""
        if obj.user:
            return {
                'id': obj.user.id,
                'username': obj.user.username,
                'email': obj.user.email,
                'full_name': f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
            }
        return None
    
    def get_action_display(self, obj):
        """Get human-readable action description."""
        action_map = {
            'LOGIN': 'User Login',
            'LOGOUT': 'User Logout',
            'REGISTER': 'User Registration',
            'PASSWORD_CHANGE': 'Password Change',
            '2FA_SETUP': '2FA Setup',
            '2FA_DISABLE': '2FA Disable',
            'SESSION_REVOKE': 'Session Revoked',
            'PROFILE_UPDATE': 'Profile Update',
            'DOMAIN_CREATE': 'Domain Created',
            'DOMAIN_UPDATE': 'Domain Updated',
            'DOMAIN_DELETE': 'Domain Deleted',
            'USER_CREATE': 'User Created',
            'USER_UPDATE': 'User Updated',
            'USER_DELETE': 'User Deleted',
        }
        return action_map.get(obj.action, obj.action)
    
    def get_metadata_formatted(self, obj):
        """Format metadata for better readability."""
        if not obj.metadata:
            return None
        
        # Format common metadata fields
        formatted = {}
        for key, value in obj.metadata.items():
            if key == 'changes':
                formatted['changes'] = value
            elif key == 'old_values':
                formatted['previous_values'] = value
            elif key == 'new_values':
                formatted['new_values'] = value
            else:
                formatted[key] = value
        
        return formatted


class AuditLogStatisticsSerializer(serializers.Serializer):
    """Serializer for audit log statistics."""
    
    total_logs = serializers.IntegerField()
    successful_actions = serializers.IntegerField()
    failed_actions = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    unique_ips = serializers.IntegerField()
    action_breakdown = serializers.DictField()
    recent_activity = serializers.ListField(child=serializers.DictField())


class SecurityEventSerializer(serializers.Serializer):
    """Serializer for security event analysis."""
    
    event_type = serializers.CharField()
    severity = serializers.ChoiceField(choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
    count = serializers.IntegerField()
    first_occurrence = serializers.DateTimeField()
    last_occurrence = serializers.DateTimeField()
    affected_users = serializers.ListField(child=serializers.CharField())
    details = serializers.DictField()


class FailedLoginSerializer(serializers.Serializer):
    """Serializer for failed login attempts analysis."""
    
    ip_address = serializers.IPAddressField()
    attempted_usernames = serializers.ListField(child=serializers.CharField())
    attempt_count = serializers.IntegerField()
    first_attempt = serializers.DateTimeField()
    last_attempt = serializers.DateTimeField()
    is_blocked = serializers.BooleanField()


class AuditLogExportSerializer(serializers.Serializer):
    """Serializer for audit log export parameters."""
    
    format = serializers.ChoiceField(choices=['CSV', 'JSON', 'PDF'])
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    actions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    include_metadata = serializers.BooleanField(default=True)


class UserActivityTimelineSerializer(serializers.Serializer):
    """Serializer for user activity timeline."""
    
    user_id = serializers.IntegerField()
    timeline_data = serializers.ListField(child=serializers.DictField())
    summary = serializers.DictField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
