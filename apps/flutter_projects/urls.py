"""URLs para Flutter Projects app."""

from rest_framework.routers import DefaultRouter

from apps.flutter_projects.viewsets.flutter_project_viewset import (
    FlutterProjectViewSet,
)

router = DefaultRouter()
router.register(r"flutter-projects", FlutterProjectViewSet, basename="flutter_project")

urlpatterns = router.urls
