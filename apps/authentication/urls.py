"""
Enterprise Authentication URLs - RESTful Architecture

Consolidated URL configuration for authentication endpoints following RESTful conventions.
Integrates all authentication, registration, user management, sessions, audit logs, and domain management.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import from viewsets directory
from .viewsets import AuthenticationViewSet, RegistrationViewSet

# Create router for RESTful ViewSets
router = DefaultRouter()

# Core authentication and registration (non-CRUD actions)
router.register(r'auth', AuthenticationViewSet, basename='auth')  
router.register(r'registration', RegistrationViewSet, basename='registration')

app_name = 'authentication'

urlpatterns = [
    # All endpoints are now handled by the router following RESTful conventions
    path('api/v1/', include(router.urls)),
    
    # Custom authentication actions (non-CRUD)
    path('api/v1/auth/login/', AuthenticationViewSet.as_view({
        'post': 'login'
    }), name='auth-login'),
    
    path('api/v1/auth/2fa/verify/', AuthenticationViewSet.as_view({
        'post': 'verify_2fa'
    }), name='auth-verify-2fa'),
    
    path('api/v1/auth/logout/', AuthenticationViewSet.as_view({
        'post': 'logout'
    }), name='auth-logout'),
    
    path('api/v1/auth/refresh-token/', AuthenticationViewSet.as_view({
        'post': 'refresh_token'
    }), name='auth-refresh-token'),
    
    # Custom registration actions (non-CRUD)
    path('api/v1/registration/register/', RegistrationViewSet.as_view({
        'post': 'register'
    }), name='registration-register'),
    
    path('api/v1/registration/verify-email/', RegistrationViewSet.as_view({
        'post': 'verify_email'
    }), name='registration-verify-email'),
    
    path('api/v1/registration/setup-2fa/', RegistrationViewSet.as_view({
        'post': 'setup_2fa'
    }), name='registration-setup-2fa'),
]
