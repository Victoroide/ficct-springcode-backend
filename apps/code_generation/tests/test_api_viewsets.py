"""
Tests for Code Generation API ViewSets.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, Mock
import json

from ..models import GenerationRequest, GenerationTemplate, GeneratedProject, GenerationHistory
from apps.projects.models import Project, Workspace

User = get_user_model()


class GenerationRequestViewSetTestCase(TestCase):
    """Test cases for GenerationRequestViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create workspace and project
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        self.project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        # Create template
        self.template = GenerationTemplate.objects.create(
            name='Basic Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='{{ class_name }}'
        )
    
    def test_create_generation_request(self):
        """Test creating a new generation request."""
        data = {
            'project': self.project.id,
            'template': self.template.id,
            'uml_data': {'classes': [{'name': 'User'}]},
            'springboot_config': {
                'group_id': 'com.example',
                'artifact_id': 'test-app'
            }
        }
        
        url = reverse('code_generation:generationrequest-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GenerationRequest.objects.count(), 1)
        
        request = GenerationRequest.objects.first()
        self.assertEqual(request.project, self.project)
        self.assertEqual(request.template, self.template)
        self.assertEqual(request.created_by, self.user)
    
    def test_list_generation_requests(self):
        """Test listing generation requests."""
        # Create test requests
        GenerationRequest.objects.create(
            project=self.project,
            template=self.template,
            created_by=self.user,
            uml_data={'classes': []},
            springboot_config={'group_id': 'com.example'}
        )
        
        url = reverse('code_generation:generationrequest-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    @patch('apps.code_generation.services.code_generation_service.CodeGenerationService.start_generation')
    def test_start_generation(self, mock_start):
        """Test starting generation process."""
        request = GenerationRequest.objects.create(
            project=self.project,
            template=self.template,
            created_by=self.user,
            uml_data={'classes': []},
            springboot_config={'group_id': 'com.example'}
        )
        
        mock_start.return_value = True
        
        url = reverse('code_generation:generationrequest-start-generation', args=[request.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_start.assert_called_once()
    
    def test_unauthorized_access(self):
        """Test unauthorized access to generation requests."""
        self.client.force_authenticate(user=None)
        
        url = reverse('code_generation:generationrequest-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class GenerationTemplateViewSetTestCase(TestCase):
    """Test cases for GenerationTemplateViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_template(self):
        """Test creating a new template."""
        data = {
            'name': 'Test Template',
            'category': 'ENTITY',
            'template_type': 'BASIC',
            'template_content': 'public class {{ class_name }} {}',
            'variables': {'class_name': 'string'},
            'is_public': True
        }
        
        url = reverse('code_generation:generationtemplate-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GenerationTemplate.objects.count(), 1)
        
        template = GenerationTemplate.objects.first()
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.author, self.user)
    
    def test_validate_template(self):
        """Test template validation endpoint."""
        template = GenerationTemplate.objects.create(
            name='Test Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} {}'
        )
        
        data = {'variables': {'class_name': 'User'}}
        
        url = reverse('code_generation:generationtemplate-validate', args=[template.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rendered_content', response.data)
    
    def test_clone_template(self):
        """Test template cloning."""
        original = GenerationTemplate.objects.create(
            name='Original Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} {}'
        )
        
        data = {'name': 'Cloned Template'}
        
        url = reverse('code_generation:generationtemplate-clone', args=[original.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GenerationTemplate.objects.count(), 2)
        
        cloned = GenerationTemplate.objects.exclude(id=original.id).first()
        self.assertEqual(cloned.name, 'Cloned Template')
        self.assertEqual(cloned.template_content, original.template_content)


class GeneratedProjectViewSetTestCase(TestCase):
    """Test cases for GeneratedProjectViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create dependencies
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        project = Project.objects.create(
            name='Test Project',
            workspace=workspace,
            owner=self.user
        )
        template = GenerationTemplate.objects.create(
            name='Test Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user
        )
        
        self.generation_request = GenerationRequest.objects.create(
            project=project,
            template=template,
            created_by=self.user,
            uml_data={'classes': []},
            springboot_config={'group_id': 'com.example'}
        )
    
    def test_list_generated_projects(self):
        """Test listing generated projects."""
        GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-project',
            file_path='/tmp/test-project.zip',
            file_size=1024,
            created_by=self.user
        )
        
        url = reverse('code_generation:generatedproject-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    @patch('django.http.FileResponse')
    def test_download_project(self, mock_file_response):
        """Test downloading generated project."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-project',
            file_path='/tmp/test-project.zip',
            file_size=1024,
            created_by=self.user
        )
        
        mock_file_response.return_value = Mock()
        
        url = reverse('code_generation:generatedproject-download', args=[project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CodeGenerationAPIPermissionsTestCase(TestCase):
    """Test permission handling in code generation APIs."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        # Create users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        
        # Create workspace and project owned by owner
        self.workspace = Workspace.objects.create(
            name='Owner Workspace',
            workspace_type='PERSONAL',
            owner=self.owner
        )
        self.project = Project.objects.create(
            name='Owner Project',
            workspace=self.workspace,
            owner=self.owner
        )
        
        # Create template by owner
        self.template = GenerationTemplate.objects.create(
            name='Owner Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.owner,
            is_public=False
        )
    
    def test_owner_can_access_resources(self):
        """Test that owner can access their resources."""
        self.client.force_authenticate(user=self.owner)
        
        # Create generation request
        data = {
            'project': self.project.id,
            'template': self.template.id,
            'uml_data': {'classes': []},
            'springboot_config': {'group_id': 'com.example'}
        }
        
        url = reverse('code_generation:generationrequest-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_other_user_cannot_access_private_resources(self):
        """Test that other users cannot access private resources."""
        self.client.force_authenticate(user=self.other_user)
        
        # Try to use owner's private template
        data = {
            'project': self.project.id,  # This should fail validation
            'template': self.template.id,  # This should fail validation
            'uml_data': {'classes': []},
            'springboot_config': {'group_id': 'com.example'}
        }
        
        url = reverse('code_generation:generationrequest-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_public_template_access(self):
        """Test access to public templates."""
        # Make template public
        self.template.is_public = True
        self.template.save()
        
        self.client.force_authenticate(user=self.other_user)
        
        url = reverse('code_generation:generationtemplate-detail', args=[self.template.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CodeGenerationAPIFilteringTestCase(TestCase):
    """Test filtering and searching in code generation APIs."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create multiple templates
        GenerationTemplate.objects.create(
            name='Entity Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        GenerationTemplate.objects.create(
            name='Repository Template',
            category='REPOSITORY',
            template_type='ADVANCED',
            author=self.user,
            is_public=True
        )
    
    def test_filter_templates_by_category(self):
        """Test filtering templates by category."""
        url = reverse('code_generation:generationtemplate-list')
        response = self.client.get(url, {'category': 'ENTITY'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['category'], 'ENTITY')
    
    def test_search_templates_by_name(self):
        """Test searching templates by name."""
        url = reverse('code_generation:generationtemplate-list')
        response = self.client.get(url, {'search': 'Entity'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Entity', response.data['results'][0]['name'])
    
    def test_order_templates(self):
        """Test ordering templates."""
        url = reverse('code_generation:generationtemplate-list')
        response = self.client.get(url, {'ordering': '-created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return results in descending order of creation
