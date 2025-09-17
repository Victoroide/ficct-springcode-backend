"""
Email Service - Business logic for enterprise email communications.
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from apps.accounts.models import EnterpriseUser
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger('authentication')


class EmailService:
    """
    Service class for handling enterprise email communications.
    
    Implements:
    - Email verification messages
    - Welcome emails
    - Password reset notifications
    - Security alert emails
    - Administrative notifications
    """
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ficct-enterprise.com')
        self.support_email = getattr(settings, 'SUPPORT_EMAIL', 'support@ficct-enterprise.com')
        self.company_name = 'FICCT Enterprise Platform'
    
    def send_verification_email(self, user: EnterpriseUser) -> bool:
        """
        Send email verification message to new user.
        
        Args:
            user: EnterpriseUser instance requiring verification
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            if not user.email_verification_token:
                user.generate_email_verification_token()
            
            # Create verification link
            verification_url = self._build_verification_url(user.email_verification_token, user.corporate_email)
            
            # Email context
            context = {
                'user': user,
                'verification_url': verification_url,
                'company_name': self.company_name,
                'support_email': self.support_email,
                'token_expires_hours': 24
            }
            
            # Render email templates
            subject = f'Verify your {self.company_name} account'
            html_message = self._render_email_template('emails/verification_email.html', context)
            plain_message = self._render_email_template('emails/verification_email.txt', context)
            
            # Send email
            success = self._send_email(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.corporate_email]
            )
            
            if success:
                logger.info(f"Verification email sent to {user.corporate_email}")
            else:
                logger.error(f"Failed to send verification email to {user.corporate_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Verification email error for {user.corporate_email}: {str(e)}")
            return False
    
    def send_welcome_email(self, user: EnterpriseUser) -> bool:
        """
        Send welcome email to newly verified user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Email context
            context = {
                'user': user,
                'company_name': self.company_name,
                'support_email': self.support_email,
                'login_url': self._build_login_url(),
                'setup_2fa_recommended': not user.is_2fa_enabled
            }
            
            # Render email templates
            subject = f'Welcome to {self.company_name}!'
            html_message = self._render_email_template('emails/welcome_email.html', context)
            plain_message = self._render_email_template('emails/welcome_email.txt', context)
            
            # Send email
            success = self._send_email(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.corporate_email]
            )
            
            if success:
                logger.info(f"Welcome email sent to {user.corporate_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Welcome email error for {user.corporate_email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, user: EnterpriseUser, reset_token: str) -> bool:
        """
        Send password reset email with secure reset link.
        
        Args:
            user: EnterpriseUser instance
            reset_token: Password reset token
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Create password reset link
            reset_url = self._build_password_reset_url(reset_token, user.corporate_email)
            
            # Email context
            context = {
                'user': user,
                'reset_url': reset_url,
                'company_name': self.company_name,
                'support_email': self.support_email,
                'token_expires_hours': 1,
                'requested_ip': getattr(user, '_reset_ip', 'Unknown')  # This would be set when requesting reset
            }
            
            # Render email templates
            subject = f'Password Reset - {self.company_name}'
            html_message = self._render_email_template('emails/password_reset_email.html', context)
            plain_message = self._render_email_template('emails/password_reset_email.txt', context)
            
            # Send email
            success = self._send_email(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.corporate_email]
            )
            
            if success:
                logger.info(f"Password reset email sent to {user.corporate_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Password reset email error for {user.corporate_email}: {str(e)}")
            return False
    
    def send_security_alert_email(self, user: EnterpriseUser, alert_type: str, details: Dict[str, Any]) -> bool:
        """
        Send security alert email to user.
        
        Args:
            user: EnterpriseUser instance
            alert_type: Type of security alert
            details: Alert details
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Email context
            context = {
                'user': user,
                'alert_type': alert_type,
                'details': details,
                'company_name': self.company_name,
                'support_email': self.support_email,
                'timestamp': details.get('timestamp', 'Unknown')
            }
            
            # Determine alert severity and subject
            severity_map = {
                'login_from_new_location': ('Medium', 'Login from new location detected'),
                'multiple_failed_attempts': ('High', 'Multiple failed login attempts detected'),
                'password_changed': ('Medium', 'Password changed successfully'),
                '2fa_disabled': ('High', 'Two-Factor Authentication disabled'),
                'account_locked': ('High', 'Account temporarily locked'),
                'suspicious_activity': ('Critical', 'Suspicious activity detected')
            }
            
            severity, alert_message = severity_map.get(alert_type, ('Medium', 'Security alert'))
            subject = f'Security Alert - {alert_message}'
            
            context.update({
                'severity': severity,
                'alert_message': alert_message
            })
            
            # Render email templates
            html_message = self._render_email_template('emails/security_alert_email.html', context)
            plain_message = self._render_email_template('emails/security_alert_email.txt', context)
            
            # Send email
            success = self._send_email(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.corporate_email]
            )
            
            if success:
                logger.info(f"Security alert email sent to {user.corporate_email}: {alert_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"Security alert email error for {user.corporate_email}: {str(e)}")
            return False
    
    def send_2fa_setup_email(self, user: EnterpriseUser) -> bool:
        """
        Send 2FA setup instructions email.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Email context
            context = {
                'user': user,
                'company_name': self.company_name,
                'support_email': self.support_email,
                'setup_url': self._build_2fa_setup_url()
            }
            
            # Render email templates
            subject = f'Set up Two-Factor Authentication - {self.company_name}'
            html_message = self._render_email_template('emails/2fa_setup_email.html', context)
            plain_message = self._render_email_template('emails/2fa_setup_email.txt', context)
            
            # Send email
            success = self._send_email(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.corporate_email]
            )
            
            if success:
                logger.info(f"2FA setup email sent to {user.corporate_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"2FA setup email error for {user.corporate_email}: {str(e)}")
            return False
    
    def send_admin_notification(self, subject: str, message: str, admin_emails: Optional[List[str]] = None) -> bool:
        """
        Send notification email to administrators.
        
        Args:
            subject: Email subject
            message: Email message
            admin_emails: Optional list of admin emails, defaults to all admins
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            if not admin_emails:
                # Get all admin users
                admin_users = EnterpriseUser.objects.filter(
                    role__in=[EnterpriseUser.UserRole.SUPER_ADMIN, EnterpriseUser.UserRole.ADMIN],
                    is_active=True,
                    email_verified=True
                )
                admin_emails = [user.corporate_email for user in admin_users]
            
            if not admin_emails:
                logger.warning("No admin emails found for notification")
                return False
            
            # Email context
            context = {
                'message': message,
                'company_name': self.company_name,
                'support_email': self.support_email
            }
            
            # Render email templates
            html_message = self._render_email_template('emails/admin_notification.html', context)
            plain_message = message  # Use plain message as is
            
            # Send email
            success = self._send_email(
                subject=f'[{self.company_name}] {subject}',
                message=plain_message,
                html_message=html_message,
                recipient_list=admin_emails
            )
            
            if success:
                logger.info(f"Admin notification sent: {subject}")
            
            return success
            
        except Exception as e:
            logger.error(f"Admin notification email error: {str(e)}")
            return False
    
    def send_bulk_notification(self, users: List[EnterpriseUser], subject: str, template_name: str, context: Dict[str, Any]) -> Dict[str, int]:
        """
        Send bulk notification to multiple users.
        
        Args:
            users: List of EnterpriseUser instances
            subject: Email subject
            template_name: Email template name (without extension)
            context: Template context
            
        Returns:
            Dict with success and failure counts
        """
        results = {'success': 0, 'failed': 0}
        
        try:
            for user in users:
                try:
                    # Add user to context
                    user_context = context.copy()
                    user_context.update({
                        'user': user,
                        'company_name': self.company_name,
                        'support_email': self.support_email
                    })
                    
                    # Render email templates
                    html_message = self._render_email_template(f'emails/{template_name}.html', user_context)
                    plain_message = self._render_email_template(f'emails/{template_name}.txt', user_context)
                    
                    # Send email
                    success = self._send_email(
                        subject=subject,
                        message=plain_message,
                        html_message=html_message,
                        recipient_list=[user.corporate_email]
                    )
                    
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Bulk email error for {user.corporate_email}: {str(e)}")
                    results['failed'] += 1
            
            logger.info(f"Bulk email completed: {results['success']} success, {results['failed']} failed")
            
        except Exception as e:
            logger.error(f"Bulk email service error: {str(e)}")
        
        return results
    
    def _send_email(self, subject: str, message: str, recipient_list: List[str], html_message: str = '') -> bool:
        """
        Send email using Django's email backend.
        
        Args:
            subject: Email subject
            message: Plain text message
            recipient_list: List of recipient emails
            html_message: Optional HTML message
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # In development, we might not have email configured
            if not getattr(settings, 'EMAIL_BACKEND', None):
                logger.info(f"Email would be sent: {subject} to {recipient_list}")
                return True
            
            sent = send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False
            )
            
            return sent > 0
            
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False
    
    def _render_email_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render email template with context.
        
        Args:
            template_name: Template file name
            context: Template context
            
        Returns:
            str: Rendered template content
        """
        try:
            return render_to_string(template_name, context)
        except Exception as e:
            logger.error(f"Template rendering error for {template_name}: {str(e)}")
            # Return a basic fallback template
            if 'verification' in template_name.lower():
                return f"Please verify your email by clicking this link: {context.get('verification_url', '')}"
            elif 'welcome' in template_name.lower():
                return f"Welcome to {context.get('company_name', 'our platform')}, {context.get('user', {}).get('full_name', 'user')}!"
            else:
                return f"Email from {context.get('company_name', 'our platform')}"
    
    def _build_verification_url(self, token: str, email: str) -> str:
        """
        Build email verification URL.
        
        Args:
            token: Verification token
            email: User email
            
        Returns:
            str: Complete verification URL
        """
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{base_url}/auth/verify-email?token={token}&email={email}"
    
    def _build_password_reset_url(self, token: str, email: str) -> str:
        """
        Build password reset URL.
        
        Args:
            token: Reset token
            email: User email
            
        Returns:
            str: Complete password reset URL
        """
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{base_url}/auth/reset-password?token={token}&email={email}"
    
    def _build_login_url(self) -> str:
        """
        Build login URL.
        
        Returns:
            str: Complete login URL
        """
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{base_url}/auth/login"
    
    def _build_2fa_setup_url(self) -> str:
        """
        Build 2FA setup URL.
        
        Returns:
            str: Complete 2FA setup URL
        """
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{base_url}/auth/setup-2fa"
    
    def validate_email_configuration(self) -> Dict[str, Any]:
        """
        Validate email service configuration.
        
        Returns:
            Dict containing validation results
        """
        validation = {
            'configured': False,
            'backend': None,
            'from_email': self.from_email,
            'issues': []
        }
        
        try:
            # Check email backend
            backend = getattr(settings, 'EMAIL_BACKEND', None)
            validation['backend'] = backend
            
            if not backend:
                validation['issues'].append('EMAIL_BACKEND not configured')
            elif 'console' in backend.lower():
                validation['issues'].append('Using console backend (development only)')
                validation['configured'] = True
            elif 'smtp' in backend.lower() or 'sendgrid' in backend.lower():
                validation['configured'] = True
            
            # Check required settings
            if not self.from_email:
                validation['issues'].append('DEFAULT_FROM_EMAIL not configured')
            
            # Check SMTP settings if using SMTP
            if backend and 'smtp' in backend.lower():
                smtp_settings = ['EMAIL_HOST', 'EMAIL_PORT']
                for setting in smtp_settings:
                    if not getattr(settings, setting, None):
                        validation['issues'].append(f'{setting} not configured')
            
            # Check SendGrid settings if using SendGrid
            if backend and 'sendgrid' in backend.lower():
                if not getattr(settings, 'SENDGRID_API_KEY', None):
                    validation['issues'].append('SENDGRID_API_KEY not configured')
            
        except Exception as e:
            validation['issues'].append(f'Configuration check error: {str(e)}')
        
        return validation
