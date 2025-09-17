"""
Projects App Configuration for workspace and project management.
"""

from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """
    Django app configuration for Projects management.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.projects'
    verbose_name = 'Projects & Workspace Management'

    def ready(self):
        """
        Initialize app when Django starts.
        """
        try:
            import apps.projects.signals
        except ImportError:
            pass
