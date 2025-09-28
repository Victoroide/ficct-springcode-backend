"""
Public URLs for UML Diagrams.

Provides public access endpoints for diagrams without authentication.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets.public_diagram_viewset import PublicDiagramViewSet

# Create router for public diagram endpoints
router = DefaultRouter()
router.register(r'diagrams', PublicDiagramViewSet, basename='public-diagrams')

app_name = 'public_uml_diagrams'

urlpatterns = [
    path('', include(router.urls)),
]
