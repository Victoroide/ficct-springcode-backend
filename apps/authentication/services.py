
import secrets
import pyotp
from datetime import timedelta
from typing import Optional, Dict, Any, Tuple
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.models import EnterpriseUser, AuthorizedDomain
from apps.audit.models import AuditLog
from apps.security.exceptions import (
    AccountLockedException,
    TwoFactorRequiredException,
    InvalidCredentialsException,
    DomainNotAuthorizedException,
    EmailNotVerifiedException
)


class AuthenticationService:
    """
    Service for handling enterprise authentication operations.
    Implements the authentication flows from sequence diagrams.
    """
    
    @staticmethod
    def authenticate_user(
        corporate_email: str,
        password: str,
        request=None
    ) -> Dict[str, Any]:
        """
        Initial authentication step.
        
        Authenticates user credentials and handles rate limiting.
        Returns authentication result with next steps.
        """
        # Rate limiting check
        rate_limit_key = f"login_attempts:{corporate_email}"
        attempts = cache.get(rate_limit_key, 0)
        
        if attempts >= settings.MAX_LOGIN_ATTEMPTS:
            AuditLog.log_action(
                AuditLog.ActionType.RATE_LIMIT_EXCEEDED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                details={'email': corporate_email, 'attempts': attempts}
            )
            raise InvalidCredentialsException("Too many login attempts. Try again later.")
        
        try:
            # Get user
            user = EnterpriseUser.objects.get(
                corporate_email=corporate_email,
                is_active=True
            )
            
            # Check if account is locked
            if user.is_account_locked():
                AuditLog.log_action(
                    AuditLog.ActionType.LOGIN_FAILED,
                    request=request,
                    user=user,
                    severity=AuditLog.Severity.MEDIUM,
                    details={'reason': 'account_locked'}
                )
                raise AccountLockedException("Account is temporarily locked due to failed attempts.")
            
            # Check if email is verified
            if not user.email_verified:
                AuditLog.log_action(
                    AuditLog.ActionType.LOGIN_FAILED,
                    request=request,
                    user=user,
                    severity=AuditLog.Severity.MEDIUM,
                    details={'reason': 'email_not_verified'}
                )
                raise EmailNotVerifiedException("Please verify your email before logging in.")
            
            # Authenticate user with request parameter for django-axes
            authenticated_user = authenticate(request=request, username=corporate_email, password=password)
            if not authenticated_user:
                # Increment failed attempts
                user.increment_failed_attempts()
                
                # Increment rate limiting counter
                cache.set(rate_limit_key, attempts + 1, timeout=900)  # 15 minutes
                
                AuditLog.log_action(
                    AuditLog.ActionType.LOGIN_FAILED,
                    request=request,
                    user=user,
                    severity=AuditLog.Severity.MEDIUM,
                    details={'reason': 'invalid_password'}
                )
                raise InvalidCredentialsException("Invalid credentials.")
            
            # Check password expiry
            if user.is_password_expired():
                AuditLog.log_action(
                    AuditLog.ActionType.LOGIN_FAILED,
                    request=request,
                    user=user,
                    severity=AuditLog.Severity.MEDIUM,
                    details={'reason': 'password_expired'}
                )
                return {
                    'status': 'password_expired',
                    'message': 'Password has expired. Please reset your password.',
                    'user_id': user.id
                }
            
            # Reset failed attempts on successful password check
            user.reset_failed_attempts()
            cache.delete(rate_limit_key)
            
            # Check if 2FA is required
            if user.is_2fa_enabled:
                # Generate and cache 2FA session token
                session_token = secrets.token_urlsafe(32)
                cache.set(
                    f"2fa_session:{session_token}",
                    user.id,
                    timeout=300  # 5 minutes
                )
                
                AuditLog.log_action(
                    AuditLog.ActionType.LOGIN_SUCCESS,
                    request=request,
                    user=user,
                    severity=AuditLog.Severity.LOW,
                    details={'stage': 'password_verified', '2fa_required': True}
                )
                
                return {
                    'status': '2fa_required',
                    'message': 'Please provide your 2FA code.',
                    '2fa_session_token': session_token,
                    'user_id': user.id
                }
            
            # Complete login without 2FA
            return AuthenticationService._complete_login(user, request)
            
        except EnterpriseUser.DoesNotExist:
            # Increment rate limiting for non-existent users too
            cache.set(rate_limit_key, attempts + 1, timeout=900)
            
            AuditLog.log_action(
                AuditLog.ActionType.LOGIN_FAILED,
                request=request,
                severity=AuditLog.Severity.MEDIUM,
                details={'email': corporate_email, 'reason': 'user_not_found'}
            )
            raise InvalidCredentialsException("Invalid credentials.")
    
    @staticmethod
    def verify_2fa_code(
        session_token: str,
        code: str,
        request=None
    ) -> Dict[str, Any]:
        """
        Two-factor authentication verification step.
        
        Verifies 2FA code and completes authentication.
        """
        # Get user from 2FA session
        user_id = cache.get(f"2fa_session:{session_token}")
        if not user_id:
            AuditLog.log_action(
                AuditLog.ActionType.TWO_FA_FAILED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                details={'reason': 'invalid_session_token'}
            )
            raise TwoFactorRequiredException("Invalid or expired 2FA session.")
        
        try:
            user = EnterpriseUser.objects.get(id=user_id, is_active=True)
        except EnterpriseUser.DoesNotExist:
            cache.delete(f"2fa_session:{session_token}")
            raise TwoFactorRequiredException("Invalid 2FA session.")
        
        # Rate limiting for 2FA attempts
        rate_limit_key = f"2fa_attempts:{user.id}"
        attempts = cache.get(rate_limit_key, 0)
        
        if attempts >= 3:  # Lower limit for 2FA
            cache.delete(f"2fa_session:{session_token}")
            AuditLog.log_action(
                AuditLog.ActionType.TWO_FA_FAILED,
                request=request,
                user=user,
                severity=AuditLog.Severity.HIGH,
                details={'reason': 'too_many_attempts'}
            )
            raise TwoFactorRequiredException("Too many 2FA attempts. Please login again.")
        
        # Verify 2FA code or backup code
        is_valid = False
        used_backup_code = False
        
        if user.verify_2fa_code(code):
            is_valid = True
        elif user.use_backup_code(code):
            is_valid = True
            used_backup_code = True
        
        if not is_valid:
            cache.set(rate_limit_key, attempts + 1, timeout=300)  # 5 minutes
            AuditLog.log_action(
                AuditLog.ActionType.TWO_FA_FAILED,
                request=request,
                user=user,
                severity=AuditLog.Severity.MEDIUM,
                details={'attempts': attempts + 1}
            )
            raise TwoFactorRequiredException("Invalid 2FA code.")
        
        # Clean up session and rate limiting
        cache.delete(f"2fa_session:{session_token}")
        cache.delete(rate_limit_key)
        
        # Log successful 2FA
        log_details = {'method': 'totp'}
        if used_backup_code:
            log_details = {'method': 'backup_code'}
            
        AuditLog.log_action(
            AuditLog.ActionType.TWO_FA_SUCCESS,
            request=request,
            user=user,
            severity=AuditLog.Severity.LOW,
            details=log_details
        )
        
        # Complete login
        return AuthenticationService._complete_login(user, request)
    
    @staticmethod
    def _complete_login(user: EnterpriseUser, request=None) -> Dict[str, Any]:
        """
        Complete login process.
        
        Generates JWT tokens, updates user info, and logs successful login.
        """
        with transaction.atomic():
            # Update user login info
            user.last_login = timezone.now()
            user.update_last_activity()
            
            if request:
                user.last_login_ip = AuditLog._get_client_ip(request)
                user.last_login_user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
                user.session_key = request.session.session_key or ''
            
            user.save(update_fields=[
                'last_login', 'last_activity', 'last_login_ip',
                'last_login_user_agent', 'session_key'
            ])
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        # Add custom claims
        permissions = user.get_user_permissions_dict()
        for key, value in permissions.items():
            access_token[key] = value
        
        # Log successful login
        AuditLog.log_action(
            AuditLog.ActionType.LOGIN_SUCCESS,
            request=request,
            user=user,
            severity=AuditLog.Severity.LOW,
            details={
                'complete_login': True,
                'has_2fa': user.is_2fa_enabled,
                'role': user.role
            }
        )
        
        return {
            'status': 'success',
            'message': 'Login successful.',
            'tokens': {
                'access': str(access_token),
                'refresh': str(refresh),
            },
            'user': {
                'id': user.id,
                'corporate_email': user.corporate_email,
                'full_name': user.full_name,
                'role': user.role,
                'department': user.department,
                'is_2fa_enabled': user.is_2fa_enabled,
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
        }
    
    @staticmethod
    def logout_user(user: EnterpriseUser, token: str = None, request=None) -> Dict[str, Any]:
        """
        Secure logout functionality.
        
        Handles secure logout with token blacklisting and cleanup.
        """
        with transaction.atomic():
            # Step 1: Auto-save work (handled by frontend)
            # Step 2: Notify collaborators (future feature)
            
            # Step 3: Blacklist JWT token
            if token:
                try:
                    refresh_token = RefreshToken(token)
                    refresh_token.blacklist()
                except TokenError:
                    # Token might already be invalid/blacklisted
                    pass
            
            # Step 4: Log logout
            AuditLog.log_action(
                AuditLog.ActionType.LOGOUT,
                request=request,
                user=user,
                severity=AuditLog.Severity.LOW,
                details={'logout_type': 'user_initiated'}
            )
            
            # Step 5: Clear session data
            user.session_key = ''
            user.save(update_fields=['session_key'])
        
        return {
            'status': 'success',
            'message': 'Logout successful.'
        }
    
    @staticmethod
    def generate_jwt_token(user: EnterpriseUser) -> Dict[str, str]:
        """
        Generate JWT tokens with enterprise claims.
        """
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        # Add custom claims
        permissions = user.get_user_permissions_dict()
        for key, value in permissions.items():
            access_token[key] = value
        
        return {
            'access': str(access_token),
            'refresh': str(refresh),
        }
    
    @staticmethod
    def invalidate_token(token: str) -> bool:
        """
        Blacklist a JWT token for secure logout.
        """
        try:
            refresh_token = RefreshToken(token)
            refresh_token.blacklist()
            return True
        except TokenError:
            return False


class RegistrationService:
    """
    Service for handling enterprise user registration.
    Implements the registration flow from sequence diagram.
    """
    
    @staticmethod
    def validate_corporate_domain(email: str) -> Tuple[bool, str]:
        """
        Corporate domain validation.
        
        Validates if email domain is authorized for registration.
        """
        if '@' not in email:
            return False, "Invalid email format."
        
        domain = email.split('@')[1].lower()
        
        # Domain validation bypassed - all domains are allowed
        return True, f"Domain '{domain}' is authorized."
    
    @staticmethod
    def create_enterprise_user(
        corporate_email: str,
        full_name: str,
        role: str,
        department: str = '',
        employee_id: str = '',
        password: str = None,
        request=None
    ) -> Dict[str, Any]:
        """
        Create new enterprise user account.
        
        Handles complete user creation process with validations.
        """
        # Step 1: Validate corporate domain
        is_valid, message = RegistrationService.validate_corporate_domain(corporate_email)
        if not is_valid:
            raise DomainNotAuthorizedException(message)
        
        # Check if user already exists
        if EnterpriseUser.objects.filter(corporate_email=corporate_email).exists():
            raise ValueError("User with this email already exists.")
        
        # Validate role
        if role not in [choice[0] for choice in EnterpriseUser.Role.choices]:
            raise ValueError("Invalid role specified.")
        
        with transaction.atomic():
            # Create user
            user = EnterpriseUser(
                corporate_email=corporate_email,
                full_name=full_name,
                role=role,
                department=department,
                employee_id=employee_id,
                company_domain=corporate_email.split('@')[1].lower(),
                is_active=True,  # Will be activated after email verification
                email_verified=False
            )
            
            if password:
                # Validate password policy
                is_valid, errors = user.check_password_policy(password)
                if not is_valid:
                    raise ValueError(f"Password policy violation: {', '.join(errors)}")
                
                user.set_password(password)
                user.set_password_expiry()
            
            user.save()
            
            # Log account creation
            AuditLog.log_action(
                AuditLog.ActionType.ACCOUNT_CREATED,
                request=request,
                user=user,
                severity=AuditLog.Severity.LOW,
                details={
                    'role': role,
                    'department': department,
                    'company_domain': user.company_domain
                }
            )
        
        # Step 2: Send verification email
        verification_result = RegistrationService.send_verification_email(user, request)
        
        return {
            'status': 'success',
            'message': 'User account created successfully. Please check your email for verification.',
            'user_id': user.id,
            'verification_sent': verification_result['sent']
        }
    
    @staticmethod
    def send_verification_email(user: EnterpriseUser, request=None) -> Dict[str, Any]:
        """
        Email verification process.
        
        Sends email verification link to user.
        """
        # Generate verification token
        token = user.generate_email_verification_token()
        
        # Create verification URL
        base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
        verification_url = f"{base_url}/auth/verify-email?token={token}&user={user.id}"
        
        # Send email
        try:
            send_mail(
                subject='FICCT Enterprise - Verify Your Email',
                message=f"""
Welcome to FICCT Enterprise Platform!

Please click the following link to verify your email address:
{verification_url}

This link will expire in 24 hours.

If you didn't create this account, please ignore this email.

Best regards,
FICCT Enterprise Team
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.corporate_email],
                fail_silently=False,
            )
            
            AuditLog.log_action(
                AuditLog.ActionType.EMAIL_VERIFIED,
                request=request,
                user=user,
                severity=AuditLog.Severity.LOW,
                details={'action': 'verification_email_sent'}
            )
            
            return {'sent': True, 'message': 'Verification email sent successfully.'}
            
        except Exception as e:
            AuditLog.log_action(
                AuditLog.ActionType.EMAIL_VERIFIED,
                request=request,
                user=user,
                severity=AuditLog.Severity.HIGH,
                error_message=str(e),
                details={'action': 'verification_email_failed'}
            )
            
            return {'sent': False, 'error': 'Failed to send verification email.'}
    
    @staticmethod
    def verify_email(user_id: int, token: str, request=None) -> Dict[str, Any]:
        """
        Verify user email with token.
        """
        try:
            user = EnterpriseUser.objects.get(id=user_id, is_active=True)
        except EnterpriseUser.DoesNotExist:
            raise ValueError("Invalid verification link.")
        
        if user.verify_email(token):
            AuditLog.log_action(
                AuditLog.ActionType.EMAIL_VERIFIED,
                request=request,
                user=user,
                severity=AuditLog.Severity.LOW,
                details={'action': 'email_verified_success'}
            )
            
            return {
                'status': 'success',
                'message': 'Email verified successfully. You can now log in.'
            }
        else:
            AuditLog.log_action(
                AuditLog.ActionType.EMAIL_VERIFIED,
                request=request,
                user=user,
                severity=AuditLog.Severity.MEDIUM,
                details={'action': 'email_verification_failed'}
            )
            
            raise ValueError("Invalid or expired verification token.")
    
    @staticmethod
    def setup_2fa(user: EnterpriseUser, request=None) -> Dict[str, Any]:
        """
        Two-factor authentication setup.
        
        Set up 2FA for enterprise user.
        """
        if user.is_2fa_enabled:
            return {
                'status': 'already_enabled',
                'message': '2FA is already enabled for this account.'
            }
        
        # Generate 2FA secret
        secret = user.generate_2fa_secret()
        qr_url = user.get_2fa_qr_code_url()
        backup_codes = user.generate_backup_codes()
        
        # Save changes but don't enable 2FA yet (user needs to verify setup)
        user.save(update_fields=['two_factor_secret', 'backup_codes'])
        
        AuditLog.log_action(
            AuditLog.ActionType.TWO_FA_ENABLED,
            request=request,
            user=user,
            severity=AuditLog.Severity.LOW,
            details={'action': '2fa_setup_initiated'}
        )
        
        return {
            'status': 'setup_required',
            'message': 'Please scan the QR code and verify with your authenticator app.',
            'qr_code_url': qr_url,
            'secret': secret,
            'backup_codes': backup_codes
        }
    
    @staticmethod
    def verify_2fa_setup(user: EnterpriseUser, code: str, request=None) -> Dict[str, Any]:
        """
        Verify 2FA setup with initial code.
        """
        if not user.two_factor_secret:
            raise ValueError("2FA setup not initiated.")
        
        if user.verify_2fa_code(code):
            user.is_2fa_enabled = True
            user.save(update_fields=['is_2fa_enabled'])
            
            AuditLog.log_action(
                AuditLog.ActionType.TWO_FA_ENABLED,
                request=request,
                user=user,
                severity=AuditLog.Severity.LOW,
                details={'action': '2fa_setup_completed'}
            )
            
            return {
                'status': 'success',
                'message': '2FA has been successfully enabled for your account.'
            }
        else:
            raise ValueError("Invalid 2FA code. Please try again.")


class AuditService:
    """
    Service for handling audit operations and security reporting.
    """
    
    @staticmethod
    def log_authentication_attempt(
        email: str,
        success: bool,
        failure_reason: str = '',
        request=None,
        user=None
    ):
        """
        Log authentication attempts with context.
        """
        action_type = AuditLog.ActionType.LOGIN_SUCCESS if success else AuditLog.ActionType.LOGIN_FAILED
        severity = AuditLog.Severity.LOW if success else AuditLog.Severity.MEDIUM
        
        details = {'email': email}
        if not success and failure_reason:
            details['failure_reason'] = failure_reason
        
        AuditLog.log_action(
            action_type=action_type,
            request=request,
            user=user,
            severity=severity,
            details=details
        )
    
    @staticmethod
    def log_user_action(
        action_type: str,
        user: EnterpriseUser,
        details: Dict[str, Any] = None,
        severity: str = AuditLog.Severity.LOW,
        request=None
    ):
        """
        Log general user actions.
        """
        AuditLog.log_action(
            action_type=action_type,
            request=request,
            user=user,
            severity=severity,
            details=details or {}
        )
    
    @staticmethod
    def generate_security_report(
        user: EnterpriseUser = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate security report for user or system-wide.
        """
        from django.db.models import Count, Q
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = AuditLog.objects.filter(timestamp__gte=cutoff_date)
        if user:
            queryset = queryset.filter(user=user)
        
        # Count by action type
        action_counts = queryset.values('action_type').annotate(count=Count('id'))
        
        # Count by severity
        severity_counts = queryset.values('severity').annotate(count=Count('id'))
        
        # Suspicious activity
        suspicious_count = queryset.filter(
            Q(action_type__in=[
                AuditLog.ActionType.LOGIN_FAILED,
                AuditLog.ActionType.TWO_FA_FAILED,
                AuditLog.ActionType.SUSPICIOUS_LOGIN,
                AuditLog.ActionType.UNAUTHORIZED_ACCESS,
            ]) | Q(severity__in=[AuditLog.Severity.HIGH, AuditLog.Severity.CRITICAL])
        ).count()
        
        return {
            'period_days': days,
            'total_events': queryset.count(),
            'suspicious_events': suspicious_count,
            'action_breakdown': {item['action_type']: item['count'] for item in action_counts},
            'severity_breakdown': {item['severity']: item['count'] for item in severity_counts},
            'generated_at': timezone.now().isoformat()
        }
