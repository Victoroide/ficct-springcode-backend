"""
Enterprise Spectacular Views Infrastructure
Custom SwaggerUI implementation with CDN fallback and static asset serving.
"""

import os
import mimetypes
from pathlib import Path
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.urls import path
from django.conf import settings
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
import requests
import logging

logger = logging.getLogger(__name__)


class SwaggerUIView(TemplateView):
    """
    Custom SwaggerUI view with CDN fallback and enterprise styling.
    """
    template_name = 'swagger-ui.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schema_url'] = '/api/schema/'
        context['title'] = 'FICCT Enterprise API Documentation'
        return context


def serve_swagger_file(request, filename):
    """
    Serve swagger-ui static files with CDN fallback.
    """

    swagger_files = {
        'swagger-ui-bundle.js': 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js',
        'swagger-ui-standalone-preset.js': 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js',
        'swagger-ui.css': 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css',
    }
    
    if filename not in swagger_files:
        raise Http404(f"Swagger file {filename} not found")

    static_path = Path(settings.STATICFILES_DIRS[0]) / 'drf_spectacular_sidecar' / filename
    
    if static_path.exists():
        try:
            with open(static_path, 'rb') as f:
                content = f.read()
                content_type, _ = mimetypes.guess_type(filename)
                return HttpResponse(content, content_type=content_type or 'application/octet-stream')
        except Exception as e:
            logger.warning(f"Failed to serve local file {filename}: {e}")

    try:
        cdn_url = swagger_files[filename]
        response = requests.get(cdn_url, timeout=10)
        response.raise_for_status()

        os.makedirs(static_path.parent, exist_ok=True)
        with open(static_path, 'wb') as f:
            f.write(response.content)
        
        content_type, _ = mimetypes.guess_type(filename)
        return HttpResponse(
            response.content, 
            content_type=content_type or 'application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch {filename} from CDN: {e}")
        raise Http404(f"Could not load {filename}")


def get_spectacular_urls():
    """
    Generate spectacular URL patterns with custom views.
    """
    return [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SwaggerUIView.as_view(), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
        path('swagger-ui-assets/<str:filename>', serve_swagger_file, name='swagger-ui-assets'),
    ]
