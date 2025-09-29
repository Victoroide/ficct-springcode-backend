from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# Import API schema view
from .api_schema import api_schema_view


def get_spectacular_urls():
    """Get URLs for API documentation."""
    return [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path(
            'docs/', 
            SpectacularSwaggerView.as_view(url_name='schema'), 
            name='swagger-ui'
        ),
        path(
            'api/docs/redoc/', 
            SpectacularRedocView.as_view(url_name='schema'), 
            name='redoc'
        ),
    ]


@extend_schema(
    tags=['System'],
    summary='API Health Check',
    description='Check API service health status',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'timestamp': {'type': 'string', 'format': 'date-time'},
                'version': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_health_check(request):
    """API health check endpoint."""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """API information endpoint."""
    return api_schema_view(request)


# Admin site configuration
admin.site.site_header = 'UML Collaborative Tool Admin'
admin.site.site_title = 'UML Tool'
admin.site.index_title = 'UML Tool Management'

# Static file serving
import os

def serve_static_file(request, filename):
    """Serve static HTML files."""
    file_path = os.path.join(settings.BASE_DIR, 'static', filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='text/html')
    else:
        return JsonResponse({'error': 'File not found'}, status=404)


urlpatterns = [
    *get_spectacular_urls(),
    path('admin/', admin.site.urls),
    path('api/health/', api_health_check, name='api_health_check'),
    path('api/', api_info, name='api_info'),
    path('api/diagrams/', include('apps.uml_diagrams.urls', namespace='uml_diagrams')),
    path('api/ai-assistant/', include('apps.ai_assistant.urls', namespace='ai_assistant')),
    
    # Frontend routes
    path('', lambda request: serve_static_file(request, 'index.html'), name='home'),
    path('editor/<uuid:diagram_id>/', lambda request, diagram_id: serve_static_file(request, 'editor.html'), name='editor'),
]

# Static files in debug mode
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
