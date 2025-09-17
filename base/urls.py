"""FICCT Enterprise URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from drf_spectacular.utils import extend_schema
from drf_spectacular.openapi import AutoSchema
from .spectacular_views import get_spectacular_urls


@extend_schema(
    tags=['System'],
    summary='API Health Check',
    description='Check API service health status',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'service': {'type': 'string'},
                'version': {'type': 'string'},
                'environment': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_health_check(request):
    return Response({
        'status': 'healthy',
        'service': 'FICCT Enterprise API',
        'version': '1.0.0',
        'environment': 'development' if settings.DEBUG else 'production'
    })


@extend_schema(
    tags=['System'],
    summary='API Information',
    description='Get API service information and available endpoints',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'version': {'type': 'string'},
                'documentation': {'type': 'string'},
                'swagger': {'type': 'string'},
                'redoc': {'type': 'string'},
                'endpoints': {
                    'type': 'object',
                    'properties': {
                        'authentication': {'type': 'string'},
                        'registration': {'type': 'string'},
                        'user_profile': {'type': 'string'},
                        'security': {'type': 'string'},
                        'admin': {'type': 'string'}
                    }
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    return Response({
        'name': 'FICCT Enterprise API',
        'description': 'Enterprise SpringBoot Code Generation Platform API',
        'version': '1.0.0',
        'documentation': '/api/docs/',
        'swagger': '/api/schema/swagger-ui/',
        'redoc': '/api/schema/redoc/',
        'endpoints': {
            'authentication': '/api/auth/',
            'registration': '/api/registration/',
            'user_profile': '/api/user/',
            'security': '/api/security/',
            'admin': '/admin/'
        }
    })
admin.site.site_header = 'FICCT Enterprise Administration'
admin.site.site_title = 'FICCT Enterprise'
admin.site.index_title = 'Enterprise Management Portal'

urlpatterns = [
    *get_spectacular_urls(),
    path('admin/', admin.site.urls),
    path('api/health/', api_health_check, name='api_health_check'),
    path('api/', api_info, name='api_info'),
    path('', include('apps.authentication.urls', namespace='auth')),
    path('', include('apps.collaboration.urls', namespace='collaboration')),
    path('', include('apps.uml_diagrams.urls', namespace='uml_diagrams')),
    path('', include('apps.code_generation.urls', namespace='code_generation')),
    path('', include('apps.projects.urls', namespace='projects')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error handlers for production
if not settings.DEBUG:
    from django.views.defaults import page_not_found, server_error, permission_denied, bad_request
    
    def custom_404(request, exception):
        return JsonResponse({
            'error': 'Not Found',
            'status_code': 404,
            'message': 'The requested resource was not found.'
        }, status=404)
    
    def custom_500(request):
        return JsonResponse({
            'error': 'Internal Server Error',
            'status_code': 500,
            'message': 'An internal server error occurred.'
        }, status=500)
    
    def custom_403(request, exception):
        return JsonResponse({
            'error': 'Forbidden',
            'status_code': 403,
            'message': 'You do not have permission to access this resource.'
        }, status=403)
    
    def custom_400(request, exception):
        return JsonResponse({
            'error': 'Bad Request',
            'status_code': 400,
            'message': 'The request was malformed or invalid.'
        }, status=400)
    
    handler404 = custom_404
    handler500 = custom_500
    handler403 = custom_403
    handler400 = custom_400
