"""
Enterprise Session Management Serializers
Serializers for user session management and security operations.
"""

from rest_framework import serializers
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model

User = get_user_model()


class SessionListSerializer(serializers.ModelSerializer):
    """Serializer for session list view."""
    
    is_current = serializers.SerializerMethodField()
    
    class Meta:
        model = Session
        fields = [
            'session_key', 'session_data', 'expire_date', 'is_current'
        ]
    
    def get_is_current(self, obj):
        """Check if this is the current session."""
        request = self.context.get('request')
        if request and hasattr(request, 'session'):
            return obj.session_key == request.session.session_key
        return False
    

class SessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual session information."""
    
    is_current = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = Session
        fields = [
            'session_key', 'session_data', 'expire_date', 'is_current', 'is_expired'
        ]
    
    def get_is_current(self, obj):
        """Check if this is the current session."""
        request = self.context.get('request')
        if request and hasattr(request, 'session'):
            return obj.session_key == request.session.session_key
        return False
    
    def get_is_expired(self, obj):
        """Check if session is expired."""
        from django.utils import timezone
        return obj.expire_date < timezone.now()


class SessionSecurityAnalysisSerializer(serializers.Serializer):
    """Serializer for session security analysis results."""
    
    total_sessions = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    suspicious_sessions = serializers.IntegerField()
    unique_ips = serializers.IntegerField()
    average_duration = serializers.FloatField()
    security_alerts = serializers.ListField(child=serializers.CharField())


class MarkSuspiciousSerializer(serializers.Serializer):
    """Serializer for marking sessions as suspicious."""
    
    session_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=50
    )
    reason = serializers.CharField(max_length=255)
    
    def validate_session_ids(self, value):
        """Validate all session IDs exist."""
        existing_keys = set(Session.objects.filter(session_key__in=value).values_list('session_key', flat=True))
        missing_keys = set(value) - existing_keys
        if missing_keys:
            raise serializers.ValidationError(
                f"Sessions with keys {list(missing_keys)} do not exist."
            )
        return value
