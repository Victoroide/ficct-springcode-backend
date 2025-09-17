"""
Code Generation app configuration for SpringBoot code generation engine.
"""

from django.apps import AppConfig


class CodeGenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.code_generation'
    verbose_name = 'SpringBoot Code Generation'
    
    def ready(self):
        """
        Initialize code generation templates and services.
        """
        try:
            from . import signals  # noqa
        except ImportError:
            pass
