from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
import time
import logging


class AnonymousWebSocketMiddleware(BaseMiddleware):
    
    async def __call__(self, scope, receive, send):
        scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)


class ConnectionTrackingMiddleware(BaseMiddleware):
    
    active_connections = set()
    
    async def __call__(self, scope, receive, send):
        connection_id = f"{scope.get('client', ['unknown'])[0]}:{id(scope)}"
        
        self.active_connections.add(connection_id)
        
        try:
            return await super().__call__(scope, receive, send)
        finally:
            self.active_connections.discard(connection_id)
    
    @classmethod
    def get_active_count(cls):
        return len(cls.active_connections)


class ConnectionThrottleMiddleware(BaseMiddleware):
    MAX_CONNECTIONS_PER_IP = 50  
    CONNECTION_WINDOW = 300      
    RATE_LIMIT_WINDOW = 60       
    MAX_CONNECTIONS_PER_MINUTE = 100  
    
    async def __call__(self, scope, receive, send):
        client_ip = self.get_client_ip(scope)
        logger = logging.getLogger('django')
        logger.info(f"WebSocket connection from {client_ip} - throttling bypassed for collaborative access")
        
        return await super().__call__(scope, receive, send)
    
    def get_client_ip(self, scope):
        client = scope.get('client', ['unknown', 0])
        return client[0] if client else 'unknown'
    
    async def check_rate_limit(self, client_ip):
        cache_key = f"ws_rate_limit:{client_ip}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= self.MAX_CONNECTIONS_PER_MINUTE:
            return False
        
        cache.set(cache_key, current_count + 1, self.RATE_LIMIT_WINDOW)
        return True
    
    async def check_concurrent_limit(self, client_ip):
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        
        return current_count < self.MAX_CONNECTIONS_PER_IP
    
    async def track_connection(self, client_ip):
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, self.CONNECTION_WINDOW)
    
    async def untrack_connection(self, client_ip):
        cache_key = f"ws_concurrent:{client_ip}"
        current_count = cache.get(cache_key, 0)
        if current_count > 0:
            cache.set(cache_key, current_count - 1, self.CONNECTION_WINDOW)
    
    async def reject_connection(self, send, reason):
        await send({
            'type': 'websocket.close',
            'code': 4003,
            'reason': reason.encode('utf-8')
        })
