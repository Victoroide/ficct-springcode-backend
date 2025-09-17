"""
URL configuration for Code Generation app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    GenerationRequestViewSet,
    GenerationTemplateViewSet,
    GeneratedProjectViewSet,
    GenerationHistoryViewSet
)

app_name = 'code_generation'

router = DefaultRouter()
router.register(r'requests', GenerationRequestViewSet, basename='generation-request')
router.register(r'templates', GenerationTemplateViewSet, basename='generation-template')
router.register(r'projects', GeneratedProjectViewSet, basename='generated-project')
router.register(r'history', GenerationHistoryViewSet, basename='generation-history')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
