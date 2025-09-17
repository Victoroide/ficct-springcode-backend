"""
Audit Service - Business logic for enterprise audit logging and security events.
"""

from django.utils import timezone
from apps.accounts.models import EnterpriseUser
from typing import Dict, Any, Optional, List
import logging
import json

logger = logging.getLogger('audit')


class AuditService:
    """
    Service class for handling enterprise audit logging and security monitoring.
    
    Implements:
    - Authentication event logging
    - User action tracking
    - Security event monitoring
    - Audit report generation
    - Compliance logging
    """
    
    def log_authentication_attempt(
        self, 
        email: str, 
        success: bool, 
        ip_address: str, 
        user_agent: str = '',
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log authentication attempt with security context.
        
        Args:
            email: User's corporate email
            success: Whether authentication was successful
            ip_address: Client IP address
            user_agent: Client user agent string
            details: Additional details about the attempt
        """
        try:
            # This would normally create an AuditLog entry
            # For now, we'll log to Django's logging system
            
            log_data = {
                'event_type': 'AUTHENTICATION_ATTEMPT',
                'email': email,
                'success': success,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'timestamp': timezone.now().isoformat(),
                'details': details or {}
            }
            
            if success:
                logger.info(f"Successful authentication: {email} from {ip_address}")
            else:
                logger.warning(f"Failed authentication: {email} from {ip_address}")
            
            # In a real implementation, this would save to AuditLog model
            self._save_audit_log('AUTHENTICATION_ATTEMPT', log_data, email)
            
        except Exception as e:
            logger.error(f"Failed to log authentication attempt: {str(e)}")
    
    def log_user_action(
        self,
        user: EnterpriseUser,
        action: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None,
        resource: str = '',
        method: str = 'POST'
    ) -> None:
        """
        Log user action for audit trail.
        
        Args:
            user: EnterpriseUser performing the action
            action: Action type (e.g., 'LOGIN_SUCCESS', 'PROFILE_UPDATED')
            ip_address: Client IP address
            details: Additional action details
            resource: Resource being accessed
            method: HTTP method
        """
        try:
            log_data = {
                'event_type': 'USER_ACTION',
                'user_id': user.id,
                'corporate_email': user.corporate_email,
                'action': action,
                'ip_address': ip_address,
                'resource': resource,
                'method': method,
                'timestamp': timezone.now().isoformat(),
                'details': details or {}
            }
            
            logger.info(f"User action: {user.corporate_email} - {action} from {ip_address}")
            
            # In a real implementation, this would save to AuditLog model
            self._save_audit_log('USER_ACTION', log_data, user.corporate_email)
            
        except Exception as e:
            logger.error(f"Failed to log user action: {str(e)}")
    
    def log_security_event(
        self,
        event_type: str,
        user: Optional[EnterpriseUser] = None,
        ip_address: str = '',
        details: Optional[Dict[str, Any]] = None,
        severity: str = 'MEDIUM'
    ) -> None:
        """
        Log security event for monitoring and alerting.
        
        Args:
            event_type: Type of security event
            user: Optional user associated with event
            ip_address: Client IP address
            details: Event details
            severity: Event severity (LOW, MEDIUM, HIGH, CRITICAL)
        """
        try:
            log_data = {
                'event_type': 'SECURITY_EVENT',
                'security_event_type': event_type,
                'user_id': user.id if user else None,
                'corporate_email': user.corporate_email if user else '',
                'ip_address': ip_address,
                'severity': severity,
                'timestamp': timezone.now().isoformat(),
                'details': details or {}
            }
            
            # Log with appropriate level based on severity
            if severity in ['HIGH', 'CRITICAL']:
                logger.error(f"Security event: {event_type} - {severity}")
            elif severity == 'MEDIUM':
                logger.warning(f"Security event: {event_type} - {severity}")
            else:
                logger.info(f"Security event: {event_type} - {severity}")
            
            # In a real implementation, this would save to SecurityAlert model
            self._save_security_alert(event_type, log_data, severity)
            
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
    
    def generate_audit_report(
        self,
        user: Optional[EnterpriseUser] = None,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate audit report for specified criteria.
        
        Args:
            user: Optional user to filter by
            start_date: Optional start date for report
            end_date: Optional end date for report
            event_types: Optional list of event types to include
            
        Returns:
            Dict containing audit report data
        """
        try:
            # This would normally query AuditLog model
            # For now, return placeholder data
            
            report = {
                'report_generated_at': timezone.now().isoformat(),
                'filters': {
                    'user': user.corporate_email if user else 'All users',
                    'start_date': start_date.isoformat() if start_date else 'Not specified',
                    'end_date': end_date.isoformat() if end_date else 'Not specified',
                    'event_types': event_types or ['All types']
                },
                'summary': {
                    'total_events': 0,
                    'authentication_attempts': 0,
                    'successful_logins': 0,
                    'failed_logins': 0,
                    'user_actions': 0,
                    'security_events': 0
                },
                'events': [],
                'security_alerts': [],
                'recommendations': []
            }
            
            # Add security recommendations based on patterns
            if user:
                recommendations = self._generate_user_security_recommendations(user)
                report['recommendations'] = recommendations
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate audit report: {str(e)}")
            return {'error': 'Failed to generate report'}
    
    def track_login_patterns(self, user: EnterpriseUser, ip_address: str) -> Dict[str, Any]:
        """
        Track and analyze user login patterns for anomaly detection.
        
        Args:
            user: EnterpriseUser instance
            ip_address: Current login IP address
            
        Returns:
            Dict containing pattern analysis results
        """
        try:
            analysis = {
                'user_id': user.id,
                'current_ip': ip_address,
                'previous_ip': user.last_login_ip,
                'ip_changed': user.last_login_ip != ip_address if user.last_login_ip else False,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'login_frequency': 'normal',  # This would be calculated from historical data
                'suspicious_indicators': []
            }
            
            # Check for suspicious patterns
            if analysis['ip_changed']:
                analysis['suspicious_indicators'].append('IP address change detected')
                
                # Log security event for IP change
                self.log_security_event(
                    event_type='SUSPICIOUS_LOCATION',
                    user=user,
                    ip_address=ip_address,
                    details={
                        'previous_ip': user.last_login_ip,
                        'current_ip': ip_address
                    },
                    severity='MEDIUM'
                )
            
            # Check time-based patterns (placeholder)
            if user.last_login:
                time_since_last = timezone.now() - user.last_login
                if time_since_last.total_seconds() < 300:  # Less than 5 minutes
                    analysis['suspicious_indicators'].append('Rapid successive logins')
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to track login patterns for user {user.id}: {str(e)}")
            return {}
    
    def monitor_failed_attempts(self, email: str, ip_address: str) -> None:
        """
        Monitor and respond to failed login attempts.
        
        Args:
            email: Corporate email address
            ip_address: Client IP address
        """
        try:
            # This would normally track failed attempts per IP and email
            # and trigger security responses like IP blocking
            
            # Log the failed attempt
            self.log_security_event(
                event_type='MULTIPLE_FAILURES',
                ip_address=ip_address,
                details={
                    'email': email,
                    'attempt_time': timezone.now().isoformat()
                },
                severity='MEDIUM'
            )
            
            # Check if this IP has multiple failures (placeholder logic)
            # In real implementation, this would query recent failures
            
        except Exception as e:
            logger.error(f"Failed to monitor failed attempts: {str(e)}")
    
    def log_data_access(
        self,
        user: EnterpriseUser,
        resource: str,
        action: str,
        ip_address: str,
        sensitive: bool = False
    ) -> None:
        """
        Log data access for compliance and monitoring.
        
        Args:
            user: User accessing the data
            resource: Resource being accessed
            action: Action performed (READ, WRITE, DELETE, etc.)
            ip_address: Client IP address
            sensitive: Whether the data is considered sensitive
        """
        try:
            details = {
                'resource': resource,
                'action': action,
                'sensitive_data': sensitive,
                'compliance_relevant': sensitive or action in ['DELETE', 'EXPORT']
            }
            
            self.log_user_action(
                user=user,
                action=f'DATA_ACCESS_{action}',
                ip_address=ip_address,
                details=details,
                resource=resource
            )
            
            # Additional logging for sensitive data access
            if sensitive:
                self.log_security_event(
                    event_type='SENSITIVE_DATA_ACCESS',
                    user=user,
                    ip_address=ip_address,
                    details=details,
                    severity='HIGH'
                )
            
        except Exception as e:
            logger.error(f"Failed to log data access: {str(e)}")
    
    def _save_audit_log(self, event_type: str, log_data: Dict[str, Any], email: str) -> None:
        """
        Save audit log entry (placeholder for actual implementation).
        
        Args:
            event_type: Type of event
            log_data: Log data dictionary
            email: User email for reference
        """
        # This would normally save to AuditLog model
        # For now, just log the JSON data
        logger.info(f"Audit log entry: {json.dumps(log_data, default=str)}")
    
    def _save_security_alert(self, event_type: str, log_data: Dict[str, Any], severity: str) -> None:
        """
        Save security alert (placeholder for actual implementation).
        
        Args:
            event_type: Type of security event
            log_data: Alert data dictionary
            severity: Alert severity level
        """
        # This would normally save to SecurityAlert model
        # For now, just log the JSON data
        logger.warning(f"Security alert: {json.dumps(log_data, default=str)}")
    
    def _generate_user_security_recommendations(self, user: EnterpriseUser) -> List[str]:
        """
        Generate security recommendations for a user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            List of security recommendations
        """
        recommendations = []
        
        if not user.is_2fa_enabled:
            recommendations.append("Enable Two-Factor Authentication for enhanced security")
        
        if user.is_password_expired():
            recommendations.append("Update expired password immediately")
        
        if user.failed_login_attempts > 0:
            recommendations.append("Review recent failed login attempts")
        
        if not user.backup_codes:
            recommendations.append("Generate backup codes for 2FA recovery")
        
        # Check password age
        if user.password_changed_at:
            days_since_change = (timezone.now() - user.password_changed_at).days
            if days_since_change > 60:
                recommendations.append("Consider updating password (last changed over 60 days ago)")
        
        return recommendations
    
    def get_security_dashboard_data(self, user: Optional[EnterpriseUser] = None) -> Dict[str, Any]:
        """
        Get security dashboard data for monitoring.
        
        Args:
            user: Optional user to filter data for
            
        Returns:
            Dict containing dashboard metrics
        """
        try:
            # This would normally aggregate data from AuditLog and SecurityAlert models
            # For now, return placeholder data
            
            dashboard = {
                'generated_at': timezone.now().isoformat(),
                'metrics': {
                    'total_users': EnterpriseUser.objects.count(),
                    'active_users_today': 0,  # Would be calculated from recent activity
                    'failed_logins_today': 0,  # Would be calculated from audit logs
                    'security_alerts_today': 0,  # Would be calculated from security alerts
                    '2fa_enabled_percentage': 0  # Would be calculated from user data
                },
                'recent_alerts': [],  # Would be fetched from SecurityAlert model
                'top_failed_ips': [],  # Would be calculated from failed attempts
                'user_activity_summary': {}
            }
            
            # Calculate 2FA percentage
            total_users = EnterpriseUser.objects.count()
            if total_users > 0:
                users_with_2fa = EnterpriseUser.objects.filter(is_2fa_enabled=True).count()
                dashboard['metrics']['2fa_enabled_percentage'] = round(
                    (users_with_2fa / total_users) * 100, 2
                )
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Failed to get security dashboard data: {str(e)}")
            return {'error': 'Failed to load dashboard data'}
    
    def cleanup_old_audit_logs(self, days_to_keep: int = 365) -> int:
        """
        Clean up old audit logs based on retention policy.
        
        Args:
            days_to_keep: Number of days to retain logs
            
        Returns:
            int: Number of logs cleaned up
        """
        try:
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            
            # This would normally delete old AuditLog entries
            # For now, just log the cleanup attempt
            logger.info(f"Audit log cleanup: would remove logs older than {cutoff_date}")
            
            return 0  # Placeholder return
            
        except Exception as e:
            logger.error(f"Failed to cleanup audit logs: {str(e)}")
            return 0
