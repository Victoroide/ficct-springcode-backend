"""
Validators for Flutter Projects.

Validates package names, project names, and Flutter project configuration.
"""

import re
from typing import Any, Dict

from django.core.exceptions import ValidationError


def validate_package_name(value: str) -> None:
    """
    Validates Flutter package name.

    Formato: com.example.app o com.company.product.module

    Args:
        value: Package name a validar

    Raises:
        ValidationError: If format is invalid

    Example:
        >>> validate_package_name("com.example.app")  # OK
        >>> validate_package_name("InvalidPackage")  # ValidationError
    """
    pattern = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Package name '{value}' inválido. "
            f"Formato requerido: 'com.example.app' (lowercase, dots separating segments)"
        )


def validate_project_name(value: str) -> None:
    """
    Validates Flutter project name.

    Formato: snake_case (ej: erp_inventory, mobile_app)

    Args:
        value: Project name a validar

    Raises:
        ValidationError: If format is invalid

    Example:
        >>> validate_project_name("erp_inventory")  # OK
        >>> validate_project_name("ERP-Inventory")  # ValidationError
    """
    pattern = r"^[a-z][a-z0-9_]*$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Project name '{value}' inválido. "
            f"Formato requerido: snake_case (ej: 'erp_inventory', 'mobile_app')"
        )


def validate_theme(value: str) -> None:
    """
    Validates Flutter theme.

    Args:
        value: Theme a validar

    Raises:
        ValidationError: If theme is not allowed
    """
    allowed_themes = ["material3", "cupertino"]

    if value not in allowed_themes:
        raise ValidationError(
            f"Theme '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_themes)}"
        )


def validate_navigation_type(value: str) -> None:
    """
    Validates Flutter navigation type.

    Args:
        value: Navigation type a validar

    Raises:
        ValidationError: If navigation type is not allowed
    """
    allowed_types = ["drawer", "bottom_nav", "tabs"]

    if value not in allowed_types:
        raise ValidationError(
            f"Navigation type '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_types)}"
        )


def validate_state_management(value: str) -> None:
    """
    Validates state management library.

    Args:
        value: State management a validar

    Raises:
        ValidationError: If not allowed
    """
    allowed_libraries = ["provider", "riverpod", "bloc", "getx"]

    if value not in allowed_libraries:
        raise ValidationError(
            f"State management '{value}' inválido. "
            f"Valores permitidos: {', '.join(allowed_libraries)}"
        )


def validate_primary_color(value: str) -> None:
    """
    Validates hexadecimal color.

    Args:
        value: Color en formato hex (#RRGGBB)

    Raises:
        ValidationError: If format is invalid

    Example:
        >>> validate_primary_color("#2196F3")  # OK
        >>> validate_primary_color("blue")  # ValidationError
    """
    pattern = r"^#[0-9A-Fa-f]{6}$"

    if not re.match(pattern, value):
        raise ValidationError(
            f"Color '{value}' inválido. "
            f"Formato requerido: #RRGGBB (ej: '#2196F3')"
        )


def validate_flutter_config(config: Dict[str, Any]) -> None:
    """
    Validates complete Flutter project configuration.

    Args:
        config: Diccionario de configuración

    Raises:
        ValidationError: Si algún campo es inválido

    Example:
        >>> config = {
        ...     "theme": "material3",
        ...     "primary_color": "#2196F3",
        ...     "navigation_type": "drawer"
        ... }
        >>> validate_flutter_config(config)  # OK
    """
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
