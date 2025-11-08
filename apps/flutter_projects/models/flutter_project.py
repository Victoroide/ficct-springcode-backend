"""
Flutter Project model for storing Flutter project metadata.

Flutter code is generated 100% in frontend (TypeScript).
Backend only stores configuration metadata.
"""

import uuid

from django.db import models


class FlutterProject(models.Model):
    """
    Model for Flutter project metadata.

    Attributes:
        id: Unique project UUID
        diagram_id: UUID of the UML diagram used
        session_id: Anonymous session ID of creator
        project_name: Project name (snake_case)
        package_name: Package name (com.example.app)
        config: Project configuration (theme, colors, navigation)
        metadata: Additional metadata (version, description, author)
        created_at: Creation date
        last_generated: Last generation date
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique Flutter project UUID",
    )

    diagram_id = models.UUIDField(
        db_index=True,
        help_text="UUID of UML diagram used to generate project",
    )

    session_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Anonymous session ID of creator",
    )

    project_name = models.CharField(
        max_length=200,
        help_text="Project name in snake_case (e.g. erp_inventory)",
    )

    package_name = models.CharField(
        max_length=200,
        help_text="Package name (e.g. com.example.erp_inventory)",
    )

    config = models.JSONField(
        default=dict,
        help_text="Flutter project configuration",
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Additional project metadata",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    last_generated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "flutter_projects"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["diagram_id"]),
            models.Index(fields=["session_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["project_name"]),
        ]

    def __str__(self) -> str:
        """String representation."""
        return f"{self.project_name} ({self.package_name})"

    def get_config_value(self, key: str, default=None):
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if not exists

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def update_config(self, updates: dict) -> None:
        """Update project configuration.

        Args:
            updates: Dictionary with updates

        Example:
            >>> project.update_config({"theme": "material3"})
        """
        self.config.update(updates)
        self.save(update_fields=["config", "last_generated"])

    def get_metadata_value(self, key: str, default=None):
        """Get metadata value.

        Args:
            key: Metadata key
            default: Default value if not exists

        Returns:
            Metadata value
        """
        return self.metadata.get(key, default)

    def update_metadata(self, updates: dict) -> None:
        """Update project metadata.

        Args:
            updates: Dictionary with updates

        Example:
            >>> project.update_metadata({"version": "1.0.1"})
        """
        self.metadata.update(updates)
        self.save(update_fields=["metadata", "last_generated"])
