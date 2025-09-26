"""
Unit Tests for Base System Endpoints

Tests for core system functionality including health checks, API info,
documentation endpoints, and error handlers.
"""

import json
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, Mock
from .test_base import BaseTestCase


class SystemEndpointsTestCase(APITestCase):
    """Test cases for base system endpoints."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_api_health_check_success(self):
        """Test GET /api/health/ returns healthy status."""
        url = reverse('api_health_check')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['service'], 'FICCT Enterprise API')
        self.assertEqual(response.data['version'], '1.0.0')
        self.assertIn('environment', response.data)
    
    @override_settings(DEBUG=True)
    def test_api_health_check_development_environment(self):
        """Test health check returns development environment when DEBUG=True."""
        url = reverse('api_health_check')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['environment'], 'development')
    
    @override_settings(DEBUG=False)
    def test_api_health_check_production_environment(self):
        """Test health check returns production environment when DEBUG=False."""
        url = reverse('api_health_check')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['environment'], 'production')
    
    def test_api_info_success(self):
        """Test GET /api/ returns API information."""
        url = reverse('api_info')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'FICCT Enterprise API')
        self.assertEqual(response.data['description'], 'Enterprise SpringBoot Code Generation Platform API')
        self.assertEqual(response.data['version'], '1.0.0')
        
        # Check documentation endpoints
        self.assertEqual(response.data['documentation'], '/api/docs/')
        self.assertEqual(response.data['swagger'], '/api/schema/swagger-ui/')
        self.assertEqual(response.data['redoc'], '/api/schema/redoc/')
        
        # Check endpoint information
        expected_endpoints = {
            'authentication': '/api/auth/',
            'registration': '/api/registration/',
            'user_profile': '/api/user/',
            'security': '/api/security/',
            'admin': '/admin/'
        }
        self.assertEqual(response.data['endpoints'], expected_endpoints)
    
    def test_openapi_schema_endpoint(self):
        """Test GET /api/schema/ returns OpenAPI schema."""
        url = reverse('schema')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/vnd.oai.openapi', response['Content-Type'])
        
        # Check that response contains basic OpenAPI structure (YAML format)
        content = response.content.decode('utf-8')
        self.assertIn('openapi:', content)
        self.assertIn('info:', content)
        self.assertIn('paths:', content)
    
    def test_swagger_ui_endpoint(self):
        """Test GET /api/docs/ returns Swagger UI."""
        url = reverse('swagger-ui')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
        self.assertIn(b'swagger-ui', response.content.lower())
    
    def test_redoc_endpoint(self):
        """Test GET /api/redoc/ returns ReDoc documentation."""
        url = reverse('redoc')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
        self.assertIn(b'redoc', response.content.lower())
    
    @patch('requests.get')
    def test_swagger_assets_cdn_fallback(self, mock_get):
        """Test swagger assets endpoint with CDN fallback."""
        # Mock successful CDN response
        mock_response = Mock()
        mock_response.content = b'mock css content'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        url = reverse('swagger-ui-assets', kwargs={'filename': 'swagger-ui.css'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b'mock css content')
    
    def test_swagger_assets_invalid_file(self):
        """Test swagger assets endpoint with invalid filename."""
        url = reverse('swagger-ui-assets', kwargs={'filename': 'invalid-file.js'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('requests.get')
    def test_swagger_assets_cdn_failure(self, mock_get):
        """Test swagger assets endpoint when CDN fails."""
        # Mock CDN failure
        mock_get.side_effect = Exception("CDN Error")
        
        url = reverse('swagger-ui-assets', kwargs={'filename': 'swagger-ui.css'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(DEBUG=False)
class CustomErrorHandlersTestCase(APITestCase):
    """Test cases for custom error handlers in production."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_404_error_handler(self):
        """Test custom 404 error handler returns JSON response."""
        response = self.client.get('/nonexistent-endpoint/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertEqual(data['error'], 'Not Found')
        self.assertEqual(data['status_code'], 404)
        self.assertEqual(data['message'], 'The requested resource was not found.')
    
    def test_403_error_handler(self):
        """Test custom 403 error handler returns JSON response."""
        # This would need specific setup to trigger 403 - placeholder test
        # In a real scenario, you'd set up a view that raises 403
        pass
    
    def test_400_error_handler(self):
        """Test custom 400 error handler returns JSON response."""
        # This would need specific setup to trigger 400 - placeholder test
        # In a real scenario, you'd set up a view that raises 400
        pass


class AdminEndpointTestCase(BaseTestCase):
    """Test cases for Django admin endpoints."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_admin_login_page_accessible(self):
        """Test that admin login page is accessible."""
        response = self.client.get('/admin/')
        
        # Should redirect to login or show login page
        self.assertIn(response.status_code, [200, 302])
    
    def test_admin_login_redirect_unauthenticated(self):
        """Test that admin redirects unauthenticated users."""
        response = self.client.get('/admin/', follow=True)
        
        # Should eventually show login page
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.content.lower())


class APIRateLimitingTestCase(APITestCase):
    """Test cases for API rate limiting (if implemented)."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_health_check_no_rate_limit(self):
        """Test that health check endpoint is not rate limited."""
        url = reverse('api_health_check')
        
        # Make multiple requests quickly
        for _ in range(10):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_api_info_no_rate_limit(self):
        """Test that API info endpoint is not rate limited."""
        url = reverse('api_info')
        
        # Make multiple requests quickly
        for _ in range(10):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class SecurityHeadersTestCase(APITestCase):
    """Test cases for security headers in responses."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_health_check_security_headers(self):
        """Test that health check includes appropriate security headers."""
        url = reverse('api_health_check')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Add specific security header checks based on your security configuration
    
    def test_api_info_security_headers(self):
        """Test that API info includes appropriate security headers."""
        url = reverse('api_info')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Add specific security header checks based on your security configuration


class CORSTestCase(APITestCase):
    """Test cases for CORS configuration."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_cors_headers_health_check(self):
        """Test CORS headers on health check endpoint."""
        url = reverse('api_health_check')
        response = self.client.options(url, HTTP_ORIGIN='http://localhost:3000')
        
        # Should handle OPTIONS request for CORS
        self.assertIn(response.status_code, [200, 204])
    
    def test_cors_headers_api_info(self):
        """Test CORS headers on API info endpoint."""
        url = reverse('api_info')
        response = self.client.options(url, HTTP_ORIGIN='http://localhost:3000')
        
        # Should handle OPTIONS request for CORS
        self.assertIn(response.status_code, [200, 204])
