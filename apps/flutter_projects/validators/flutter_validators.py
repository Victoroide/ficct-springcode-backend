"""
Validators for Flutter Projects.

Validates package names, project names, and Flutter project configuration.
"""

import re
from typing import Any, Dict

from django.core.exceptions import ValidationError


def validate_package_name(value: str) -> None:
    pattern = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Package name '{value}' inválido. "
            f"Formato requerido: 'com.example.app' (lowercase, dots separating segments)"
        )


def validate_project_name(value: str) -> None:
    pattern = r"^[a-z][a-z0-9_]*$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Project name '{value}' inválido. "
            f"Formato requerido: snake_case (ej: 'erp_inventory', 'mobile_app')"
        )


def validate_theme(value: str) -> None:
    allowed_themes = ["material3", "cupertino"]

    if value not in allowed_themes:
        raise ValidationError(
            f"Theme '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_themes)}"
        )


def validate_navigation_type(value: str) -> None:
    allowed_types = ["drawer", "bottom_nav", "tabs"]

    if value not in allowed_types:
        raise ValidationError(
            f"Navigation type '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_types)}"
        )


def validate_state_management(value: str) -> None:
    allowed_libraries = ["provider", "riverpod", "bloc", "getx"]

    if value not in allowed_libraries:
        raise ValidationError(
            f"State management '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_libraries)}"
        )


def validate_primary_color(value: str) -> None:
    pattern = r"^#[0-9A-Fa-f]{6}$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Color '{value}' inválido. "
            f"Formato requerido: #RRGGBB (ej: '#2196F3')"
        )


def validate_flutter_config(config: Dict[str, Any]) -> None:
    errors = []

    if "theme" in config:
        try:
            validate_theme(config["theme"])
        except ValidationError as e:
            errors.append(str(e))

    if "navigation_type" in config:
        try:
            validate_navigation_type(config["navigation_type"])
        except ValidationError as e:
            errors.append(str(e))

    if "state_management" in config:
        try:
            validate_state_management(config["state_management"])
        except ValidationError as e:
            errors.append(str(e))

    if "primary_color" in config:
        try:
            validate_primary_color(config["primary_color"])
        except ValidationError as e:
            errors.append(str(e))

    if errors:
        raise ValidationError(errors)
