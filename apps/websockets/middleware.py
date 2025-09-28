"""
Anonymous WebSocket Middleware for UML Diagram collaboration.

Simple middleware for anonymous WebSocket connections without authentication.
"""

from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
import time


class AnonymousWebSocketMiddleware(BaseMiddleware):
    """
    Anonymous WebSocket middleware that assigns AnonymousUser to all connections.
    No authentication required - all connections are treated as anonymous.
    """
    
    async def __call__(self, scope, receive, send):
        # Always assign AnonymousUser for anonymous access
        scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)


class ConnectionTrackingMiddleware(BaseMiddleware):
    """
    Middleware to track WebSocket connections for monitoring.
    """
    
    active_connections = set()
    
    async def __call__(self, scope, receive, send):
        connection_id = f"{scope.get('client', ['unknown'])[0]}:{id(scope)}"
        
        # Track connection
        self.active_connections.add(connection_id)
        
        try:
            return await super().__call__(scope, receive, send)
        finally:
            # Clean up connection
            self.active_connections.discard(connection_id)
    
    @classmethod
    def get_active_count(cls):
        """Get number of active WebSocket connections."""
        return len(cls.active_connections)


class ConnectionThrottleMiddleware(BaseMiddleware):
    """
    Throttle WebSocket connections to prevent spam and abuse.
    """
    
    # Configuration
    MAX_CONNECTIONS_PER_IP = 5  # Max concurrent connections per IP
    CONNECTION_WINDOW = 300      # 5 minutes window for tracking
    RATE_LIMIT_WINDOW = 60       # 1 minute window for rate limiting
    MAX_CONNECTIONS_PER_MINUTE = 10  # Max new connections per minute per IP
    
    async def __call__(self, scope, receive, send):
        client_ip = self.get_client_ip(scope)
        
        # Check rate limiting (new connections per minute)
        if not await self.check_rate_limit(client_ip):
            await self.reject_connection(send, "Rate limit exceeded. Too many connections.")
            return
        
        # Check concurrent connection limit
        if not await self.check_concurrent_limit(client_ip):
            await self.reject_connection(send, "Connection limit exceeded.")
            return
        
        # Track this connection
        await self.track_connection(client_ip)
        
        try:
            return await super().__call__(scope, receive, send)
        finally:
            # Clean up tracking
            await self.untrack_connection(client_ip)
    
    def get_client_ip(self, scope):
        """Extract client IP from scope."""
        client = scope.get('client', ['unknown', 0])
        return client[0] if client else 'unknown'
    
    async def check_rate_limit(self, client_ip):
        """Check if client IP is within rate limits for new connections."""
        cache_key = f"ws_rate_limit:{client_ip}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= self.MAX_CONNECTIONS_PER_MINUTE:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, self.RATE_LIMIT_WINDOW)
        return True
    
    async def check_concurrent_limit(self, client_ip):
        """Check if client IP has too many concurrent connections."""
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        
        return current_count < self.MAX_CONNECTIONS_PER_IP
    
    async def track_connection(self, client_ip):
        """Track a new connection."""
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, self.CONNECTION_WINDOW)
    
    async def untrack_connection(self, client_ip):
        """Untrack a connection when it closes."""
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        if current_count > 0:
            cache.set(cache_key, current_count - 1, self.CONNECTION_WINDOW)
    
    async def reject_connection(self, send, reason):
        """Reject WebSocket connection with reason."""
        await send({
            'type': 'websocket.close',
            'code': 4003,  # Policy violation
            'reason': reason.encode('utf-8')
        })
