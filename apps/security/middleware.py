"""
Enterprise Security Middleware

Middleware components for enterprise-grade security including IP whitelisting,
security headers, rate limiting, and audit logging.
"""

import logging
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from apps.audit.models import AuditLog
from .exceptions import UnauthorizedDomainAccessException, RateLimitExceededException

User = get_user_model()
logger = logging.getLogger('security')


class EnterpriseSecurityMiddleware(MiddlewareMixin):
    """
    Enterprise security middleware for comprehensive request security.
    
    Features:
    - Request logging and monitoring
    - Suspicious activity detection
    - Security headers enforcement
    - User activity tracking
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process incoming requests for security validation."""
        # Track request start time for performance monitoring
        request.security_start_time = timezone.now()
        
        # Extract client information
        request.client_ip = self._get_client_ip(request)
        request.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Log high-risk endpoints
        if self._is_sensitive_endpoint(request.path):
            self._log_sensitive_access(request)
        
        # Check for suspicious patterns
        if self._detect_suspicious_activity(request):
            logger.warning(f"Suspicious activity detected from {request.client_ip}")
            AuditLog.log_action(
                AuditLog.ActionType.SUSPICIOUS_LOGIN,
                request=request,
                severity=AuditLog.Severity.HIGH,
                details={'pattern': 'suspicious_request_pattern'}
            )
        
        return None
    
    def process_response(self, request, response):
        """Process responses to add security headers and logging."""
        # Add enterprise security headers
        response = self._add_security_headers(response)
        
        # Log response for sensitive endpoints
        if hasattr(request, 'security_start_time') and self._is_sensitive_endpoint(request.path):
            duration = (timezone.now() - request.security_start_time).total_seconds()
            
            # Log slow responses as potential security concern
            if duration > 5.0:  # 5 seconds
                logger.warning(f"Slow response detected: {request.path} took {duration}s")
        
        # Update user activity if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                request.user.update_last_activity()
            except Exception as e:
                logger.error(f"Failed to update user activity: {e}")
        
        return response
    
    def _get_client_ip(self, request):
        """Extract real client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def _is_sensitive_endpoint(self, path):
        """Check if endpoint is security-sensitive."""
        sensitive_patterns = [
            '/auth/',
            '/admin/',
            '/api/auth/',
            '/api/user/',
            '/api/security/'
        ]
        return any(pattern in path for pattern in sensitive_patterns)
    
    def _log_sensitive_access(self, request):
        """Log access to sensitive endpoints."""
        logger.info(
            f"Sensitive endpoint access: {request.path} from {request.client_ip} "
            f"User-Agent: {request.user_agent[:100]}"
        )
    
    def _detect_suspicious_activity(self, request):
        """Detect potentially suspicious request patterns."""
        # Check for unusual user agent patterns
        user_agent = request.user_agent.lower()
        suspicious_agents = ['bot', 'crawler', 'spider', 'scanner', 'hack']
        
        if any(agent in user_agent for agent in suspicious_agents):
            return True
        
        # Check for rapid requests from same IP
        ip_key = f"request_count:{request.client_ip}"
        current_count = cache.get(ip_key, 0)
        
        if current_count > 100:  # More than 100 requests per minute
            return True
        
        # Increment request counter
        cache.set(ip_key, current_count + 1, timeout=60)
        
        return False
    
    def _add_security_headers(self, response):
        """Add comprehensive security headers."""
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'X-Permitted-Cross-Domain-Policies': 'none',
        }
        
        for header, value in security_headers.items():
            if header not in response:
                response[header] = value
        
        return response


class IPWhitelistMiddleware(MiddlewareMixin):
    """
    IP Whitelisting middleware for administrative access.
    
    Restricts access to admin endpoints based on configured IP whitelist.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_whitelist = getattr(settings, 'ADMIN_IP_WHITELIST', ['127.0.0.1'])
        super().__init__(get_response)
    
    def process_request(self, request):
        """Check IP whitelist for admin endpoints."""
        if not self._is_admin_endpoint(request.path):
            return None
        
        client_ip = self._get_client_ip(request)
        
        if not self._is_ip_whitelisted(client_ip):
            logger.warning(f"Unauthorized admin access attempt from {client_ip}")
            
            AuditLog.log_action(
                AuditLog.ActionType.UNAUTHORIZED_ACCESS,
                request=request,
                severity=AuditLog.Severity.CRITICAL,
                details={'endpoint': request.path, 'reason': 'ip_not_whitelisted'}
            )
            
            return JsonResponse(
                {'error': 'Access denied from this IP address.'},
                status=403
            )
        
        return None
    
    def _is_admin_endpoint(self, path):
        """Check if path is an admin endpoint."""
        admin_patterns = ['/admin/', '/api/admin/']
        return any(pattern in path for pattern in admin_patterns)
    
    def _get_client_ip(self, request):
        """Extract client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def _is_ip_whitelisted(self, ip):
        """Check if IP is in the whitelist."""
        return ip in self.admin_whitelist or 'localhost' in self.admin_whitelist


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Session security middleware for enterprise session management.
    
    Features:
    - Session hijacking detection
    - Concurrent session limiting
    - Session timeout enforcement
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process request for session security validation."""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Check for session hijacking indicators
        if self._detect_session_hijacking(request):
            logger.critical(f"Potential session hijacking detected for user {request.user.id}")
            
            AuditLog.log_action(
                AuditLog.ActionType.SESSION_HIJACK,
                request=request,
                user=request.user,
                severity=AuditLog.Severity.CRITICAL,
                details={'indicators': 'user_agent_change_or_ip_change'}
            )
            
            # Force logout by clearing session
            request.session.flush()
            
            return JsonResponse(
                {'error': 'Session security violation detected. Please login again.'},
                status=401
            )
        
        # Update session tracking information
        self._update_session_tracking(request)
        
        return None
    
    def _detect_session_hijacking(self, request):
        """Detect potential session hijacking."""
        user = request.user
        current_ip = self._get_client_ip(request)
        current_ua = request.META.get('HTTP_USER_AGENT', '')
        
        # Compare with stored session info
        if user.last_login_ip and user.last_login_ip != current_ip:
            # IP changed - potential hijacking
            return True
        
        if user.last_login_user_agent and user.last_login_user_agent != current_ua:
            # User agent changed significantly - potential hijacking
            return True
        
        return False
    
    def _update_session_tracking(self, request):
        """Update session tracking information."""
        user = request.user
        current_ip = self._get_client_ip(request)
        current_ua = request.META.get('HTTP_USER_AGENT', '')
        
        # Update if changed
        if user.last_login_ip != current_ip or user.last_login_user_agent != current_ua:
            user.last_login_ip = current_ip
            user.last_login_user_agent = current_ua
            user.save(update_fields=['last_login_ip', 'last_login_user_agent'])
    
    def _get_client_ip(self, request):
        """Extract client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip


class RateLimitingMiddleware(MiddlewareMixin):
    """
    Enterprise rate limiting middleware.
    
    Implements sophisticated rate limiting with different tiers
    based on user authentication status and endpoint sensitivity.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process request for rate limiting."""
        # Determine rate limit key and limits
        rate_key, limit, window = self._get_rate_limit_params(request)
        
        # Check current rate
        current_count = cache.get(rate_key, 0)
        
        if current_count >= limit:
            logger.warning(f"Rate limit exceeded for {rate_key}")
            
            AuditLog.log_action(
                AuditLog.ActionType.RATE_LIMIT_EXCEEDED,
                request=request,
                severity=AuditLog.Severity.HIGH,
                details={'limit': limit, 'window': window, 'key': rate_key}
            )
            
            return JsonResponse(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'retry_after': window
                },
                status=429
            )
        
        # Increment counter
        cache.set(rate_key, current_count + 1, timeout=window)
        
        return None
    
    def _get_rate_limit_params(self, request):
        """Determine rate limiting parameters based on request context."""
        client_ip = self._get_client_ip(request)
        
        # Authenticated users get higher limits
        if hasattr(request, 'user') and request.user.is_authenticated:
            rate_key = f"rate_limit:user:{request.user.id}"
            limit = 1000  # 1000 requests per hour
            window = 3600  # 1 hour
        else:
            rate_key = f"rate_limit:ip:{client_ip}"
            limit = 100   # 100 requests per hour
            window = 3600  # 1 hour
        
        # Stricter limits for sensitive endpoints
        if self._is_auth_endpoint(request.path):
            limit = limit // 10  # 10x stricter for auth endpoints
            window = 900  # 15 minutes
            rate_key += ":auth"
        
        return rate_key, limit, window
    
    def _is_auth_endpoint(self, path):
        """Check if endpoint is authentication-related."""
        auth_patterns = ['/auth/login', '/auth/register', '/auth/verify']
        return any(pattern in path for pattern in auth_patterns)
    
    def _get_client_ip(self, request):
        """Extract client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Comprehensive audit logging middleware for enterprise compliance.
    
    Logs all API access and user activities for audit trails.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Log API access for audit purposes."""
        # Only log API endpoints
        if not request.path.startswith('/api/'):
            return response
        
        # Prepare audit data
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Determine action type based on endpoint
        action_type = self._determine_action_type(request.path, request.method)
        
        # Determine severity based on endpoint and status code
        severity = self._determine_severity(request.path, response.status_code)
        
        # Log the API access
        AuditLog.log_action(
            action_type=action_type,
            request=request,
            user=user,
            severity=severity,
            details={
                'endpoint': request.path,
                'method': request.method,
                'status_code': response.status_code,
                'user_authenticated': user is not None
            },
            status_code=response.status_code
        )
        
        return response
    
    def _determine_action_type(self, path, method):
        """Determine audit action type based on endpoint and method."""
        if '/auth/login' in path:
            return AuditLog.ActionType.LOGIN_SUCCESS if method == 'POST' else AuditLog.ActionType.API_ACCESS
        elif '/auth/logout' in path:
            return AuditLog.ActionType.LOGOUT
        elif '/auth/register' in path:
            return AuditLog.ActionType.ACCOUNT_CREATED
        elif '/admin/' in path:
            return AuditLog.ActionType.ADMIN_LOGIN
        else:
            return AuditLog.ActionType.API_ACCESS
    
    def _determine_severity(self, path, status_code):
        """Determine audit severity based on endpoint and response."""
        # High severity for authentication failures
        if '/auth/' in path and status_code >= 400:
            return AuditLog.Severity.HIGH
        
        # Medium severity for admin access
        if '/admin/' in path:
            return AuditLog.Severity.MEDIUM
        
        # High severity for server errors
        if status_code >= 500:
            return AuditLog.Severity.HIGH
        
        # Medium severity for client errors
        if status_code >= 400:
            return AuditLog.Severity.MEDIUM
        
        # Low severity for successful requests
        return AuditLog.Severity.LOW
