"""
Authentication Serializers Package
"""

from .authentication_serializer import (
    LoginSerializer,
    TwoFactorVerifySerializer,
    LogoutSerializer,
    TokenRefreshSerializer,
)
from .registration_serializer import (
    UserRegistrationSerializer,
    EmailVerificationSerializer,
    Setup2FASerializer,
)
from .user_profile_serializer import UserProfileSerializer, PasswordChangeSerializer

# Enterprise Management Serializers
from .user_management_serializer import (
    UserListSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    PasswordResetSerializer,
    UserSessionSerializer,
    BulkUserUpdateSerializer,
)
from .session_management_serializer import (
    SessionListSerializer,
    SessionDetailSerializer,
    SessionSecurityAnalysisSerializer,
    MarkSuspiciousSerializer,
)
from .audit_management_serializer import (
    AuditLogListSerializer,
    AuditLogDetailSerializer,
    AuditLogStatisticsSerializer,
    SecurityEventSerializer,
    FailedLoginSerializer,
    AuditLogExportSerializer,
    UserActivityTimelineSerializer,
)
from .domain_management_serializer import (
    DomainListSerializer,
    DomainDetailSerializer,
    DomainCreateSerializer,
    DomainUpdateSerializer,
    DomainValidationSerializer,
    DomainStatisticsSerializer,
    DomainUserListSerializer,
    BulkDomainOperationSerializer,
    DomainActivationSerializer,
)

__all__ = [
    # Core Authentication
    'LoginSerializer',
    'TwoFactorVerifySerializer',
    'LogoutSerializer',
    'TokenRefreshSerializer',
    'UserRegistrationSerializer',
    'EmailVerificationSerializer',
    'Setup2FASerializer',
    'UserProfileSerializer',
    'PasswordChangeSerializer',
    
    # User Management
    'UserListSerializer',
    'UserDetailSerializer',
    'UserCreateSerializer',
    'UserUpdateSerializer',
    'PasswordResetSerializer',
    'UserSessionSerializer',
    'BulkUserUpdateSerializer',
    
    # Session Management
    'SessionListSerializer',
    'SessionDetailSerializer',
    'SessionSecurityAnalysisSerializer',
    'MarkSuspiciousSerializer',
    
    # Audit Management
    'AuditLogListSerializer',
    'AuditLogDetailSerializer',
    'AuditLogStatisticsSerializer',
    'SecurityEventSerializer',
    'FailedLoginSerializer',
    'AuditLogExportSerializer',
    'UserActivityTimelineSerializer',
    
    # Domain Management
    'DomainListSerializer',
    'DomainDetailSerializer',
    'DomainCreateSerializer',
    'DomainUpdateSerializer',
    'DomainValidationSerializer',
    'DomainStatisticsSerializer',
    'DomainUserListSerializer',
    'BulkDomainOperationSerializer',
    'DomainActivationSerializer',
]
