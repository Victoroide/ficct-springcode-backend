"""Configuración de app Flutter Projects."""

from django.apps import AppConfig


class FlutterProjectsConfig(AppConfig):
    """Configuración para Flutter Projects app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flutter_projects"
    verbose_name = "Flutter Projects"
