"""
Collaboration app configuration for real-time UML editing.
"""

from django.apps import AppConfig


class CollaborationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.collaboration'
    verbose_name = 'UML Collaboration'
    
    def ready(self):
        """
        Initialize collaboration services on app startup.
        """
        try:
            from . import signals  # noqa
        except ImportError:
            pass
