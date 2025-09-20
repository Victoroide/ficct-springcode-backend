"""
Enterprise Authentication ViewSets

REST API endpoints for enterprise authentication flows.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view

from .serializers import (
    LoginRequestSerializer,
    TwoFactorVerifySerializer,
    LoginResponseSerializer,
    LogoutRequestSerializer,
    RegistrationRequestSerializer,
    EmailVerificationSerializer,
    TwoFactorSetupSerializer,
    TwoFactorVerifySetupSerializer,
    UserProfileSerializer,
    PasswordChangeSerializer,
    AuthorizedDomainSerializer,
    AuditLogSerializer,
    SecurityReportSerializer,
)
from .services import AuthenticationService, RegistrationService, AuditService
from apps.security.exceptions import (
    InvalidCredentialsException,
    AccountLockedException,
    TwoFactorRequiredException,
    DomainNotAuthorizedException,
    EmailNotVerifiedException,
)
from apps.audit.models import AuditLog
from apps.accounts.models import AuthorizedDomain

User = get_user_model()


@extend_schema_view(
    login=extend_schema(
        tags=['Authentication'],
        summary="Enterprise Login - Step 1",
        description="Authenticate user credentials and initiate login process",
        request=LoginRequestSerializer,
        responses={200: LoginResponseSerializer}
    ),
    verify_2fa=extend_schema(
        tags=['Authentication'],
        summary="Enterprise Login - Step 2",
        description="Verify 2FA code and complete authentication",
        request=TwoFactorVerifySerializer,
        responses={200: LoginResponseSerializer}
    ),
    logout=extend_schema(
        tags=['Authentication'],
        summary="Secure Logout",
        description="Securely logout user and invalidate tokens",
        request=LogoutRequestSerializer,
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}}
    )
)
class AuthenticationViewSet(GenericViewSet):
    """
    ViewSet for enterprise authentication operations.
    """
    throttle_classes = [AnonRateThrottle]
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'logout':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """
        Enterprise user login.
        
        Validates user credentials and determines next steps (2FA or complete login).
        """
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = AuthenticationService.authenticate_user(
                corporate_email=serializer.validated_data['corporate_email'],
                password=serializer.validated_data['password'],
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except InvalidCredentialsException as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except AccountLockedException as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_423_LOCKED
            )
        except EmailNotVerifiedException as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            # Log unexpected errors
            AuditLog.log_action(
                AuditLog.ActionType.LOGIN_FAILED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                error_message=str(e),
                details={'unexpected_error': True}
            )
            return Response(
                {'status': 'error', 'message': 'An unexpected error occurred.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='verify-2fa')
    def verify_2fa(self, request):
        """
        Two-factor authentication verification.
        
        Verifies 2FA code and completes authentication process.
        """
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = AuthenticationService.verify_2fa_code(
                session_token=serializer.validated_data['session_token'],
                code=serializer.validated_data['code'],
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except TwoFactorRequiredException as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            AuditLog.log_action(
                AuditLog.ActionType.TWO_FA_FAILED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                error_message=str(e),
                details={'unexpected_error': True}
            )
            return Response(
                {'status': 'error', 'message': 'An unexpected error occurred.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        """
        
        Securely logs out user and invalidates tokens.
        """
        serializer = LogoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = AuthenticationService.logout_user(
                user=request.user,
                token=serializer.validated_data.get('refresh_token'),
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            AuditLog.log_action(
                AuditLog.ActionType.LOGOUT,
                request=request,
                user=request.user,
                severity=AuditLog.Severity.MEDIUM,
                error_message=str(e),
                details={'logout_error': True}
            )
            return Response(
                {'status': 'error', 'message': 'Logout completed with warnings.'},
                status=status.HTTP_200_OK
            )


@extend_schema_view(
    register=extend_schema(
        tags=['Authentication'],
        summary="Enterprise User Registration",
        description="Register new enterprise user with corporate email validation",
        request=RegistrationRequestSerializer,
        responses={201: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}}
    ),
    verify_email=extend_schema(
        tags=['Authentication'],
        summary="Email Verification",
        description="Verify corporate email with token from verification email",
        request=EmailVerificationSerializer,
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}}
    ),
    setup_2fa=extend_schema(
        tags=['Authentication'],
        summary="Setup Two-Factor Authentication",
        description="Initialize 2FA setup for enterprise user",
        request=TwoFactorSetupSerializer,
        responses={200: {"type": "object"}}
    ),
    verify_2fa_setup=extend_schema(
        tags=['Authentication'],
        summary="Verify 2FA Setup",
        description="Complete 2FA setup by verifying initial code",
        request=TwoFactorVerifySetupSerializer,
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}}
    )
)
class RegistrationViewSet(GenericViewSet):
    """
    ViewSet for enterprise user registration operations
    """
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    
    def get_permissions(self):
        """
        Setup 2FA actions require authentication.
        """
        if self.action in ['setup_2fa', 'verify_2fa_setup']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """        
        Complete enterprise user registration with domain validation.
        """
        serializer = RegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.create_enterprise_user(
                corporate_email=serializer.validated_data['corporate_email'],
                full_name=serializer.validated_data['full_name'],
                role=serializer.validated_data['role'],
                department=serializer.validated_data.get('department', ''),
                employee_id=serializer.validated_data.get('employee_id', ''),
                password=serializer.validated_data['password'],
                request=request
            )
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except DomainNotAuthorizedException as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            AuditLog.log_action(
                AuditLog.ActionType.ACCOUNT_CREATED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                error_message=str(e),
                details={'registration_error': True, 'email': serializer.validated_data.get('corporate_email')}
            )
            return Response(
                {'status': 'error', 'message': 'Registration failed due to system error.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='verify-email')
    def verify_email(self, request):
        """        
        Verify corporate email address with token.
        """
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.verify_email(
                user_id=serializer.validated_data['user_id'],
                token=serializer.validated_data['token'],
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], url_path='setup-2fa')
    def setup_2fa(self, request):
        """        
        Initialize 2FA setup for authenticated user.
        """
        try:
            result = RegistrationService.setup_2fa(
                user=request.user,
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'status': 'error', 'message': 'Failed to setup 2FA.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='verify-2fa-setup')
    def verify_2fa_setup(self, request):
        """
        Complete 2FA setup by verifying initial code.
        """
        serializer = TwoFactorVerifySetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.verify_2fa_setup(
                user=request.user,
                code=serializer.validated_data['code'],
                request=request
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    profile=extend_schema(
        tags=['Authentication'],
        summary="Get User Profile",
        description="Get authenticated user profile information",
        responses={200: UserProfileSerializer}
    ),
    update_profile=extend_schema(
        tags=['Authentication'],
        summary="Update User Profile",
        description="Update authenticated user profile",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    ),
    change_password=extend_schema(
        tags=['Authentication'],
        summary="Change Password",
        description="Change user password with enterprise policy validation",
        request=PasswordChangeSerializer,
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}, "message": {"type": "string"}}}}
    )
)
class UserProfileViewSet(GenericViewSet):
    """
    ViewSet for user profile management.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get authenticated user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['patch'], url_path='update-profile')
    def update_profile(self, request):
        """Update authenticated user profile."""
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        AuditLog.log_action(
            AuditLog.ActionType.PROFILE_UPDATED,
            request=request,
            user=request.user,
            severity=AuditLog.Severity.LOW,
            details={'updated_fields': list(serializer.validated_data.keys())}
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        """Change user password with enterprise policy validation."""
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Verify current password
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'status': 'error', 'message': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.set_password_expiry()
        user.save()
        
        AuditLog.log_action(
            AuditLog.ActionType.PASSWORD_CHANGE,
            request=request,
            user=user,
            severity=AuditLog.Severity.MEDIUM,
            details={'changed_by_user': True}
        )
        
        return Response(
            {'status': 'success', 'message': 'Password changed successfully.'},
            status=status.HTTP_200_OK
        )


@extend_schema_view(
    authorized_domains=extend_schema(
        tags=['Authentication'],
        summary="Get Authorized Domains",
        description="Get list of authorized corporate domains",
        responses={200: AuthorizedDomainSerializer(many=True)}
    ),
    audit_logs=extend_schema(
        tags=['Authentication'],
        summary="Get User Audit Logs",
        description="Get audit logs for authenticated user",
        responses={200: AuditLogSerializer(many=True)}
    ),
    security_report=extend_schema(
        tags=['Authentication'],
        summary="Get Security Report",
        description="Get security report for authenticated user",
        responses={200: SecurityReportSerializer}
    )
)
class SecurityViewSet(GenericViewSet):
    """
    ViewSet for security-related operations.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @method_decorator(cache_page(300))  # Cache for 5 minutes
    @action(detail=False, methods=['get'], url_path='authorized-domains')
    def authorized_domains(self, request):
        """Get list of authorized corporate domains."""
        domains = AuthorizedDomain.objects.filter(is_active=True)
        serializer = AuthorizedDomainSerializer(domains, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='audit-logs')
    def audit_logs(self, request):
        """Get audit logs for authenticated user."""
        logs = AuditLog.objects.filter(user=request.user)[:50]  # Last 50 entries
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='security-report')
    def security_report(self, request):
        """Get security report for authenticated user."""
        days = int(request.query_params.get('days', 30))
        report = AuditService.generate_security_report(user=request.user, days=days)
        serializer = SecurityReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)
