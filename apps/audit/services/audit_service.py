from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
import logging

logger = logging.getLogger('audit_service')


class AuditService:
    """
    Enterprise audit service for comprehensive user action logging.
    
    Provides centralized audit logging functionality with structured
    data capture and security event tracking.
    """
    
    def __init__(self):
        """Initialize the audit service."""
        pass
    
    def log_user_action(self, user, action, ip_address, details=None, resource=None):
        """
        Log user action with comprehensive audit trail.
        
        Args:
            user: User instance performing the action
            action: Action description/type
            ip_address: Client IP address
            details: Additional action details (dict)
            resource: Related model instance (optional)
        
        Returns:
            AuditLog instance if successful, None if failed
        """
        try:
            audit_data = {
                'user': user if user.is_authenticated else None,
                'action': action,
                'ip_address': ip_address,
                'timestamp': timezone.now(),
                'details': details or {},
            }
            
            # Add resource information if provided
            if resource:
                audit_data.update({
                    'content_type': ContentType.objects.get_for_model(resource),
                    'object_id': str(resource.pk),
                    'object_repr': str(resource)[:200]  # Limit length
                })
            
            # Create audit log entry
            audit_log = AuditLog.objects.create(**audit_data)
            
            logger.info(f"Audit log created: {action} by {user} from {ip_address}")
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            return None
    
    def log_security_event(self, event_type, user=None, ip_address=None, details=None):
        """
        Log security-related events with high priority.
        
        Args:
            event_type: Type of security event
            user: User involved (if any)
            ip_address: Source IP address
            details: Event details
        """
        try:
            action = f"SECURITY_EVENT_{event_type}"
            return self.log_user_action(
                user=user,
                action=action,
                ip_address=ip_address or '0.0.0.0',
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
            return None
    
    def log_system_action(self, action, details=None):
        """
        Log system-initiated actions.
        
        Args:
            action: System action description
            details: Additional details
        """
        try:
            return self.log_user_action(
                user=None,
                action=f"SYSTEM_{action}",
                ip_address='127.0.0.1',
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to log system action: {str(e)}")
            return None
