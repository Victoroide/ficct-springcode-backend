from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import CollaborationSessionViewSet, SessionParticipantViewSet, UMLChangeEventViewSet

app_name = 'collaboration'

router = DefaultRouter()
router.register(r'sessions', CollaborationSessionViewSet, basename='collaborationsession')
router.register(r'participants', SessionParticipantViewSet, basename='sessionparticipant')
router.register(r'events', UMLChangeEventViewSet, basename='umlchangeevent')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
