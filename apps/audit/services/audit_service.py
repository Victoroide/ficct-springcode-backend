from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
import logging

logger = logging.getLogger('audit_service')


class AuditService:
    
    def __init__(self):
        pass
    
    @classmethod
    def log_user_action(cls, user, action, resource_type=None, resource_id=None, ip_address=None, details=None, **kwargs):
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
            # Handle both authenticated and anonymous users
            audit_user = None
            if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
                audit_user = user
            
            audit_data = {
                'user': audit_user,
                'action_type': action,  # Map 'action' to 'action_type'
                'ip_address': ip_address or '127.0.0.1',
                'details': details or {},
                'severity': 'LOW',  # Default severity
            }
            
            # Add resource information if provided
            if resource_type:
                audit_data['resource_type'] = resource_type
            if resource_id:
                audit_data['resource_id'] = str(resource_id)
            
            # Create audit log entry with error handling
            try:
                audit_log = AuditLog.objects.create(**audit_data)
                logger.info(f"Audit log created: {action} by {user} from {ip_address}")
                return audit_log
            except Exception as create_error:
                # Fallback - create minimal audit log
                minimal_data = {
                    'user': audit_user,
                    'action_type': 'SYSTEM_ACTION',
                    'ip_address': ip_address or '127.0.0.1',
                    'details': {'original_action': action, 'error': str(create_error)},
                    'severity': 'LOW',
                }
                audit_log = AuditLog.objects.create(**minimal_data)
                logger.warning(f"Created fallback audit log due to error: {create_error}")
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
