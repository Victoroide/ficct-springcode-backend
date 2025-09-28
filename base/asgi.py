
"""
ASGI config for UML Diagram Collaborative Platform.

This module contains the ASGI application used by Django's development server
and any production ASGI deployments. It exposes the ASGI callable as a
module-level variable named ``application``.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from apps.websockets.routing import websocket_urlpatterns
from apps.websockets.middleware import AnonymousWebSocketMiddleware, ConnectionThrottleMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        ConnectionThrottleMiddleware(
            AnonymousWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
