"""
Registration ViewSet for enterprise user registration and email verification.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework.serializers import ValidationError as DRFValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from apps.accounts.models import AuthorizedDomain
from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.swagger.enterprise_documentation import EnterpriseDocumentation
from ..serializers import (
    UserRegistrationSerializer,
    EmailVerificationSerializer,
    Setup2FASerializer,
)
from ..services import RegistrationService, EmailService, TwoFactorService, AuditService
from typing import Dict, Any
import logging
import traceback

logger = logging.getLogger('authentication')


@extend_schema_view(
    register=extend_schema(
        tags=['Authentication'],
        summary='User Registration',
        description='Register new enterprise user with corporate email validation.',
        examples=[
            OpenApiExample(
                'Registration Request',
                value={
                    'corporate_email': 'jane.smith@ficct-enterprise.com',
                    'password': 'SecurePass123!',
                    'full_name': 'Jane Smith',
                    'role': 'DEVELOPER',
                    'department': 'Engineering'
                },
                request_only=True
            ),
            OpenApiExample(
                'Registration Response',
                value={
                    'success': True,
                    'message': 'Registration successful. Please check your email for verification instructions.',
                    'user_id': 'uuid-here',
                    'corporate_email': 'jane.smith@ficct-enterprise.com',
                    'verification_required': True
                },
                response_only=True
            )
        ]
    ),
    verify_email=extend_schema(
        tags=['Authentication'],
        summary='Email Verification',
        description='Verify user email address with verification token.',
        examples=[
            OpenApiExample(
                'Email Verification Request',
                value={
                    'email': 'jane.smith@ficct-enterprise.com',
                    'verification_token': 'abc123def456'
                },
                request_only=True
            )
        ]
    ),
    setup_2fa=extend_schema(
        tags=['Authentication'],
        summary='Setup 2FA',
        description='Configure two-factor authentication during registration.',
        examples=[
            OpenApiExample(
                '2FA Setup Request',
                value={
                    'email': 'jane.smith@ficct-enterprise.com',
                    'qr_secret': 'JBSWY3DPEHPK3PXP'
                },
                request_only=True
            )
        ]
    )    
)
@method_decorator(never_cache, name='dispatch')
class RegistrationViewSet(EnterpriseViewSetMixin, viewsets.GenericViewSet):
    """
    ViewSet for enterprise user registration operations.
    
    Provides endpoints for:
    - Initial registration (CU3 step 1)
    - Email verification (CU3 step 2)
    - 2FA setup (CU3 step 3)
    - Domain listing
    - Verification resend
    """
    
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def get_client_ip(self, request) -> str:
        """
        Get client IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or '127.0.0.1'
    
    def get_user_agent(self, request) -> str:
        """
        Get user agent from request.
        """
        return request.META.get('HTTP_USER_AGENT', '')
    
    @method_decorator(ratelimit(key='ip', rate='3/hour', method='POST'))
    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request) -> Response:
        """
        Enterprise user registration endpoint (CU3 step 1).
        
        Creates new user account with email verification requirement.
        """
        # Log the incoming registration data for debugging (excluding password)
        debug_data = request.data.copy() if hasattr(request.data, 'copy') else {}
        if 'password' in debug_data:
            debug_data['password'] = '********'
        if 'password_confirm' in debug_data:
            debug_data['password_confirm'] = '********'
        
        logger.debug(f"Registration attempt received: {debug_data}")
        
        # Validate the serializer data
        serializer = UserRegistrationSerializer(data=request.data)
        
        # We want to handle validation errors ourselves rather than using raise_exception=True
        if not serializer.is_valid():
            logger.debug(f"Validation errors: {serializer.errors}")
            return Response({
                'error': True,
                'error_code': 'validation_error',
                'message': _('Registration validation failed'),
                'validation_errors': serializer.errors,
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        
        ip_address = self.get_client_ip(request)
        user_agent = self.get_user_agent(request)
        
        try:
            # Use registration service for business logic
            registration_service = RegistrationService()
            email_service = EmailService()
            audit_service = AuditService()
            
            # Create user account
            user = registration_service.create_enterprise_user(serializer.validated_data)
            logger.info(f"User account created for {user.corporate_email}")
            
            # Send verification email
            verification_sent = email_service.send_verification_email(user)
            logger.info(f"Verification email sent: {verification_sent}")
            
            # Log registration attempt
            audit_service.log_user_action(
                user=user,
                action='USER_REGISTRATION',
                ip_address=ip_address,
                details={
                    'email_sent': verification_sent,
                    'domain': user.company_domain,
                    'role': user.role
                }
            )
            
            response_data = {
                'success': True,
                'message': _('Registration successful. Please check your email for verification instructions.'),
                'user_id': user.id,
                'corporate_email': user.corporate_email,
                'verification_required': True
            }
            
            if not verification_sent:
                response_data['warning'] = _('Registration completed but verification email could not be sent. Please contact support.')
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            # Handle Django core validation errors (convert to serializer errors format)
            logger.error(f"Django validation error: {e}")
            return Response({
                'error': True,
                'error_code': 'validation_error',
                'message': _('Registration validation failed'),
                'validation_errors': {'__all__': list(e.messages) if hasattr(e, 'messages') else [str(e)]},
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except DRFValidationError as e:
            # Handle DRF validation errors with detailed error info
            logger.error(f"DRF validation error: {e}")
            return Response({
                'error': True,
                'error_code': 'validation_error',
                'message': _('Registration validation failed'),
                'validation_errors': e.detail if hasattr(e, 'detail') else {'__all__': [str(e)]},
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            # Log the full exception with traceback for debugging
            logger.error(f"Registration error for {serializer.validated_data.get('corporate_email')}: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            
            # Log failed registration
            AuditService().log_authentication_attempt(
                email=serializer.validated_data.get('corporate_email', ''),
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    'error': str(e),
                    'error_type': e.__class__.__name__,
                    'action': 'registration'
                }
            )
            
            # Determine if we can return more specific error information
            error_code = 'registration_failed'
            error_message = _('Registration failed. Please try again.')
            
            # Handle specific known exceptions with more descriptive messages
            if 'domain' in str(e).lower():
                error_code = 'domain_validation_failed'
                error_message = _('Email domain is not authorized for registration.')
            
            return Response({
                'error': True,
                'error_code': error_code,
                'message': error_message,
                'detail': str(e),  # Include the actual error message for debugging
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @method_decorator(ratelimit(key='ip', rate='10/hour', method='POST'))
    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='verify-email')
    def verify_email(self, request) -> Response:
        """
        Email verification endpoint (CU3 step 2).
        
        Verifies user's email address and activates account.
        """
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        token = serializer.validated_data['verification_token']
        ip_address = self.get_client_ip(request)
        
        try:
            # Activate user account
            user = serializer.activate_user(email, token)
            
            # Log successful verification
            AuditService().log_user_action(
                user=user,
                action='EMAIL_VERIFIED',
                ip_address=ip_address,
                details={'verification_method': 'token'}
            )
            
            return Response({
                'success': True,
                'message': _('Email verified successfully. Your account is now active.'),
                'user_id': user.id,
                'corporate_email': user.corporate_email,
                'next_step': 'setup_2fa' if not user.is_2fa_enabled else 'login'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Email verification error for {email}: {str(e)}")
            
            return Response({
                'error': True,
                'error_code': 'email_verification_failed',
                'message': _('Email verification failed. Please check your verification link.'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @method_decorator(ratelimit(key='ip', rate='5/hour', method='POST'))
    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='setup-2fa')
    def setup_2fa(self, request) -> Response:
        """
        2FA setup endpoint (CU3 step 3).
        
        Sets up TOTP 2FA for the user account.
        """
        serializer = Setup2FASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get user from email or user_id in request
        user_identifier = request.data.get('email') or request.data.get('user_id')
        if not user_identifier:
            return Response({
                'error': True,
                'error_code': 'missing_user_identifier',
                'message': _('User identifier (email or user_id) is required'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user
            if '@' in str(user_identifier):
                from apps.accounts.models import EnterpriseUser
                user = EnterpriseUser.objects.get(corporate_email=user_identifier)
            else:
                from apps.accounts.models import EnterpriseUser
                user = EnterpriseUser.objects.get(id=user_identifier)
            
            # Use 2FA service for setup
            two_factor_service = TwoFactorService()
            
            # Setup 2FA
            result = serializer.enable_2fa(user, serializer.validated_data['qr_secret'])
            
            # Log 2FA setup
            AuditService().log_user_action(
                user=user,
                action='TWO_FA_ENABLED',
                ip_address=self.get_client_ip(request),
                details={'method': 'registration_setup'}
            )
            
            return Response({
                'success': True,
                'message': _('2FA enabled successfully'),
                'backup_codes': result['backup_codes'],
                'warning': _('Please save these backup codes in a secure location'),
                'next_step': 'login'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"2FA setup error: {str(e)}")
            
            return Response({
                'error': True,
                'error_code': 'two_factor_setup_failed',
                'message': _('2FA setup failed. Please try again.'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='domains')
    def get_authorized_domains(self, request) -> Response:
        """
        Get list of authorized corporate domains for registration.
        
        Helps users understand which domains are allowed.
        """
        try:
            domains = AuthorizedDomain.get_active_domains()
            
            domain_list = [
                {
                    'domain': domain.domain,
                    'company_name': domain.company_name,
                    'created_at': domain.created_at.isoformat()
                }
                for domain in domains
            ]
            
            return Response({
                'success': True,
                'authorized_domains': domain_list,
                'count': len(domain_list)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching authorized domains: {str(e)}")
            
            return Response({
                'error': True,
                'error_code': 'domains_fetch_failed',
                'message': _('Could not fetch authorized domains'),
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @method_decorator(ratelimit(key='ip', rate='3/hour', method='POST'))
    @transaction.atomic
    @action(detail=False, methods=['post'], url_path='resend-verification')
    def resend_verification(self, request) -> Response:
        """
        Resend email verification for unverified accounts.
        
        Allows users to request a new verification email.
        """
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['corporate_email']
        
        try:
            # Get user
            user = serializer.get_user(email)
            
            # Generate new verification token
            user.generate_email_verification_token()
            
            # Send verification email
            email_service = EmailService()
            verification_sent = email_service.send_verification_email(user)
            
            # Log resend attempt
            AuditService().log_user_action(
                user=user,
                action='VERIFICATION_RESENT',
                ip_address=self.get_client_ip(request),
                details={'email_sent': verification_sent}
            )
            
            response_data = {
                'success': True,
                'message': _('Verification email sent successfully'),
                'corporate_email': user.corporate_email
            }
            
            if not verification_sent:
                response_data['warning'] = _('Email could not be sent. Please contact support.')
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Resend verification error for {email}: {str(e)}")
            
            return Response({
                'error': True,
                'error_code': 'verification_resend_failed',
                'message': _('Could not resend verification email'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='generate-2fa-qr')
    def generate_2fa_qr(self, request) -> Response:
        """
        Generate 2FA QR code for user setup.
        
        Returns QR code data and secret for TOTP setup.
        """
        email = request.data.get('email')
        if not email:
            return Response({
                'error': True,
                'error_code': 'email_required',
                'message': _('Email is required'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from apps.accounts.models import EnterpriseUser
            user = EnterpriseUser.objects.get(corporate_email=email, email_verified=True)
            
            # Use 2FA service to generate QR data
            two_factor_service = TwoFactorService()
            qr_data = two_factor_service.generate_qr_code_data(user)
            
            return Response({
                'success': True,
                'qr_code_uri': qr_data['qr_uri'],
                'secret_key': qr_data['secret'],
                'manual_entry_key': qr_data['secret'],
                'issuer': 'FICCT Enterprise',
                'account_name': user.corporate_email
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"QR generation error for {email}: {str(e)}")
            
            return Response({
                'error': True,
                'error_code': 'qr_generation_failed',
                'message': _('Could not generate 2FA QR code'),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='validate-domain')
    def validate_domain(self, request) -> Response:
        """
        Validate if an email domain is authorized for registration.
        
        Helper endpoint for frontend validation.
        """
        email = request.data.get('email')
        if not email or '@' not in email:
            return Response({
                'success': False,
                'valid': False,
                'message': _('Invalid email format')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            domain = email.split('@')[1].lower()
            is_authorized = AuthorizedDomain.is_domain_authorized(domain)
            
            response_data = {
                'success': True,
                'valid': is_authorized,
                'domain': domain
            }
            
            if is_authorized:
                # Get company info
                try:
                    domain_obj = AuthorizedDomain.objects.get(domain=domain, is_active=True)
                    response_data['company_name'] = domain_obj.company_name
                except AuthorizedDomain.DoesNotExist:
                    pass
            else:
                response_data['message'] = _('Domain is not authorized for registration')
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Domain validation error for {email}: {str(e)}")
            
            return Response({
                'success': False,
                'valid': False,
                'message': _('Domain validation failed')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='registration-status')
    def check_registration_status(self, request) -> Response:
        """
        Check registration status for an email address.
        
        Helps users understand their current registration state.
        """
        email = request.query_params.get('email')
        if not email:
            return Response({
                'success': False,
                'message': _('Email parameter is required')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from apps.accounts.models import EnterpriseUser
            
            try:
                user = EnterpriseUser.objects.get(corporate_email=email.lower())
                
                status_info = {
                    'success': True,
                    'exists': True,
                    'email_verified': user.email_verified,
                    'is_active': user.is_active,
                    'is_2fa_enabled': user.is_2fa_enabled,
                    'created_at': user.created_at.isoformat(),
                    'next_step': self._get_next_registration_step(user)
                }
                
            except EnterpriseUser.DoesNotExist:
                status_info = {
                    'success': True,
                    'exists': False,
                    'next_step': 'register'
                }
            
            return Response(status_info, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Registration status check error for {email}: {str(e)}")
            
            return Response({
                'success': False,
                'message': _('Could not check registration status')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_next_registration_step(self, user) -> str:
        """
        Determine the next step in the registration process.
        """
        if not user.email_verified:
            return 'verify_email'
        elif not user.is_active:
            return 'contact_support'  # Account exists but not active
        elif not user.is_2fa_enabled:
            return 'setup_2fa'
        else:
            return 'complete'  # Registration complete, can login
