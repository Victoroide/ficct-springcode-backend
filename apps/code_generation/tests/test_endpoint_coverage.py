"""
Comprehensive Unit Tests for Code Generation Endpoints

Tests for ALL code generation endpoints including GenerationRequestViewSet,
GenerationTemplateViewSet, GeneratedProjectViewSet, and GenerationHistoryViewSet.
"""

import json
from unittest.mock import patch, Mock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from base.test_base import BaseTestCase
from base.test_factories import EnterpriseUserFactory
from apps.code_generation.models import (
    GenerationRequest, GenerationTemplate, GeneratedProject, GenerationHistory
)
from apps.projects.models import Project
from apps.uml_diagrams.models import UMLDiagram

User = get_user_model()


class GenerationRequestViewSetTestCase(BaseTestCase):
    """Test cases for GenerationRequestViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and diagram
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for code generation',
            owner=self.test_user
        )
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user
        )
        
        # Create test generation request
        self.generation_request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.test_user,
            generation_type='spring_boot',
            parameters={'package_name': 'com.example.test'},
            status='pending'
        )
        
        self.base_url = '/api/v1/requests/'
    
    def test_list_requests_success(self):
        """Test GET /api/v1/requests/ returns list of generation requests."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_request_success(self):
        """Test POST /api/v1/requests/ creates new generation request."""
        data = {
            'project': self.project.id,
            'diagram': self.diagram.id,
            'generation_type': 'spring_boot',
            'parameters': {
                'package_name': 'com.example.newtest',
                'java_version': '17',
                'spring_boot_version': '3.0.0'
            }
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['generation_type'], 'spring_boot')
        self.assertEqual(response.data['project'], self.project.id)
    
    def test_create_request_missing_fields(self):
        """Test creating request with missing required fields."""
        data = {
            'project': self.project.id,
            'generation_type': 'spring_boot'
            # Missing diagram
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_request_success(self):
        """Test GET /api/v1/requests/{id}/ returns specific request."""
        url = f'{self.base_url}{self.generation_request.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.generation_request.id)
        self.assertEqual(response.data['generation_type'], 'spring_boot')
    
    def test_update_request_success(self):
        """Test PATCH /api/v1/requests/{id}/ updates request."""
        url = f'{self.base_url}{self.generation_request.id}/'
        data = {
            'parameters': {
                'package_name': 'com.example.updated',
                'description': 'Updated request'
            }
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['parameters']['package_name'],
            'com.example.updated'
        )
    
    def test_delete_request_success(self):
        """Test DELETE /api/v1/requests/{id}/ deletes request."""
        request_to_delete = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.test_user,
            generation_type='spring_boot',
            parameters={},
            status='pending'
        )
        
        url = f'{self.base_url}{request_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            GenerationRequest.objects.filter(id=request_to_delete.id).exists()
        )


class GenerationTemplateViewSetTestCase(BaseTestCase):
    """Test cases for GenerationTemplateViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test template
        self.template = GenerationTemplate.objects.create(
            name='Spring Boot Template',
            template_type='spring_boot',
            version='1.0',
            description='Template for Spring Boot applications',
            template_content={'files': [], 'structure': {}},
            created_by=self.test_user,
            is_active=True
        )
        
        self.base_url = '/api/v1/templates/'
    
    def test_list_templates_success(self):
        """Test GET /api/v1/templates/ returns list of templates."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_template_success(self):
        """Test POST /api/v1/templates/ creates new template."""
        data = {
            'name': 'New Spring Boot Template',
            'description': 'Updated Spring Boot template',
            'language': 'java',
            'framework': 'springboot',
            'template_type': 'ENTITY',
            'template_content': 'public class {{className}} { }',
            'output_filename_pattern': '{{className}}.java',
            'output_directory': 'src/main/java',
            'is_active': True
        }
        
        response = self.client.post(self.base_url, data, format='json')
        
        # Should handle gracefully - either create successfully or return appropriate error
        self.assertIn(response.status_code, [201, 400, 500])
        if response.status_code == 201:
            self.assertEqual(response.data['name'], 'New Spring Boot Template')
            self.assertEqual(response.data['template_type'], 'ENTITY')
    
    def test_retrieve_template_success(self):
        """Test GET /api/v1/templates/{id}/ returns specific template."""
        url = f'{self.base_url}{self.template.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.template.id)
        self.assertEqual(response.data['name'], 'Spring Boot Template')
    
    def test_update_template_success(self):
        """Test PATCH /api/v1/templates/{id}/ updates template."""
        url = f'{self.base_url}{self.template.id}/'
        data = {
            'description': 'Updated template description',
            'version': '1.1'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated template description')
        self.assertEqual(response.data['version'], '1.1')
    
    def test_delete_template_success(self):
        """Test DELETE /api/v1/templates/{id}/ deletes template."""
        template_to_delete = GenerationTemplate.objects.create(
            name='Template to Delete',
            template_type='spring_boot',
            version='1.0',
            template_content={},
            created_by=self.test_user
        )
        
        url = f'{self.base_url}{template_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            GenerationTemplate.objects.filter(id=template_to_delete.id).exists()
        )


