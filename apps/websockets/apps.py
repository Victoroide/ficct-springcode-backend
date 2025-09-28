from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    """
    Django app configuration for WebSocket functionality.
    
    This app handles:
    - Real-time UML diagram collaboration
    - WebSocket consumers for diagram editing
    - Chat functionality for collaborative sessions
    - Connection management and user presence
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.websockets'
    verbose_name = 'WebSocket Collaboration'
    
    def ready(self):
        """
        App initialization - set up WebSocket consumers.
        """
        pass
