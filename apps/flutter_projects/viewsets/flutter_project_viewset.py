"""
ViewSet for Flutter Projects.

Proporciona endpoints CRUD para metadata de proyectos Flutter.
"""

import logging

from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.flutter_projects.models import FlutterProject
from apps.flutter_projects.serializers.flutter_project_serializer import (
    FlutterProjectCreateSerializer,
    FlutterProjectListSerializer,
    FlutterProjectSerializer,
    FlutterProjectUpdateSerializer,
)

logger = logging.getLogger(__name__)


class FlutterProjectViewSet(viewsets.ModelViewSet):
    """
    Endpoints:
    - GET /api/flutter-projects/ - Lista proyectos por sesión
    - POST /api/flutter-projects/ - Crea nuevo proyecto
    - GET /api/flutter-projects/{id}/ - Detalle de proyecto
    - PATCH /api/flutter-projects/{id}/ - Actualiza config/metadata
    - DELETE /api/flutter-projects/{id}/ - Elimina proyecto
    - GET /api/flutter-projects/{id}/export-config/ - Exporta configuración
    """

    queryset = FlutterProject.objects.all()
    permission_classes = [AllowAny]
    lookup_field = "id"

    def get_serializer_class(self):
        """Selecciona serializer según acción."""
        if self.action == "list":
            return FlutterProjectListSerializer
        elif self.action == "create":
            return FlutterProjectCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return FlutterProjectUpdateSerializer
        return FlutterProjectSerializer

    def get_queryset(self):
        """Filtra proyectos por session_id."""
        queryset = FlutterProject.objects.all()

        session_id = self.request.query_params.get("session_id")
        diagram_id = self.request.query_params.get("diagram_id")

        if self.action == "list":
            if not session_id:
                return FlutterProject.objects.none()
            queryset = queryset.filter(session_id=session_id)

        if diagram_id:
            queryset = queryset.filter(diagram_id=diagram_id)

        return queryset.order_by("-created_at")

    @ratelimit(key="ip", rate="50/h", method="POST")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            flutter_project = serializer.save()

            logger.info(
                f"Flutter project created: {flutter_project.id} "
                f"({flutter_project.project_name})"
            )

            response_serializer = FlutterProjectSerializer(flutter_project)

            return Response(
                response_serializer.data, status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error creating Flutter project: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @ratelimit(key="ip", rate="50/h", method="PATCH")
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        session_id = request.query_params.get("session_id")

        if instance.session_id != session_id:
            return Response(
                {"error": "No tienes permiso para actualizar este proyecto"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )

        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Flutter project updated: {instance.id}")

            response_serializer = FlutterProjectSerializer(instance)

            return Response(response_serializer.data)

        except Exception as e:
            logger.error(f"Error updating Flutter project: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        session_id = request.query_params.get("session_id")

        if instance.session_id != session_id:
            return Response(
                {"error": "No tienes permiso para eliminar este proyecto"},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info(
            f"Flutter project deleted: {instance.id} ({instance.project_name})"
        )

        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def export_config(self, request, id=None):
        instance = self.get_object()

        export_data = {
            "project_name": instance.project_name,
            "package_name": instance.package_name,
            "config": instance.config,
            "metadata": instance.metadata,
            "diagram_id": str(instance.diagram_id),
            "created_at": instance.created_at.isoformat(),
        }

        logger.info(f"Config exported for project: {instance.id}")

        return Response(export_data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        session_id = request.query_params.get("session_id")

        if not session_id:
            return Response(
                {"error": "session_id requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        projects = FlutterProject.objects.filter(session_id=session_id)

        themes_count = {}
        state_management_count = {}

        for project in projects:
            theme = project.get_config_value("theme", "unknown")
            themes_count[theme] = themes_count.get(theme, 0) + 1

            state_mgmt = project.get_config_value(
                "state_management", "unknown"
            )
            state_management_count[state_mgmt] = (
                state_management_count.get(state_mgmt, 0) + 1
            )

        stats = {
            "total_projects": projects.count(),
            "themes_used": themes_count,
            "state_management_used": state_management_count,
        }

        return Response(stats)
