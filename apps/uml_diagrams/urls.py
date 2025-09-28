from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets.anonymous_diagram_viewset import AnonymousDiagramViewSet

app_name = 'uml_diagrams'

router = DefaultRouter()
router.register(r'', AnonymousDiagramViewSet, basename='diagrams')

urlpatterns = [
    path('', include(router.urls)),
]
