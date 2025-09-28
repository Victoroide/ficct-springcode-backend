from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.websockets'
    verbose_name = 'WebSocket Collaboration'
    
    def ready(self):
        pass