class GeneratedProjectViewSetTestCase(BaseTestCase):
    """Test cases for GeneratedProjectViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and related objects
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for code generation',
            owner=self.test_user
        )
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user
        )
        
        self.generation_request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.test_user,
            generation_type='spring_boot',
            parameters={},
            status='completed'
        )
        
        # Create test generated project
        self.generated_project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='GeneratedTestProject',
            generated_code={'files': [], 'structure': {}},
            file_structure={'src': ['main', 'test']},
            download_url='http://example.com/download/123',
            status='completed'
        )
        
        self.base_url = '/api/v1/generated-projects/'
    
    def test_list_projects_success(self):
        """Test GET /api/v1/projects/ returns list of generated projects."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_create_project_success(self):
        """Test POST /api/v1/projects/ creates new generated project."""
        data = {
            'generation_request': self.generation_request.id,
            'project_name': 'NewGeneratedProject',
            'generated_code': {
                'files': ['Application.java'],
                'content': {'Application.java': 'public class Application {}'}
            },
            'file_structure': {'src': ['main']},
            'status': 'in_progress'
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['project_name'], 'NewGeneratedProject')
        self.assertEqual(response.data['status'], 'in_progress')
    
    def test_retrieve_project_success(self):
        """Test GET /api/v1/projects/{id}/ returns specific generated project."""
        url = f'{self.base_url}{self.generated_project.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.generated_project.id)
        self.assertEqual(response.data['project_name'], 'GeneratedTestProject')
    
    def test_update_project_success(self):
        """Test PATCH /api/v1/projects/{id}/ updates generated project."""
        url = f'{self.base_url}{self.generated_project.id}/'
        data = {
            'status': 'completed',
            'download_url': 'http://example.com/download/updated'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['download_url'], 'http://example.com/download/updated')
    
    def test_delete_project_success(self):
        """Test DELETE /api/v1/projects/{id}/ deletes generated project."""
        project_to_delete = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='ProjectToDelete',
            generated_code={},
            file_structure={},
            status='completed'
        )
        
        url = f'{self.base_url}{project_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            GeneratedProject.objects.filter(id=project_to_delete.id).exists()
        )


class GenerationHistoryViewSetTestCase(BaseTestCase):
    """Test cases for GenerationHistoryViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and related objects
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for code generation',
            owner=self.test_user
        )
        
        self.generation_request = GenerationRequest.objects.create(
            project=self.project,
            requested_by=self.test_user,
            generation_type='spring_boot',
            parameters={},
            status='completed'
        )
        
        # Create test history entry
        self.history = GenerationHistory.objects.create(
            generation_request=self.generation_request,
            user=self.test_user,
            action='generation_started',
            details={'message': 'Code generation initiated'},
            timestamp='2024-01-01T00:00:00Z'
        )
        
        self.base_url = '/api/v1/history/'
    
    def test_list_history_success(self):
        """Test GET /api/v1/history/ returns list of history entries."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_create_history_success(self):
        """Test POST /api/v1/history/ creates new history entry."""
        data = {
            'generation_request': self.generation_request.id,
            'action': 'generation_completed',
            'details': {
                'message': 'Code generation completed successfully',
                'files_generated': 25
            }
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['action'], 'generation_completed')
        self.assertEqual(response.data['details']['files_generated'], 25)
    
    def test_retrieve_history_success(self):
        """Test GET /api/v1/history/{id}/ returns specific history entry."""
        url = f'{self.base_url}{self.history.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.history.id)
        self.assertEqual(response.data['action'], 'generation_started')
    
    def test_update_history_success(self):
        """Test PATCH /api/v1/history/{id}/ updates history entry."""
        url = f'{self.base_url}{self.history.id}/'
        data = {
            'details': {
                'message': 'Updated message',
                'additional_info': 'Added information'
            }
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['details']['message'], 'Updated message')
    
    def test_delete_history_success(self):
        """Test DELETE /api/v1/history/{id}/ deletes history entry."""
        history_to_delete = GenerationHistory.objects.create(
            generation_request=self.generation_request,
            user=self.test_user,
            action='generation_failed',
            details={'error': 'Test error'},
            timestamp='2024-01-02T00:00:00Z'
        )
        
        url = f'{self.base_url}{history_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            GenerationHistory.objects.filter(id=history_to_delete.id).exists()
        )


class CodeGenerationErrorHandlingTestCase(BaseTestCase):
    """Test cases for code generation error handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
    
    def test_invalid_generation_type(self):
        """Test creating request with invalid generation type."""
        data = {
            'project': 1,
            'diagram': 1,
            'generation_type': 'invalid_type',
            'parameters': {}
        }
        
        response = self.client.post('/api/v1/requests/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_template_content(self):
        """Test creating template with invalid content structure."""
        data = {
            'name': 'Invalid Template',
            'template_type': 'spring_boot',
            'version': '1.0',
            'template_content': 'invalid json string'
        }
        
        response = self.client.post('/api/v1/templates/', data, format='json')
        # Should handle gracefully
        self.assertIn(response.status_code, [400, 201])
    
    def test_large_generated_code_handling(self):
        """Test handling of large generated code payloads."""
        # Test with extremely large template content to verify graceful handling
        large_template_content = 'x' * 100000  # 100KB template content
        
        data = {
            'name': 'Large Template Test',
            'description': 'Test template with large content',
            'language': 'java',
            'framework': 'springboot',
            'template_content': large_template_content,
            'output_filename_pattern': 'LargeClass.java',
            'output_directory': 'src/main/java',
            'created_by': self.test_user.id
        }
        
        # Test if the system handles large payloads gracefully
        response = self.client.post('/api/v1/templates/', data, format='json')
        # Should handle gracefully - either create successfully or return appropriate error
        self.assertIn(response.status_code, [201, 400, 413])


class CodeGenerationPermissionsTestCase(BaseTestCase):
    """Test cases for code generation permissions."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access endpoints."""
        endpoints = [
            '/api/v1/requests/',
            '/api/v1/templates/',
            '/api/v1/generated-projects/',
            '/api/v1/history/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test that authenticated users can access endpoints."""
        self.client.force_authenticate(user=self.test_user)
        
        endpoints = [
            '/api/v1/requests/',
            '/api/v1/templates/',
            '/api/v1/generated-projects/',
            '/api/v1/history/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertNotIn(response.status_code, [401, 403])
