"""
WebSocket URL routing for real-time collaboration.
"""

from django.urls import re_path
from .consumers import UMLCollaborationConsumer, CursorTrackingConsumer

websocket_urlpatterns = [
    re_path(r'ws/collaboration/(?P<project_id>[^/]+)/(?P<diagram_id>[^/]+)/$', UMLCollaborationConsumer.as_asgi()),
    re_path(r'ws/cursor/(?P<project_id>[^/]+)/(?P<diagram_id>[^/]+)/$', CursorTrackingConsumer.as_asgi()),
]
