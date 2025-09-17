"""
Tests for Projects API ViewSets.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, Mock
import json

from ..models import Project, ProjectMember, Workspace, ProjectTemplate

User = get_user_model()


class ProjectViewSetTestCase(TestCase):
    """Test cases for ProjectViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
    
    def test_create_project(self):
        """Test creating a new project."""
        data = {
            'name': 'Test Project',
            'description': 'A test project',
            'workspace': self.workspace.id,
            'visibility': 'PRIVATE',
            'springboot_config': {
                'group_id': 'com.example',
                'artifact_id': 'test-project',
                'java_version': '17'
            }
        }
        
        url = reverse('projects:project-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 1)
        
        project = Project.objects.first()
        self.assertEqual(project.name, 'Test Project')
        self.assertEqual(project.owner, self.user)
        self.assertEqual(project.workspace, self.workspace)
    
    def test_list_projects(self):
        """Test listing user's projects."""
        # Create projects
        Project.objects.create(
            name='Project 1',
            workspace=self.workspace,
            owner=self.user
        )
        Project.objects.create(
            name='Project 2',
            workspace=self.workspace,
            owner=self.user,
            status='ARCHIVED'
        )
        
        url = reverse('projects:project-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_project_detail(self):
        """Test retrieving project details."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        url = reverse('projects:project-detail', args=[project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Project')
    
    def test_invite_user_to_project(self):
        """Test inviting user to project."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        invited_user = User.objects.create_user(
            username='invited',
            email='invited@example.com',
            password='testpass123'
        )
        
        data = {
            'user_id': invited_user.id,
            'role': 'EDITOR'
        }
        
        url = reverse('projects:project-invite-user', args=[project.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ProjectMember.objects.filter(
            project=project,
            user=invited_user,
            role='EDITOR'
        ).exists())
    
    def test_clone_project(self):
        """Test cloning a project."""
        original = Project.objects.create(
            name='Original Project',
            workspace=self.workspace,
            owner=self.user,
            description='Original description'
        )
        
        data = {'name': 'Cloned Project'}
        
        url = reverse('projects:project-clone', args=[original.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 2)
        
        cloned = Project.objects.exclude(id=original.id).first()
        self.assertEqual(cloned.name, 'Cloned Project')
        self.assertEqual(cloned.description, original.description)
    
    def test_archive_project(self):
        """Test archiving a project."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        url = reverse('projects:project-archive', args=[project.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, 'ARCHIVED')
    
    def test_project_statistics(self):
        """Test project statistics endpoint."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        # Add members
        member_user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='testpass123'
        )
        ProjectMember.objects.create(
            project=project,
            user=member_user,
            role='EDITOR',
            status='ACTIVE'
        )
        
        url = reverse('projects:project-statistics', args=[project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('member_count', response.data)
        self.assertIn('role_distribution', response.data)


class ProjectMemberViewSetTestCase(TestCase):
    """Test cases for ProjectMemberViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='testpass123'
        )
        
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.owner
        )
        
        self.project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.owner
        )
        
        self.client.force_authenticate(user=self.owner)
    
    def test_list_project_members(self):
        """Test listing project members."""
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='ACTIVE'
        )
        
        url = reverse('projects:project-members-list', args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_add_project_member(self):
        """Test adding a project member."""
        data = {
            'user': self.member.id,
            'role': 'EDITOR'
        }
        
        url = reverse('projects:project-members-list', args=[self.project.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ProjectMember.objects.filter(
            project=self.project,
            user=self.member,
            role='EDITOR'
        ).exists())
    
    def test_update_member_role(self):
        """Test updating member role."""
        member_obj = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='VIEWER',
            status='ACTIVE'
        )
        
        data = {'role': 'EDITOR'}
        
        url = reverse('projects:project-members-detail', args=[self.project.id, member_obj.id])
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member_obj.refresh_from_db()
        self.assertEqual(member_obj.role, 'EDITOR')
    
    def test_accept_invitation(self):
        """Test accepting project invitation."""
        member_obj = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='PENDING'
        )
        
        # Switch to member user
        self.client.force_authenticate(user=self.member)
        
        url = reverse('projects:project-members-accept-invitation', args=[self.project.id, member_obj.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member_obj.refresh_from_db()
        self.assertEqual(member_obj.status, 'ACTIVE')
    
    def test_bulk_member_actions(self):
        """Test bulk member actions."""
        member1 = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='ACTIVE'
        )
        
        member2_user = User.objects.create_user(
            username='member2',
            email='member2@example.com',
            password='testpass123'
        )
        member2 = ProjectMember.objects.create(
            project=self.project,
            user=member2_user,
            role='VIEWER',
            status='ACTIVE'
        )
        
        data = {
            'action': 'update_role',
            'member_ids': [member1.id, member2.id],
            'role': 'EDITOR'
        }
        
        url = reverse('projects:project-members-bulk-actions', args=[self.project.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        member1.refresh_from_db()
        member2.refresh_from_db()
        self.assertEqual(member1.role, 'EDITOR')
        self.assertEqual(member2.role, 'EDITOR')


class WorkspaceViewSetTestCase(TestCase):
    """Test cases for WorkspaceViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_workspace(self):
        """Test creating a new workspace."""
        data = {
            'name': 'Test Workspace',
            'description': 'A test workspace',
            'workspace_type': 'TEAM'
        }
        
        url = reverse('projects:workspace-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Workspace.objects.count(), 1)
        
        workspace = Workspace.objects.first()
        self.assertEqual(workspace.name, 'Test Workspace')
        self.assertEqual(workspace.owner, self.user)
    
    def test_list_workspaces(self):
        """Test listing user's workspaces."""
        Workspace.objects.create(
            name='Personal Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        Workspace.objects.create(
            name='Team Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        url = reverse('projects:workspace-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_workspace_projects(self):
        """Test listing workspace projects."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        # Create projects
        Project.objects.create(
            name='Project 1',
            workspace=workspace,
            owner=self.user
        )
        Project.objects.create(
            name='Project 2',
            workspace=workspace,
            owner=self.user
        )
        
        url = reverse('projects:workspace-projects', args=[workspace.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_workspace_usage_report(self):
        """Test workspace usage report."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        url = reverse('projects:workspace-usage-report', args=[workspace.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('project_count', response.data)
        self.assertIn('storage_usage', response.data)
    
    def test_transfer_ownership(self):
        """Test transferring workspace ownership."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        new_owner = User.objects.create_user(
            username='newowner',
            email='newowner@example.com',
            password='testpass123'
        )
        
        data = {'new_owner_id': new_owner.id}
        
        url = reverse('projects:workspace-transfer-ownership', args=[workspace.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workspace.refresh_from_db()
        self.assertEqual(workspace.owner, new_owner)


class ProjectTemplateViewSetTestCase(TestCase):
    """Test cases for ProjectTemplateViewSet."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_project_template(self):
        """Test creating a project template."""
        data = {
            'name': 'Web App Template',
            'description': 'Template for web applications',
            'category': 'WEB_APPLICATION',
            'template_type': 'BASIC',
            'is_public': True,
            'springboot_config': {
                'group_id': 'com.example',
                'java_version': '17'
            },
            'uml_template_data': {
                'classes': [],
                'relationships': []
            }
        }
        
        url = reverse('projects:projecttemplate-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectTemplate.objects.count(), 1)
        
        template = ProjectTemplate.objects.first()
        self.assertEqual(template.name, 'Web App Template')
        self.assertEqual(template.author, self.user)
    
    def test_list_public_templates(self):
        """Test listing public templates."""
        # Create public template
        ProjectTemplate.objects.create(
            name='Public Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        # Create private template
        ProjectTemplate.objects.create(
            name='Private Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=False
        )
        
        url = reverse('projects:projecttemplate-list')
        response = self.client.get(url, {'is_public': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Public Template')
    
    def test_clone_template(self):
        """Test cloning a template."""
        original = ProjectTemplate.objects.create(
            name='Original Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        data = {'name': 'Cloned Template'}
        
        url = reverse('projects:projecttemplate-clone', args=[original.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectTemplate.objects.count(), 2)
        
        cloned = ProjectTemplate.objects.exclude(id=original.id).first()
        self.assertEqual(cloned.name, 'Cloned Template')
        self.assertEqual(cloned.author, self.user)
    
    def test_rate_template(self):
        """Test rating a template."""
        template = ProjectTemplate.objects.create(
            name='Test Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        data = {'rating': 5}
        
        url = reverse('projects:projecttemplate-rate', args=[template.id])
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_search_templates(self):
        """Test searching templates."""
        ProjectTemplate.objects.create(
            name='Web Application Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        ProjectTemplate.objects.create(
            name='REST API Template',
            category='REST_API',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        url = reverse('projects:projecttemplate-search')
        response = self.client.get(url, {'query': 'web'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Web', response.data['results'][0]['name'])
    
    def test_featured_templates(self):
        """Test featured templates endpoint."""
        template = ProjectTemplate.objects.create(
            name='Featured Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True,
            is_featured=True
        )
        
        url = reverse('projects:projecttemplate-featured')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue(response.data['results'][0]['is_featured'])


class ProjectAPIPermissionsTestCase(TestCase):
    """Test permission handling in projects APIs."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
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
        
        self.workspace = Workspace.objects.create(
            name='Owner Workspace',
            workspace_type='PERSONAL',
            owner=self.owner
        )
        
        self.project = Project.objects.create(
            name='Owner Project',
            workspace=self.workspace,
            owner=self.owner,
            visibility='PRIVATE'
        )
    
    def test_owner_can_access_project(self):
        """Test that owner can access their project."""
        self.client.force_authenticate(user=self.owner)
        
        url = reverse('projects:project-detail', args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_other_user_cannot_access_private_project(self):
        """Test that other users cannot access private project."""
        self.client.force_authenticate(user=self.other_user)
        
        url = reverse('projects:project-detail', args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_public_project_visibility(self):
        """Test public project visibility."""
        self.project.visibility = 'PUBLIC'
        self.project.save()
        
        self.client.force_authenticate(user=self.other_user)
        
        url = reverse('projects:project-detail', args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # But other user still cannot edit
        data = {'name': 'Modified Name'}
        response = self.client.patch(url, data, format='json')
        
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
    
    def test_project_member_permissions(self):
        """Test project member permissions."""
        # Add other_user as member
        ProjectMember.objects.create(
            project=self.project,
            user=self.other_user,
            role='EDITOR',
            status='ACTIVE'
        )
        
        self.client.force_authenticate(user=self.other_user)
        
        # Member should be able to view and edit
        url = reverse('projects:project-detail', args=[self.project.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Member should be able to edit (depending on role)
        data = {'description': 'Updated by member'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
