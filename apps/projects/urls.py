"""
URL configuration for Projects app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .viewsets import (
    ProjectViewSet,
    ProjectMemberViewSet,
    WorkspaceViewSet,
    ProjectTemplateViewSet
)

app_name = 'projects'

# Main router
router = DefaultRouter()
router.register(r'workspaces', WorkspaceViewSet, basename='workspace')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'templates', ProjectTemplateViewSet, basename='project-template')

# Nested routers for project-specific resources
projects_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
projects_router.register(r'members', ProjectMemberViewSet, basename='project-members')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/', include(projects_router.urls)),
]
