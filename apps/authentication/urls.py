
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter

from .viewsets import AuthenticationViewSet, RegistrationViewSet

router = DefaultRouter()

router.register(r'auth', AuthenticationViewSet, basename='auth')  
router.register(r'registration', RegistrationViewSet, basename='registration')

app_name = 'authentication'

urlpatterns = [
    path('api/v1/', include(router.urls)),
    
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
