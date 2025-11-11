"""
Serializers for Flutter Projects.

Handles serialization and validation of Flutter projects.
"""

from rest_framework import serializers

from apps.flutter_projects.models import FlutterProject
from apps.flutter_projects.validators.flutter_validators import (
    validate_flutter_config,
    validate_package_name,
    validate_primary_color,
    validate_project_name,
)


class FlutterProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlutterProject
        fields = [
            "id",
            "diagram_id",
            "session_id",
            "project_name",
            "package_name",
            "config",
            "metadata",
            "created_at",
            "last_generated",
        ]
        read_only_fields = ["id", "created_at", "last_generated"]

    def validate_project_name(self, value: str) -> str:
        """Validates project name with custom validator."""
        validate_project_name(value)
        return value

    def validate_package_name(self, value: str) -> str:
        """Validates package name with custom validator."""
        validate_package_name(value)
        return value

    def validate_config(self, value: dict) -> dict:
        validate_flutter_config(value)

        if "enable_dark_mode" in value and not isinstance(
            value["enable_dark_mode"], bool
        ):
            raise serializers.ValidationError(
                {"enable_dark_mode": "Debe ser booleano"}
            )

        return value


class FlutterProjectCreateSerializer(serializers.ModelSerializer):
    config = serializers.JSONField(required=False, default=dict)
    metadata = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = FlutterProject
        fields = [
            "diagram_id",
            "session_id",
            "project_name",
            "package_name",
            "config",
            "metadata",
        ]

    def validate_project_name(self, value: str) -> str:
        """Validates project name."""
        validate_project_name(value)
        return value

    def validate_package_name(self, value: str) -> str:
        """Validates package name."""
        validate_package_name(value)
        return value

    def validate_config(self, value: dict) -> dict:
        """Validates configuration."""
        if value:
            validate_flutter_config(value)
        return value

    def validate(self, attrs):
        """Object-level validation."""
        config = attrs.get("config", {})

        defaults = {
            "theme": "material3",
            "primary_color": "#2196F3",
            "navigation_type": "bottom_nav",
            "state_management": "provider",
            "enable_dark_mode": True,
        }

        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value

        attrs["config"] = config

        metadata = attrs.get("metadata", {})

        if "version" not in metadata:
            metadata["version"] = "1.0.0"

        if "description" not in metadata:
            metadata["description"] = f"Flutter app for {attrs['project_name']}"

        attrs["metadata"] = metadata

        return attrs


class FlutterProjectUpdateSerializer(serializers.ModelSerializer):
    """Permite actualizar config y metadata, pero no campos inmutables."""
    class Meta:
        model = FlutterProject
        fields = ["config", "metadata"]

    def validate_config(self, value: dict) -> dict:
        """Validates configuration."""
        validate_flutter_config(value)
        return value


class FlutterProjectListSerializer(serializers.ModelSerializer):
    """Versión ligera sin config/metadata completos."""
    theme = serializers.SerializerMethodField()
    classes_count = serializers.SerializerMethodField()

    class Meta:
        model = FlutterProject
        fields = [
            "id",
            "project_name",
            "package_name",
            "theme",
            "classes_count",
            "created_at",
            "last_generated",
        ]

    def get_theme(self, obj: FlutterProject) -> str:
        return obj.get_config_value("theme", "material3")

    def get_classes_count(self, obj: FlutterProject) -> int:
        return obj.get_metadata_value("classes_count", 0)
