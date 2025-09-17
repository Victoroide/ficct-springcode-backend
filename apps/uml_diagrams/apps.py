"""
UML Diagrams app configuration for enterprise diagram management.
"""

from django.apps import AppConfig


class UmlDiagramsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.uml_diagrams'
    verbose_name = 'UML Diagrams'
    
    def ready(self):
        """
        Initialize UML validation services and diagram patterns.
        """
        try:
            from . import signals  # noqa
        except ImportError:
            pass
