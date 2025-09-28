from django.urls import re_path
from .anonymous_consumers import AnonymousUMLDiagramConsumer, AnonymousDiagramChatConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/diagrams/(?P<diagram_id>[\w-]+)/(?P<session_id>[\w-]+)/$',
        AnonymousUMLDiagramConsumer.as_asgi(),
        name='anonymous_diagram_websocket'
    ),
    
    re_path(
        r'^ws/diagram/(?P<diagram_id>[\w-]+)/$',
        AnonymousUMLDiagramConsumer.as_asgi(),
        name='anonymous_diagram_websocket_legacy'
    ),
    
    re_path(
        r'^ws/diagram/(?P<diagram_id>[\w-]+)/chat/$',
        AnonymousDiagramChatConsumer.as_asgi(),
        name='diagram_chat_websocket'
    ),
]
