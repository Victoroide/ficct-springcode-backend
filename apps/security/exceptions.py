"""
Enterprise Security Exceptions

Custom exceptions for enterprise authentication and security operations.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class EnterpriseSecurityException(APIException):
    """Base exception for all enterprise security-related errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A security error occurred.'
    default_code = 'security_error'


class InvalidCredentialsException(EnterpriseSecurityException):
    """Raised when user provides invalid login credentials."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid credentials provided.'
    default_code = 'invalid_credentials'


class AccountLockedException(EnterpriseSecurityException):
    """Raised when user account is locked due to failed attempts."""
    status_code = status.HTTP_423_LOCKED
    default_detail = 'Account is temporarily locked.'
    default_code = 'account_locked'


class TwoFactorRequiredException(EnterpriseSecurityException):
    """Raised when 2FA verification is required."""
    status_code = status.HTTP_200_OK  # Not an error, just requires additional step
    default_detail = '2FA verification required.'
    default_code = '2fa_required'


class DomainNotAuthorizedException(EnterpriseSecurityException):
    """Raised when email domain is not authorized for registration."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Email domain is not authorized.'
    default_code = 'domain_not_authorized'


class EmailNotVerifiedException(EnterpriseSecurityException):
    """Raised when user tries to login with unverified email."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Email address must be verified before login.'
    default_code = 'email_not_verified'


class PasswordExpiredException(EnterpriseSecurityException):
    """Raised when user password has expired."""
    status_code = status.HTTP_200_OK  # Not an error, requires password reset
    default_detail = 'Password has expired and must be reset.'
    default_code = 'password_expired'


class RateLimitExceededException(EnterpriseSecurityException):
    """Raised when rate limiting threshold is exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Too many requests. Please try again later.'
    default_code = 'rate_limit_exceeded'


class UnauthorizedDomainAccessException(EnterpriseSecurityException):
    """Raised when access is attempted from unauthorized domain/IP."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Access denied from this location.'
    default_code = 'unauthorized_access'


class TokenExpiredException(EnterpriseSecurityException):
    """Raised when authentication token has expired."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication token has expired.'
    default_code = 'token_expired'


class InvalidTokenException(EnterpriseSecurityException):
    """Raised when authentication token is invalid."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid authentication token.'
    default_code = 'invalid_token'


class PermissionDeniedException(EnterpriseSecurityException):
    """Raised when user lacks required permissions."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Insufficient permissions for this operation.'
    default_code = 'permission_denied'


class SuspiciousActivityException(EnterpriseSecurityException):
    """Raised when suspicious activity is detected."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Suspicious activity detected. Access temporarily restricted.'
    default_code = 'suspicious_activity'
