"""
Enterprise Exception Handling System.

Professional-grade exception handling with structured responses,
audit logging, and consistent error formatting across all ViewSets.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.exceptions import (
    ValidationError, 
    PermissionDenied, 
    NotFound, 
    MethodNotAllowed,
    APIException
)
import logging

logger = logging.getLogger('enterprise_exceptions')


class EnterpriseAPIException(APIException):
    """Base exception for enterprise API errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'An error occurred processing your request.'
    default_code = 'enterprise_error'


class BusinessLogicException(EnterpriseAPIException):
    """Exception for business logic violations."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Business logic validation failed.'
    default_code = 'business_logic_error'


class ResourceConflictException(EnterpriseAPIException):
    """Exception for resource conflicts."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Resource conflict detected.'
    default_code = 'resource_conflict'


class InsufficientPermissionsException(PermissionDenied):
    """Exception for insufficient permissions."""
    default_detail = 'You do not have permission to perform this action.'
    default_code = 'insufficient_permissions'


def enterprise_exception_handler(exc, context):
    """
    Enterprise-grade exception handler with structured responses.
    
    Provides consistent error formatting, audit logging, and
    detailed error information for debugging and client consumption.
    """

    response = exception_handler(exc, context)
    
    if response is not None:

        request = context.get('request')
        view = context.get('view')

        user_info = None
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user_info = {
                'user_id': str(request.user.id),
                'username': request.user.username
            }

        custom_response_data = {
            'error': True,
            'error_code': getattr(exc, 'default_code', 'unknown_error'),
            'message': _get_error_message(exc, response),
            'status_code': response.status_code,
            'timestamp': _get_iso_timestamp(),
            'request_id': _generate_request_id(request),
            'details': _get_error_details(exc, response)
        }

        if user_info:
            custom_response_data['user_context'] = user_info

        if view:
            custom_response_data['resource'] = view.__class__.__name__

        _log_exception(exc, context, custom_response_data)
        
        response.data = custom_response_data
    
    return response


def _get_error_message(exc, response):
    """Extract appropriate error message from exception."""
    
    if isinstance(exc, ValidationError):

        if isinstance(response.data, dict):

            for field, errors in response.data.items():
                if isinstance(errors, list) and errors:
                    return f"Validation error in {field}: {errors[0]}"
            return "Validation error occurred"
        elif isinstance(response.data, list) and response.data:
            return str(response.data[0])
    
    elif isinstance(exc, DjangoValidationError):

        if hasattr(exc, 'message_dict'):
            messages = []
            for field, errors in exc.message_dict.items():
                messages.extend(errors)
            return "; ".join(messages)
        elif hasattr(exc, 'messages'):
            return "; ".join(exc.messages)
    
    elif isinstance(exc, IntegrityError):
        return "Database integrity constraint violation"
    
    elif isinstance(exc, PermissionDenied):
        return "Access denied - insufficient permissions"
    
    elif isinstance(exc, NotFound):
        return "Resource not found"
    
    elif isinstance(exc, MethodNotAllowed):
        return f"Method {getattr(exc, 'method', 'UNKNOWN')} not allowed"

    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            return str(exc.detail.get('detail', exc.detail))
        return str(exc.detail)
    
    return str(exc)


def _get_error_details(exc, response):
    """Extract detailed error information for debugging."""
    
    details = {}
    
    if isinstance(exc, ValidationError) and response:
        details['validation_errors'] = response.data
    
    elif isinstance(exc, DjangoValidationError):
        if hasattr(exc, 'message_dict'):
            details['field_errors'] = exc.message_dict
        elif hasattr(exc, 'messages'):
            details['messages'] = exc.messages
    
    elif isinstance(exc, IntegrityError):
        details['constraint_violation'] = str(exc)

    details['exception_type'] = exc.__class__.__name__
    
    return details


def _get_iso_timestamp():
    """Get current timestamp in ISO format."""
    from django.utils import timezone
    return timezone.now().isoformat()


def _generate_request_id(request):
    """Generate or extract request ID for tracing."""
    if request:

        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if request_id:
            return request_id

    import uuid
    return str(uuid.uuid4())[:8]


def _log_exception(exc, context, error_data):
    """Log exception details for monitoring and debugging."""
    
    request = context.get('request')
    view = context.get('view')
    
    log_data = {
        'exception_type': exc.__class__.__name__,
        'error_code': error_data.get('error_code'),
        'status_code': error_data.get('status_code'),
        'request_id': error_data.get('request_id'),
        'message': error_data.get('message'),
    }

    if request:
        log_data.update({
            'method': request.method,
            'path': request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': _get_client_ip(request)
        })

    if view:
        log_data['view'] = view.__class__.__name__
        log_data['action'] = getattr(view, 'action', 'unknown')

    if error_data.get('status_code', 500) >= 500:
        logger.error(f"Server error: {exc}", extra=log_data, exc_info=True)
    elif error_data.get('status_code', 400) >= 400:
        logger.warning(f"Client error: {exc}", extra=log_data)
    else:
        logger.info(f"Exception handled: {exc}", extra=log_data)


def _get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or '127.0.0.1'


class EnterpriseExceptionHandler:
    """
    Enterprise exception handler class for ViewSet integration.
    
    Provides structured exception handling methods for ViewSets
    to maintain consistent error responses and audit logging.
    """
    
    @staticmethod
    def handle_exception(exc, context=None):
        """
        Handle exceptions with enterprise standards.
        
        Args:
            exc: Exception instance
            context: Request context
            
        Returns:
            Response with structured error data
        """
        return enterprise_exception_handler(exc, context)
    
    @staticmethod
    def handle_validation_error(exc, context=None):
        """Handle validation errors specifically."""
        if not isinstance(exc, (ValidationError, DjangoValidationError)):
            exc = ValidationError(str(exc))
        return enterprise_exception_handler(exc, context)
    
    @staticmethod
    def handle_business_logic_error(message, context=None):
        """Handle business logic violations."""
        exc = BusinessLogicException(detail=message)
        return enterprise_exception_handler(exc, context)
    
    @staticmethod
    def handle_resource_conflict(message, context=None):
        """Handle resource conflicts."""
        exc = ResourceConflictException(detail=message)
        return enterprise_exception_handler(exc, context)
    
    @staticmethod
    def handle_permission_error(message=None, context=None):
        """Handle permission errors."""
        exc = InsufficientPermissionsException(detail=message)
        return enterprise_exception_handler(exc, context)
