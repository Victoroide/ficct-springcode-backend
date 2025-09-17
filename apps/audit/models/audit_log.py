"""
Audit Log Model - Core audit logging for enterprise security tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import Dict, Any


class AuditLog(models.Model):
    """
    Enterprise audit log model for tracking critical user actions and security events.
    
    Provides comprehensive logging capabilities including:
    - User authentication events
    - Security incidents and violations
    - Administrative actions
    - API access patterns
    - Geographic and session context
    """
    
    class ActionType(models.TextChoices):
        # Authentication Actions
        LOGIN_SUCCESS = 'LOGIN_SUCCESS', 'Successful Login'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Failed Login Attempt'
        LOGOUT = 'LOGOUT', 'User Logout'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Changed'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
        
        # 2FA Actions
        TWO_FA_ENABLED = '2FA_ENABLED', '2FA Enabled'
        TWO_FA_DISABLED = '2FA_DISABLED', '2FA Disabled'
        TWO_FA_SUCCESS = '2FA_SUCCESS', '2FA Verification Success'
        TWO_FA_FAILED = '2FA_FAILED', '2FA Verification Failed'
        BACKUP_CODE_USED = 'BACKUP_CODE_USED', 'Backup Code Used'
        
        # Account Management
        ACCOUNT_CREATED = 'ACCOUNT_CREATED', 'Account Created'
        ACCOUNT_LOCKED = 'ACCOUNT_LOCKED', 'Account Locked'
        ACCOUNT_UNLOCKED = 'ACCOUNT_UNLOCKED', 'Account Unlocked'
        EMAIL_VERIFIED = 'EMAIL_VERIFIED', 'Email Verified'
        PROFILE_UPDATED = 'PROFILE_UPDATED', 'Profile Updated'
        
        # Security Events
        SUSPICIOUS_LOGIN = 'SUSPICIOUS_LOGIN', 'Suspicious Login Detected'
        RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED', 'Rate Limit Exceeded'
        UNAUTHORIZED_ACCESS = 'UNAUTHORIZED_ACCESS', 'Unauthorized Access Attempt'
        SESSION_HIJACK = 'SESSION_HIJACK', 'Potential Session Hijacking'
        
        # Admin Actions
        ADMIN_LOGIN = 'ADMIN_LOGIN', 'Admin Login'
        PERMISSION_GRANTED = 'PERMISSION_GRANTED', 'Permission Granted'
        PERMISSION_REVOKED = 'PERMISSION_REVOKED', 'Permission Revoked'
        DOMAIN_ADDED = 'DOMAIN_ADDED', 'Authorized Domain Added'
        DOMAIN_REMOVED = 'DOMAIN_REMOVED', 'Authorized Domain Removed'
        
        # API Actions
        API_ACCESS = 'API_ACCESS', 'API Access'
        API_UNAUTHORIZED = 'API_UNAUTHORIZED', 'Unauthorized API Access'
        TOKEN_GENERATED = 'TOKEN_GENERATED', 'JWT Token Generated'
        TOKEN_REVOKED = 'TOKEN_REVOKED', 'JWT Token Revoked'
    
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'
    
    # Core audit fields
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='User who performed the action (null for anonymous actions)'
    )
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        help_text='Type of action performed'
    )
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.LOW,
        help_text='Security severity level'
    )
    
    # Request context
    ip_address = models.GenericIPAddressField(
        help_text='IP address of the request'
    )
    user_agent = models.TextField(
        blank=True,
        help_text='User agent string from the request'
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text='Session key if available'
    )
    
    # Action details
    resource = models.CharField(
        max_length=200,
        blank=True,
        help_text='Resource or endpoint accessed'
    )
    method = models.CharField(
        max_length=10,
        blank=True,
        help_text='HTTP method used'
    )
    status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='HTTP status code returned'
    )
    
    # Additional context
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional details about the action'
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error message if action failed'
    )
    
    # Timestamps
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='When the action occurred'
    )
    
    # Geographic info (optional)
    country = models.CharField(
        max_length=2,
        blank=True,
        help_text='Country code based on IP'
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text='City based on IP'
    )
    
    class Meta:
        app_label = 'audit'
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'action_type']),
        ]
    
    def __str__(self) -> str:
        user_info = self.user.corporate_email if self.user else 'Anonymous'
        return f"{self.action_type} by {user_info} at {self.timestamp}"
    
    @classmethod
    def log_action(
        cls,
        action_type: str,
        request=None,
        user=None,
        severity: str = Severity.LOW,
        details: Dict[str, Any] = None,
        error_message: str = '',
        **kwargs
    ) -> 'AuditLog':
        """
        Convenience method to create audit log entries.
        
        Args:
            action_type: Type of action from ActionType choices
            request: Django request object (optional)
            user: User who performed the action (optional)
            severity: Security severity level
            details: Additional context data
            error_message: Error message if applicable
            **kwargs: Additional fields
        
        Returns:
            Created AuditLog instance
        """
        if details is None:
            details = {}
        
        # Extract info from request if provided
        ip_address = '127.0.0.1'  # Default
        user_agent = ''
        session_key = ''
        resource = ''
        method = ''
        
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length
            session_key = request.session.session_key or ''
            resource = request.path
            method = request.method
            
            # Extract user from request if not provided
            if not user and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
        
        # Override with any kwargs
        log_data = {
            'user': user,
            'action_type': action_type,
            'severity': severity,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_key': session_key,
            'resource': resource,
            'method': method,
            'details': details,
            'error_message': error_message,
            **kwargs
        }
        
        return cls.objects.create(**log_data)
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def is_suspicious(self) -> bool:
        """
        Check if this audit log entry represents suspicious activity.
        
        Returns:
            bool: True if the action is considered suspicious
        """
        suspicious_actions = [
            self.ActionType.LOGIN_FAILED,
            self.ActionType.TWO_FA_FAILED,
            self.ActionType.SUSPICIOUS_LOGIN,
            self.ActionType.UNAUTHORIZED_ACCESS,
            self.ActionType.SESSION_HIJACK,
            self.ActionType.RATE_LIMIT_EXCEEDED,
        ]
        
        return (
            self.action_type in suspicious_actions or
            self.severity in [self.Severity.HIGH, self.Severity.CRITICAL]
        )
    
    def get_risk_score(self) -> int:
        """
        Calculate a risk score for this audit entry (0-100).
        
        Returns:
            int: Risk score between 0 and 100
        """
        base_scores = {
            self.ActionType.LOGIN_FAILED: 20,
            self.ActionType.TWO_FA_FAILED: 30,
            self.ActionType.SUSPICIOUS_LOGIN: 50,
            self.ActionType.UNAUTHORIZED_ACCESS: 70,
            self.ActionType.SESSION_HIJACK: 90,
            self.ActionType.RATE_LIMIT_EXCEEDED: 40,
        }
        
        severity_multiplier = {
            self.Severity.LOW: 1.0,
            self.Severity.MEDIUM: 1.5,
            self.Severity.HIGH: 2.0,
            self.Severity.CRITICAL: 2.5,
        }
        
        base_score = base_scores.get(self.action_type, 10)
        multiplier = severity_multiplier.get(self.severity, 1.0)
        
        return min(int(base_score * multiplier), 100)
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the audit log context for reporting.
        
        Returns:
            Dict containing context summary
        """
        return {
            'user_email': self.user.corporate_email if self.user else None,
            'action': self.get_action_type_display(),
            'severity': self.get_severity_display(),
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'location': f"{self.city}, {self.country}" if self.city and self.country else None,
            'resource': self.resource,
            'method': self.method,
            'status_code': self.status_code,
            'risk_score': self.get_risk_score(),
            'suspicious': self.is_suspicious()
        }
    
    @classmethod
    def get_user_activity_summary(cls, user, days: int = 30) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.
        
        Args:
            user: EnterpriseUser instance
            days: Number of days to look back
            
        Returns:
            Dict containing user activity summary
        """
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        logs = cls.objects.filter(
            user=user,
            timestamp__gte=start_date
        )
        
        return {
            'total_actions': logs.count(),
            'login_attempts': logs.filter(action_type=cls.ActionType.LOGIN_SUCCESS).count(),
            'failed_logins': logs.filter(action_type=cls.ActionType.LOGIN_FAILED).count(),
            'suspicious_events': logs.filter(
                action_type__in=[
                    cls.ActionType.SUSPICIOUS_LOGIN,
                    cls.ActionType.UNAUTHORIZED_ACCESS,
                    cls.ActionType.RATE_LIMIT_EXCEEDED
                ]
            ).count(),
            'unique_ips': logs.values_list('ip_address', flat=True).distinct().count(),
            'avg_risk_score': logs.aggregate(
                avg_risk=models.Avg('details__risk_score')
            )['avg_risk'] or 0,
            'period_days': days
        }
    
    @classmethod
    def get_security_metrics(cls, days: int = 7) -> Dict[str, Any]:
        """
        Get enterprise security metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict containing security metrics
        """
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        logs = cls.objects.filter(timestamp__gte=start_date)
        
        return {
            'total_events': logs.count(),
            'failed_logins': logs.filter(action_type=cls.ActionType.LOGIN_FAILED).count(),
            'successful_logins': logs.filter(action_type=cls.ActionType.LOGIN_SUCCESS).count(),
            'suspicious_events': logs.filter(
                severity__in=[cls.Severity.HIGH, cls.Severity.CRITICAL]
            ).count(),
            'unique_users': logs.exclude(user__isnull=True).values_list('user', flat=True).distinct().count(),
            'unique_ips': logs.values_list('ip_address', flat=True).distinct().count(),
            'admin_actions': logs.filter(
                action_type__in=[
                    cls.ActionType.ADMIN_LOGIN,
                    cls.ActionType.PERMISSION_GRANTED,
                    cls.ActionType.PERMISSION_REVOKED
                ]
            ).count(),
            'api_calls': logs.filter(action_type=cls.ActionType.API_ACCESS).count(),
            'period_days': days
        }
