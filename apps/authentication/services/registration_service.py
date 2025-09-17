"""
Registration Service - Business logic for enterprise user registration.
"""

import logging
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.accounts.models import AuthorizedDomain, EnterpriseUser, PasswordHistory
from .email_service import EmailService
from .audit_service import AuditService

logger = logging.getLogger('authentication')


class RegistrationService:
    """Enterprise user registration with domain validation and audit logging."""
    
    def validate_corporate_domain(self, email: str) -> bool:
        if not email or '@' not in email:
            return False
        
        domain = email.split('@')[1].lower()
        return AuthorizedDomain.is_domain_authorized(domain)
    
    @transaction.atomic
    def create_enterprise_user(self, validated_data: Dict[str, Any]) -> EnterpriseUser:
        """Create enterprise user with domain validation and email verification setup."""
        try:
            password = validated_data.pop('password')
            corporate_email = validated_data['corporate_email']
            
            if not self.validate_corporate_domain(corporate_email):
                raise ValueError("Email domain is not authorized for registration")
            
            domain = corporate_email.split('@')[1].lower()
            validated_data['company_domain'] = domain
            
            user = EnterpriseUser(**validated_data)
            user.set_password(password)
            user.is_active = False
            user.email_verified = False
            
            user.save()
            
            user.generate_email_verification_token()
            user.set_password_expiry()
            
            try:
                PasswordHistory.add_password_to_history(user, password)
            except Exception as ph_error:
                logger.warning(f"Could not add password to history: {str(ph_error)}")
            
            logger.info(f"Enterprise user created: {user.corporate_email}")
            
            return user
            
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            raise ValueError(f"Failed to create user: {str(e)}")
    
    def send_verification_email(self, user: EnterpriseUser) -> bool:
        """
        Initiate email verification process for new user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            from .email_service import EmailService
            email_service = EmailService()
            return email_service.send_verification_email(user)
            
        except Exception as e:
            logger.error(f"Verification email error for {user.corporate_email}: {str(e)}")
            return False
    
    def verify_email_token(self, token: str, email: str) -> EnterpriseUser:
        """
        Verify email verification token and activate user.
        
        Args:
            token: Email verification token
            email: Corporate email address
            
        Returns:
            EnterpriseUser: Activated user instance
            
        Raises:
            ValueError: If verification fails
        """
        try:
            user = EnterpriseUser.objects.get(corporate_email=email.lower())
            
            if user.email_verified:
                raise ValueError("Email is already verified")
            
            if user.verify_email_with_token(token):
                user.is_active = True
                user.save(update_fields=['is_active'])
                logger.info(f"Email verified for user: {user.corporate_email}")
                return user
            else:
                raise ValueError("Invalid or expired verification token")
                
        except EnterpriseUser.DoesNotExist:
            raise ValueError("User not found")
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            raise ValueError("Email verification failed")
    
    def setup_2fa_for_user(self, user: EnterpriseUser, secret: str) -> Dict[str, Any]:
        """
        Set up 2FA for enterprise user.
        
        Args:
            user: EnterpriseUser instance
            secret: Base32 TOTP secret
            
        Returns:
            Dict containing setup result and backup codes
        """
        try:
            user.two_factor_secret = secret
            user.enable_2fa()
            
            # Generate backup codes
            backup_codes = user.generate_backup_codes()
            
            logger.info(f"2FA enabled for user: {user.corporate_email}")
            
            return {
                'success': True,
                'backup_codes': backup_codes,
                'message': '2FA enabled successfully'
            }
            
        except Exception as e:
            logger.error(f"2FA setup error for {user.corporate_email}: {str(e)}")
            raise ValueError("Failed to setup 2FA")
    
    def assign_role_permissions(self, user: EnterpriseUser, role: str) -> bool:
        """
        Assign role and associated permissions to user.
        
        Args:
            user: EnterpriseUser instance
            role: User role from UserRole choices
            
        Returns:
            bool: True if role was assigned successfully
        """
        try:
            # Validate role
            if role not in [choice[0] for choice in EnterpriseUser.UserRole.choices]:
                raise ValueError(f"Invalid role: {role}")
            
            # Don't allow direct assignment of SUPER_ADMIN through registration
            if role == EnterpriseUser.UserRole.SUPER_ADMIN:
                raise ValueError("Super Admin role cannot be assigned through registration")
            
            user.role = role
            
            # Set staff status for admin roles
            if role in [EnterpriseUser.UserRole.ADMIN, EnterpriseUser.UserRole.SUPER_ADMIN]:
                user.is_staff = True
            
            user.save(update_fields=['role', 'is_staff'])
            
            logger.info(f"Role {role} assigned to user: {user.corporate_email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Role assignment error for {user.corporate_email}: {str(e)}")
            return False
    
    def get_registration_requirements(self, domain: str = None) -> Dict[str, Any]:
        """
        Get registration requirements for domain or general requirements.
        
        Args:
            domain: Optional domain to check specific requirements
            
        Returns:
            Dict containing registration requirements
        """
        requirements = {
            'password_requirements': {
                'min_length': 12,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_digits': True,
                'require_special': True,
                'no_consecutive': True
            },
            'email_verification_required': True,
            '2fa_recommended': True,
            'available_roles': [
                {
                    'value': role[0],
                    'label': role[1],
                    'assignable': role[0] != EnterpriseUser.UserRole.SUPER_ADMIN
                }
                for role in EnterpriseUser.UserRole.choices
            ]
        }
        
        if domain:
            requirements['domain_authorized'] = AuthorizedDomain.is_domain_authorized(domain)
            if requirements['domain_authorized']:
                try:
                    domain_obj = AuthorizedDomain.objects.get(domain=domain, is_active=True)
                    requirements['company_name'] = domain_obj.company_name
                except AuthorizedDomain.DoesNotExist:
                    pass
        
        return requirements
    
    def check_registration_eligibility(self, email: str) -> Dict[str, Any]:
        """
        Check if email is eligible for registration.
        
        Args:
            email: Corporate email address
            
        Returns:
            Dict containing eligibility status and details
        """
        result = {
            'eligible': False,
            'reasons': []
        }
        
        try:
            # Check email format
            if not email or '@' not in email:
                result['reasons'].append('Invalid email format')
                return result
            
            # Check if user already exists
            if EnterpriseUser.objects.filter(corporate_email=email.lower()).exists():
                result['reasons'].append('User with this email already exists')
                return result
            
            # Check domain authorization
            domain = email.split('@')[1].lower()
            if not AuthorizedDomain.is_domain_authorized(domain):
                result['reasons'].append(f'Domain {domain} is not authorized for registration')
                return result
            
            # All checks passed
            result['eligible'] = True
            result['domain'] = domain
            
            # Add company info if available
            try:
                domain_obj = AuthorizedDomain.objects.get(domain=domain, is_active=True)
                result['company_name'] = domain_obj.company_name
            except AuthorizedDomain.DoesNotExist:
                pass
            
        except Exception as e:
            logger.error(f"Registration eligibility check error for {email}: {str(e)}")
            result['reasons'].append('Unable to check eligibility')
        
        return result
    
    def get_user_registration_status(self, email: str) -> Dict[str, Any]:
        """
        Get detailed registration status for user.
        
        Args:
            email: Corporate email address
            
        Returns:
            Dict containing detailed registration status
        """
        try:
            user = EnterpriseUser.objects.get(corporate_email=email.lower())
            
            return {
                'exists': True,
                'email_verified': user.email_verified,
                'is_active': user.is_active,
                'is_2fa_enabled': user.is_2fa_enabled,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'registration_complete': user.email_verified and user.is_active,
                'next_step': self._determine_next_step(user)
            }
            
        except EnterpriseUser.DoesNotExist:
            return {
                'exists': False,
                'next_step': 'register'
            }
        except Exception as e:
            logger.error(f"Registration status error for {email}: {str(e)}")
            return {
                'exists': False,
                'error': 'Unable to check status'
            }
    
    def _determine_next_step(self, user: EnterpriseUser) -> str:
        """
        Determine the next step in registration process for user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            str: Next step identifier
        """
        if not user.email_verified:
            return 'verify_email'
        elif not user.is_active:
            return 'contact_support'
        elif not user.is_2fa_enabled:
            return 'setup_2fa_optional'
        else:
            return 'registration_complete'
    
    def resend_verification_email(self, user: EnterpriseUser) -> bool:
        """
        Resend verification email with new token.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            if user.email_verified:
                raise ValueError("Email is already verified")
            
            # Generate new verification token
            user.generate_email_verification_token()
            
            # Send verification email
            return self.send_verification_email(user)
            
        except Exception as e:
            logger.error(f"Resend verification error for {user.corporate_email}: {str(e)}")
            return False
    
    def cleanup_incomplete_registrations(self, days_old: int = 7) -> int:
        """
        Clean up incomplete registrations older than specified days.
        
        Args:
            days_old: Number of days to consider registrations stale
            
        Returns:
            int: Number of registrations cleaned up
        """
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days_old)
            
            # Find unverified users older than cutoff
            stale_users = EnterpriseUser.objects.filter(
                email_verified=False,
                is_active=False,
                created_at__lt=cutoff_date
            )
            
            count = stale_users.count()
            stale_users.delete()
            
            logger.info(f"Cleaned up {count} incomplete registrations older than {days_old} days")
            
            return count
            
        except Exception as e:
            logger.error(f"Registration cleanup error: {str(e)}")
            return 0
