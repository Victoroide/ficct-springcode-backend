"""
Anonymous WebSocket URL routing for UML Diagram collaboration.

Defines WebSocket URL patterns for anonymous access:
- Diagram collaboration: /ws/diagram/<diagram_id>/
- Diagram chat: /ws/diagram/<diagram_id>/chat/
"""

from django.urls import re_path
from .anonymous_consumers import AnonymousUMLDiagramConsumer, AnonymousDiagramChatConsumer

websocket_urlpatterns = [
    # Anonymous diagram collaboration WebSocket
    re_path(
        r'^ws/diagram/(?P<diagram_id>[\w-]+)/$', 
        AnonymousUMLDiagramConsumer.as_asgi(),
        name='diagram_websocket'
    ),
    
    # Anonymous diagram chat WebSocket
    re_path(
        r'^ws/diagram/(?P<diagram_id>[\w-]+)/chat/$', 
        AnonymousDiagramChatConsumer.as_asgi(),
        name='diagram_chat_websocket'
    ),
]
