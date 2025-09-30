"""
Middleware for public diagram access.

Handles public access bypassing, rate limiting, and security for
anonymous users accessing public diagrams.
"""

import time
from collections import defaultdict
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from apps.audit.services.audit_service import AuditService


class PublicAccessMiddleware(MiddlewareMixin):
    """
    Middleware for handling public diagram access.
    
    Features:
    - Rate limiting per IP for public endpoints
    - Security headers for public access
    - Logging of anonymous access attempts
    - Anti-spam protection
    """

    _access_log = defaultdict(list)
    _blocked_ips = set()
    
    def process_request(self, request):
        """Process incoming request for public access."""

        if not request.path.startswith('/api/public/'):
            return None
        
        client_ip = self.get_client_ip(request)

        if client_ip in self._blocked_ips:
            return JsonResponse(
                {'error': 'Access blocked due to suspicious activity'},
                status=429
            )

        if not self.check_rate_limit(client_ip, request):
            return JsonResponse(
                {'error': 'Rate limit exceeded'},
                status=429
            )

        self.log_public_access(request, client_ip)
        
        return None
    
    def process_response(self, request, response):
        """Process response for public access."""

        if request.path.startswith('/api/public/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
            response['Access-Control-Max-Age'] = '3600'
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def check_rate_limit(self, ip, request):
        """Check rate limiting for IP."""
        now = time.time()
        window = 60  # 1 minute window

        self._access_log[ip] = [
            timestamp for timestamp in self._access_log[ip]
            if now - timestamp < window
        ]

        if request.method == 'GET':
            limit = 30  # 30 GET requests per minute
        else:
            limit = 10  # 10 POST/PUT requests per minute

        if len(self._access_log[ip]) >= limit:

            if len(self._access_log[ip]) >= limit * 2:
                self._blocked_ips.add(ip)
            return False

        self._access_log[ip].append(now)
        return True
    
    def log_public_access(self, request, ip):
        """Log public access attempt."""
        try:
            AuditService.log_anonymous_action(
                action_type='PUBLIC_API_ACCESS',
                resource_type='API',
                resource_id=request.path,
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'method': request.method,
                    'path': request.path,
                    'query_params': dict(request.GET) if request.GET else {},
                    'content_type': request.META.get('CONTENT_TYPE', ''),
                }
            )
        except Exception:

            pass


class AntiSpamMiddleware(MiddlewareMixin):
    """
    Anti-spam middleware for public endpoints.
    
    Detects and blocks potential spam/bot requests.
    """
    
    SUSPICIOUS_USER_AGENTS = [
        'bot', 'crawler', 'spider', 'scraper', 'automated',
        'python-requests', 'curl', 'wget', 'postman'
    ]
    
    SUSPICIOUS_PATTERNS = [
        'test', 'spam', 'hack', 'exploit', 'inject'
    ]
    
    def process_request(self, request):
        """Check for suspicious activity."""

        if not request.path.startswith('/api/public/'):
            return None

        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()

        if any(browser in user_agent for browser in ['mozilla', 'chrome', 'safari', 'firefox', 'edge']):
            return None

        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if any(suspicious in user_agent for suspicious in self.SUSPICIOUS_USER_AGENTS):
                return JsonResponse(
                    {'error': 'Automated requests not allowed for modifications'},
                    status=403
                )

        if hasattr(request, 'body') and request.body:
            try:
                content = request.body.decode('utf-8').lower()
                if any(pattern in content for pattern in self.SUSPICIOUS_PATTERNS):
                    return JsonResponse(
                        {'error': 'Request content rejected'},
                        status=400
                    )
            except UnicodeDecodeError:
                pass
        
        return None
