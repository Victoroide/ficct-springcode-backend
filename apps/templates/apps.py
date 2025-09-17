"""
Templates App Configuration for SpringBoot code generation templates.
"""

from django.apps import AppConfig


class TemplatesConfig(AppConfig):
    """
    Django app configuration for SpringBoot code generation templates.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.templates'
    verbose_name = 'SpringBoot Code Generation Templates'

    def ready(self):
        """
        Initialize app when Django starts.
        """
        pass
