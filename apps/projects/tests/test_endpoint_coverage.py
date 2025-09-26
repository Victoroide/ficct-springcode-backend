"""
Comprehensive Unit Tests for Projects Endpoints

Tests for ALL projects endpoints including WorkspaceViewSet, ProjectViewSet,
ProjectTemplateViewSet, and nested ProjectMemberViewSet with full CRUD operations.
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
from apps.projects.models import Workspace, Project, ProjectMember, ProjectTemplate

User = get_user_model()


class WorkspaceViewSetTestCase(BaseTestCase):
    """Test cases for WorkspaceViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test workspace
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            description='Test workspace for projects',
            owner=self.test_user,
            is_active=True
        )
        
        self.base_url = '/api/v1/workspaces/'
    
    def test_list_workspaces_success(self):
        """Test GET /api/v1/workspaces/ returns list of workspaces."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_workspace_success(self):
        """Test POST /api/v1/workspaces/ creates new workspace."""
        data = {
            'name': 'New Test Workspace',
            'description': 'New workspace for testing',
            'is_active': True
        }
        
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Test Workspace')
        self.assertEqual(response.data['owner'], self.test_user.id)
    
    def test_create_workspace_missing_name(self):
        """Test creating workspace with missing name field."""
        data = {
            'description': 'Workspace without name'
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_workspace_success(self):
        """Test GET /api/v1/workspaces/{id}/ returns specific workspace."""
        url = f'{self.base_url}{self.workspace.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.workspace.id)
        self.assertEqual(response.data['name'], self.workspace.name)
    
    def test_update_workspace_success(self):
        """Test PATCH /api/v1/workspaces/{id}/ updates workspace."""
        url = f'{self.base_url}{self.workspace.id}/'
        data = {
            'name': 'Updated Workspace Name',
            'description': 'Updated description'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Workspace Name')
        self.assertEqual(response.data['description'], 'Updated description')
    
    def test_delete_workspace_success(self):
        """Test DELETE /api/v1/workspaces/{id}/ deletes workspace."""
        workspace_to_delete = Workspace.objects.create(
            name='Workspace to Delete',
            description='This workspace will be deleted',
            owner=self.test_user
        )
        
        url = f'{self.base_url}{workspace_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Workspace.objects.filter(id=workspace_to_delete.id).exists()
        )


class ProjectViewSetTestCase(BaseTestCase):
    """Test cases for ProjectViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test workspace and project
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            description='Test workspace for projects',
            owner=self.test_user
        )
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for endpoints',
            workspace=self.workspace,
            owner=self.test_user,
            status='ACTIVE'
        )
        self.base_url = '/api/v1/projects/'
    
    def test_list_projects_success(self):
        """Test GET /api/v1/projects/ returns list of projects."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_project_success(self):
        """Test POST /api/v1/projects/ creates new project."""
        data = {
            'name': 'New Test Project',
            'description': 'New project for testing',
            'workspace': self.workspace.id,
            'status': 'ACTIVE'
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Test Project')
        self.assertEqual(response.data['status'], 'ACTIVE')
        self.assertEqual(response.data['owner'], self.test_user.id)
    
    def test_create_project_missing_required_fields(self):
        """Test creating project with missing required fields."""
        data = {
            'name': 'Incomplete Project'
            # Missing workspace
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_project_success(self):
        """Test GET /api/v1/projects/{id}/ returns specific project."""
        url = f'{self.base_url}{self.project.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.project.id)
        self.assertEqual(response.data['name'], self.project.name)
    
    def test_update_project_success(self):
        """Test PATCH /api/v1/projects/{id}/ updates project."""
        url = f'{self.base_url}{self.project.id}/'
        data = {
            'name': 'Updated Project Name',
            'description': 'Updated project description',
            'status': 'completed'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Project Name')
        self.assertEqual(response.data['status'], 'completed')
    
    def test_delete_project_success(self):
        """Test DELETE /api/v1/projects/{id}/ deletes project."""
        project_to_delete = Project.objects.create(
            name='Project to Delete',
            description='This project will be deleted',
            workspace=self.workspace,
            owner=self.test_user
        )
        
        url = f'{self.base_url}{project_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Project.objects.filter(id=project_to_delete.id).exists()
        )
    
    def test_filter_projects_by_workspace(self):
        """Test filtering projects by workspace."""
        # Create another workspace and project
        other_workspace = Workspace.objects.create(
            name='Other Workspace',
            owner=self.test_user
        )
        other_project = Project.objects.create(
            name='Other Project',
            workspace=other_workspace,
            owner=self.test_user
        )
        
        # Filter by workspace
        response = self.client.get(f'{self.base_url}?workspace={self.workspace.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only projects from the specified workspace are returned
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            projects = data['results']
        else:
            projects = data
        
        for project in projects:
            self.assertEqual(project['workspace'], self.workspace.id)


class ProjectMemberViewSetTestCase(BaseTestCase):
    """Test cases for nested ProjectMemberViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test workspace and project
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            owner=self.test_user
        )
        
        self.project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.test_user
        )
        
        # Create test member
        self.member = ProjectMember.objects.create(
            project=self.project,
            user=self.test_user,
            role='owner',
            permissions=['read', 'write', 'admin']
        )
        
        # Nested URL pattern
        self.base_url = f'/api/v1/projects/{self.project.id}/members/'
    
    def test_list_members_success(self):
        """Test GET /api/v1/projects/{project_id}/members/ returns list of members."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_member_success(self):
        """Test POST /api/v1/projects/{project_id}/members/ creates new member."""
        # Create another user to add as member
        new_user = EnterpriseUserFactory()
        
        data = {
            'user': new_user.id,
            'role': 'developer',
            'permissions': ['read', 'write']
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], new_user.id)
        self.assertEqual(response.data['role'], 'developer')
        self.assertEqual(response.data['project'], self.project.id)
    
    def test_create_member_duplicate_user(self):
        """Test creating duplicate member."""
        data = {
            'user': self.test_user.id,
            'role': 'developer',
            'permissions': ['read']
        }
        
        response = self.client.post(self.base_url, data)
        
        # Should fail due to unique constraint
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_member_success(self):
        """Test GET /api/v1/projects/{project_id}/members/{id}/ returns specific member."""
        url = f'{self.base_url}{self.member.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.member.id)
        self.assertEqual(response.data['user'], self.test_user.id)
    
    def test_update_member_role(self):
        """Test updating member role and permissions."""
        url = f'{self.base_url}{self.member.id}/'
        data = {
            'role': 'developer',
            'permissions': ['read', 'write']
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'developer')
        self.assertEqual(response.data['permissions'], ['read', 'write'])
    
    def test_delete_member_success(self):
        """Test DELETE /api/v1/projects/{project_id}/members/{id}/ removes member."""
        # Create a member to delete
        new_user = EnterpriseUserFactory()
        member_to_delete = ProjectMember.objects.create(
            project=self.project,
            user=new_user,
            role='viewer',
            permissions=['read']
        )
        
        url = f'{self.base_url}{member_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ProjectMember.objects.filter(id=member_to_delete.id).exists()
        )
    
    def test_invalid_project_id_in_nested_url(self):
        """Test accessing members with invalid project ID."""
        invalid_url = '/api/v1/projects/99999/members/'
        response = self.client.get(invalid_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProjectTemplateViewSetTestCase(BaseTestCase):
    """Test cases for ProjectTemplateViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test template
        self.template = ProjectTemplate.objects.create(
            name='Spring Boot Template',
            description='Template for Spring Boot projects',
            template_type='spring_boot',
            configuration={
                'java_version': '17',
                'spring_boot_version': '3.0.0',
                'dependencies': ['web', 'jpa', 'security']
            },
            created_by=self.test_user,
            is_active=True
        )
        
        self.base_url = '/api/v1/templates/'
    
    def test_list_templates_success(self):
        """Test GET /api/v1/templates/ returns list of project templates."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_create_template_success(self):
        """Test POST /api/v1/templates/ creates new project template."""
        data = {
            'name': 'React App Template',
            'description': 'Template for React applications',
            'template_type': 'react_app',
            'configuration': {
                'node_version': '18',
                'react_version': '18.2.0',
                'packages': ['typescript', 'styled-components']
            },
            'is_active': True
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'React App Template')
        self.assertEqual(response.data['template_type'], 'react_app')
    
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
            'description': 'Updated Spring Boot template',
            'configuration': {
                'java_version': '21',
                'spring_boot_version': '3.2.0',
                'dependencies': ['web', 'jpa', 'security', 'actuator']
            }
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated Spring Boot template')
        self.assertEqual(response.data['configuration']['java_version'], '21')
    
    def test_delete_template_success(self):
        """Test DELETE /api/v1/templates/{id}/ deletes template."""
        template_to_delete = ProjectTemplate.objects.create(
            name='Template to Delete',
            template_type='spring_boot',
            configuration={},
            created_by=self.test_user
        )
        
        url = f'{self.base_url}{template_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ProjectTemplate.objects.filter(id=template_to_delete.id).exists()
        )


class ProjectsErrorHandlingTestCase(BaseTestCase):
    """Test cases for projects error handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
    
    def test_invalid_project_status(self):
        """Test creating project with invalid status."""
        data = {
            'name': 'Invalid Project',
            'workspace': 1,
            'status': 'invalid_status'
        }
        
        response = self.client.post('/api/v1/projects/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_member_permissions(self):
        """Test creating member with invalid permissions."""
        workspace = Workspace.objects.create(name='Test', owner=self.test_user)
        project = Project.objects.create(
            name='Test', workspace=workspace, owner=self.test_user
        )
        
        data = {
            'user': self.test_user.id,
            'role': 'developer',
            'permissions': ['invalid_permission']
        }
        
        response = self.client.post(f'/api/v1/projects/{project.id}/members/', data, format='json')
        # Should handle gracefully
        self.assertIn(response.status_code, [400, 201])
    
    def test_large_configuration_handling(self):
        """Test handling of large configuration objects."""
        large_config = {
            'dependencies': ['package' + str(i) for i in range(1000)],
            'settings': {f'setting_{i}': f'value_{i}' for i in range(100)}
        }
        
        data = {
            'name': 'Large Config Template',
            'template_type': 'spring_boot',
            'configuration': large_config
        }
        
        response = self.client.post('/api/v1/templates/', data, format='json')
        # Should handle gracefully
        self.assertIn(response.status_code, [201, 400, 413])


class ProjectsPermissionsTestCase(BaseTestCase):
    """Test cases for projects permissions."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access endpoints."""
        endpoints = [
            '/api/v1/workspaces/',
            '/api/v1/projects/',
            '/api/v1/templates/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test that authenticated users can access endpoints."""
        self.client.force_authenticate(user=self.test_user)
        
        endpoints = [
            '/api/v1/workspaces/',
            '/api/v1/projects/',
            '/api/v1/templates/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertNotIn(response.status_code, [401, 403])
    
    def test_project_member_access_control(self):
        """Test project member access control."""
        self.client.force_authenticate(user=self.test_user)
        
        # Create workspace and project
        workspace = Workspace.objects.create(name='Test', owner=self.test_user)
        project = Project.objects.create(
            name='Test', workspace=workspace, owner=self.test_user
        )
        
        # Test nested member endpoint access
        response = self.client.get(f'/api/v1/projects/{project.id}/members/')
        self.assertNotIn(response.status_code, [401, 403])


class ProjectsIntegrationTestCase(BaseTestCase):
    """Integration test cases for projects workflow."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
    
    def test_complete_project_workflow(self):
        """Test complete project creation and management workflow."""
        # 1. Create workspace
        workspace_data = {
            'name': 'Integration Test Workspace',
            'description': 'Workspace for integration testing',
            'is_active': True
        }
        
        workspace_response = self.client.post('/api/v1/workspaces/', workspace_data, format='json')
        self.assertEqual(workspace_response.status_code, status.HTTP_201_CREATED)
        workspace_id = workspace_response.data['id']
        
        # 2. Create project in workspace  
        project_data = {
            'name': 'Integration Test Project',
            'description': 'Project for integration testing',
            'workspace': workspace_id,
            'status': 'ACTIVE',
            'visibility': 'PRIVATE'
        }
        
        project_response = self.client.post('/api/v1/projects/', project_data, format='json')
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)
        project_id = project_response.data['id']
        
        # 3. Add member to project
        new_user = EnterpriseUserFactory()
        member_data = {
            'user': new_user.id,
            'role': 'developer',
            'permissions': ['read', 'write']
        }
        
        member_response = self.client.post(f'/api/v1/projects/{project_id}/members/', member_data, format='json')
        self.assertEqual(member_response.status_code, status.HTTP_201_CREATED)
        
        # 4. Create project template
        template_data = {
            'name': 'Integration Test Template',
            'description': 'Template for integration testing',
            'template_type': 'spring_boot',
            'configuration': {'java_version': '17'},
            'is_active': True
        }
        
        template_response = self.client.post('/api/v1/templates/', template_data, format='json')
        self.assertEqual(template_response.status_code, status.HTTP_201_CREATED)
        
        # 5. Verify all components exist and are linked
        # Check workspace exists
        workspace_check = self.client.get(f'/api/v1/workspaces/{workspace_id}/')
        self.assertEqual(workspace_check.status_code, status.HTTP_200_OK)
        
        # Check project exists
        project_check = self.client.get(f'/api/v1/projects/{project_id}/')
        self.assertEqual(project_check.status_code, status.HTTP_200_OK)
        self.assertEqual(project_check.data['workspace'], workspace_id)
        
        # Check member exists
        members_check = self.client.get(f'/api/v1/projects/{project_id}/members/')
        self.assertEqual(members_check.status_code, status.HTTP_200_OK)
