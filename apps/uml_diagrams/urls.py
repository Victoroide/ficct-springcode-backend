from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import UMLDiagramViewSet, UMLElementViewSet, UMLRelationshipViewSet

app_name = 'uml_diagrams'

router = DefaultRouter()
router.register(r'diagrams', UMLDiagramViewSet, basename='umldiagram')
router.register(r'elements', UMLElementViewSet, basename='umlelement')
router.register(r'relationships', UMLRelationshipViewSet, basename='umlrelationship')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
