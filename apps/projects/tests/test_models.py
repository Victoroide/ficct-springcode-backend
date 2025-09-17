"""
Tests for Projects app models - Project, ProjectMember, Workspace, ProjectTemplate.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
import uuid

from ..models import Project, ProjectMember, Workspace, ProjectTemplate

User = get_user_model()


class WorkspaceModelTestCase(TestCase):
    """Test cases for Workspace model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_workspace_creation(self):
        """Test basic workspace creation."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            description='A test workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        self.assertEqual(workspace.name, 'Test Workspace')
        self.assertEqual(workspace.workspace_type, 'TEAM')
        self.assertEqual(workspace.owner, self.user)
        self.assertEqual(workspace.status, 'ACTIVE')
        self.assertTrue(workspace.is_active)
    
    def test_workspace_str_representation(self):
        """Test workspace string representation."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        expected_str = f'Test Workspace (PERSONAL) - {self.user.username}'
        self.assertEqual(str(workspace), expected_str)
    
    def test_workspace_resource_limits_default(self):
        """Test default resource limits."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        self.assertIsNotNone(workspace.resource_limits)
        self.assertIn('max_projects', workspace.resource_limits)
        self.assertIn('max_members', workspace.resource_limits)
        self.assertIn('storage_limit_gb', workspace.resource_limits)
    
    def test_workspace_can_user_access(self):
        """Test user access permissions."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        # Owner should have access
        self.assertTrue(workspace.can_user_access(self.user))
        
        # Other users should not have access to personal workspace
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.assertFalse(workspace.can_user_access(other_user))
    
    def test_workspace_project_count(self):
        """Test project count methods."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
        
        # Create projects
        Project.objects.create(
            name='Active Project',
            workspace=workspace,
            owner=self.user,
            status='ACTIVE'
        )
        Project.objects.create(
            name='Archived Project',
            workspace=workspace,
            owner=self.user,
            status='ARCHIVED'
        )
        
        self.assertEqual(workspace.get_project_count(), 2)
        self.assertEqual(workspace.get_active_project_count(), 1)
        self.assertEqual(workspace.get_archived_project_count(), 1)
    
    def test_workspace_soft_delete(self):
        """Test workspace soft deletion."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        workspace.soft_delete()
        
        self.assertTrue(workspace.is_deleted)
        self.assertIsNotNone(workspace.deleted_at)
    
    def test_workspace_archive_restore(self):
        """Test workspace archive and restore."""
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        # Archive
        workspace.archive()
        self.assertEqual(workspace.status, 'ARCHIVED')
        
        # Restore
        workspace.restore()
        self.assertEqual(workspace.status, 'ACTIVE')


class ProjectModelTestCase(TestCase):
    """Test cases for Project model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.user
        )
    
    def test_project_creation(self):
        """Test basic project creation."""
        project = Project.objects.create(
            name='Test Project',
            description='A test project',
            workspace=self.workspace,
            owner=self.user
        )
        
        self.assertEqual(project.name, 'Test Project')
        self.assertEqual(project.workspace, self.workspace)
        self.assertEqual(project.owner, self.user)
        self.assertEqual(project.status, 'ACTIVE')
        self.assertEqual(project.visibility, 'PRIVATE')
    
    def test_project_str_representation(self):
        """Test project string representation."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        expected_str = f'Test Project - {self.workspace.name}'
        self.assertEqual(str(project), expected_str)
    
    def test_project_springboot_config_default(self):
        """Test default SpringBoot configuration."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        self.assertIsNotNone(project.springboot_config)
        self.assertIn('group_id', project.springboot_config)
        self.assertIn('artifact_id', project.springboot_config)
        self.assertIn('java_version', project.springboot_config)
    
    def test_project_permissions(self):
        """Test project permission methods."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        # Owner permissions
        self.assertTrue(project.can_user_view(self.user))
        self.assertTrue(project.can_user_edit(self.user))
        self.assertTrue(project.can_user_delete(self.user))
        self.assertTrue(project.can_user_manage_members(self.user))
        
        # Other user permissions
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.assertFalse(project.can_user_view(other_user))
        self.assertFalse(project.can_user_edit(other_user))
        self.assertFalse(project.can_user_delete(other_user))
    
    def test_project_public_visibility(self):
        """Test public project visibility."""
        project = Project.objects.create(
            name='Public Project',
            workspace=self.workspace,
            owner=self.user,
            visibility='PUBLIC'
        )
        
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Public projects should be viewable by anyone
        self.assertTrue(project.can_user_view(other_user))
        self.assertFalse(project.can_user_edit(other_user))
    
    def test_project_member_count(self):
        """Test project member count methods."""
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
        
        ProjectMember.objects.create(
            project=project,
            user=User.objects.create_user(
                username='pending',
                email='pending@example.com',
                password='testpass123'
            ),
            role='VIEWER',
            status='PENDING'
        )
        
        self.assertEqual(project.get_member_count(), 2)
        self.assertEqual(project.get_active_member_count(), 1)
        self.assertEqual(project.get_pending_member_count(), 1)
    
    def test_project_activity_update(self):
        """Test project activity tracking."""
        project = Project.objects.create(
            name='Test Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        original_activity = project.last_activity_at
        
        # Update activity
        project.update_activity()
        
        self.assertGreater(project.last_activity_at, original_activity)


class ProjectMemberModelTestCase(TestCase):
    """Test cases for ProjectMember model."""
    
    def setUp(self):
        """Set up test fixtures."""
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
    
    def test_project_member_creation(self):
        """Test basic project member creation."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            invited_by=self.owner
        )
        
        self.assertEqual(member.project, self.project)
        self.assertEqual(member.user, self.member)
        self.assertEqual(member.role, 'EDITOR')
        self.assertEqual(member.status, 'PENDING')
        self.assertEqual(member.invited_by, self.owner)
    
    def test_project_member_str_representation(self):
        """Test project member string representation."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR'
        )
        
        expected_str = f'{self.member.username} - {self.project.name} (EDITOR)'
        self.assertEqual(str(member), expected_str)
    
    def test_project_member_unique_constraint(self):
        """Test unique constraint on project-user combination."""
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR'
        )
        
        # Should not be able to create duplicate membership
        with self.assertRaises(IntegrityError):
            ProjectMember.objects.create(
                project=self.project,
                user=self.member,
                role='VIEWER'
            )
    
    def test_invitation_acceptance(self):
        """Test invitation acceptance."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='PENDING'
        )
        
        member.accept_invitation()
        
        self.assertEqual(member.status, 'ACTIVE')
        self.assertIsNotNone(member.joined_at)
    
    def test_invitation_decline(self):
        """Test invitation decline."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='PENDING'
        )
        
        member.decline_invitation()
        
        self.assertEqual(member.status, 'DECLINED')
    
    def test_invitation_expiration(self):
        """Test invitation expiration."""
        # Create expired invitation
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='PENDING'
        )
        
        # Set expiration to past
        member.invitation_expires_at = timezone.now() - timedelta(days=1)
        member.save()
        
        self.assertTrue(member.has_invitation_expired())
    
    def test_member_activity_update(self):
        """Test member activity tracking."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='ACTIVE'
        )
        
        original_activity = member.last_activity_at
        
        member.update_activity()
        
        self.assertGreater(member.last_activity_at, original_activity)
    
    def test_effective_permissions(self):
        """Test effective permissions calculation."""
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role='EDITOR',
            status='ACTIVE'
        )
        
        permissions = member.get_effective_permissions()
        
        self.assertIsInstance(permissions, dict)
        self.assertIn('can_view', permissions)
        self.assertIn('can_edit', permissions)
        self.assertIn('can_manage_members', permissions)
        
        # Editor should have edit permissions but not member management
        self.assertTrue(permissions['can_edit'])
        self.assertFalse(permissions['can_manage_members'])


class ProjectTemplateModelTestCase(TestCase):
    """Test cases for ProjectTemplate model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_project_template_creation(self):
        """Test basic project template creation."""
        template = ProjectTemplate.objects.create(
            name='Web Application Template',
            description='A template for web applications',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        self.assertEqual(template.name, 'Web Application Template')
        self.assertEqual(template.category, 'WEB_APPLICATION')
        self.assertEqual(template.author, self.user)
        self.assertTrue(template.is_public)
    
    def test_template_str_representation(self):
        """Test template string representation."""
        template = ProjectTemplate.objects.create(
            name='API Template',
            category='REST_API',
            template_type='ADVANCED',
            author=self.user
        )
        
        expected_str = f'API Template (REST_API) by {self.user.username}'
        self.assertEqual(str(template), expected_str)
    
    def test_template_springboot_config_default(self):
        """Test default SpringBoot configuration in template."""
        template = ProjectTemplate.objects.create(
            name='Test Template',
            category='CUSTOM',
            template_type='BASIC',
            author=self.user
        )
        
        self.assertIsNotNone(template.springboot_config)
        self.assertIn('group_id', template.springboot_config)
        self.assertIn('java_version', template.springboot_config)
    
    def test_template_accessibility(self):
        """Test template accessibility."""
        # Public template
        public_template = ProjectTemplate.objects.create(
            name='Public Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=True
        )
        
        # Private template
        private_template = ProjectTemplate.objects.create(
            name='Private Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            is_public=False
        )
        
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Author should access both
        self.assertTrue(public_template.is_accessible_by_user(self.user))
        self.assertTrue(private_template.is_accessible_by_user(self.user))
        
        # Other user should only access public
        self.assertTrue(public_template.is_accessible_by_user(other_user))
        self.assertFalse(private_template.is_accessible_by_user(other_user))
    
    def test_template_usage_increment(self):
        """Test template usage tracking."""
        template = ProjectTemplate.objects.create(
            name='Test Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user
        )
        
        original_count = template.usage_count
        original_last_used = template.last_used_at
        
        template.increment_usage()
        
        self.assertEqual(template.usage_count, original_count + 1)
        if original_last_used:
            self.assertGreater(template.last_used_at, original_last_used)
        else:
            self.assertIsNotNone(template.last_used_at)
    
    def test_template_validation(self):
        """Test template configuration validation."""
        template = ProjectTemplate.objects.create(
            name='Test Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            springboot_config={
                'group_id': 'com.example',
                'artifact_id': 'test-app',
                'java_version': '17'
            },
            uml_template_data={
                'classes': [],
                'relationships': []
            }
        )
        
        # Should not raise exception for valid template
        try:
            template.validate_template()
        except Exception:
            self.fail("Template validation raised exception for valid template")
    
    def test_template_clone_metadata(self):
        """Test template cloning support."""
        original = ProjectTemplate.objects.create(
            name='Original Template',
            category='WEB_APPLICATION',
            template_type='BASIC',
            author=self.user,
            springboot_config={
                'group_id': 'com.example',
                'artifact_id': 'original'
            }
        )
        
        # Simulate cloning
        clone_data = original.get_clone_data()
        
        self.assertIn('springboot_config', clone_data)
        self.assertIn('uml_template_data', clone_data)
        self.assertIn('collaboration_settings', clone_data)
        
        # Original data should be preserved
        self.assertEqual(
            clone_data['springboot_config']['group_id'],
            'com.example'
        )


class ProjectModelRelationshipTestCase(TestCase):
    """Test cases for model relationships and complex interactions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
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
    
    def test_workspace_project_cascade_delete(self):
        """Test cascade delete from workspace to projects."""
        project_id = self.project.id
        
        # Soft delete workspace
        self.workspace.soft_delete()
        
        # Projects should also be soft deleted
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_deleted)
    
    def test_project_member_cleanup_on_project_delete(self):
        """Test member cleanup when project is deleted."""
        member_user = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='testpass123'
        )
        
        member = ProjectMember.objects.create(
            project=self.project,
            user=member_user,
            role='EDITOR'
        )
        
        member_id = member.id
        
        # Delete project
        self.project.delete()
        
        # Member should be deleted
        with self.assertRaises(ProjectMember.DoesNotExist):
            ProjectMember.objects.get(id=member_id)
    
    def test_workspace_resource_limit_enforcement(self):
        """Test workspace resource limit enforcement."""
        # Set low project limit
        self.workspace.resource_limits['max_projects'] = 1
        self.workspace.save()
        
        # First project already exists, should be at limit
        self.assertTrue(self.workspace.is_at_project_limit())
        
        # Should not be able to create another project
        self.assertFalse(self.workspace.can_user_create_project(self.owner))
    
    def test_project_statistics_aggregation(self):
        """Test project statistics aggregation."""
        # Add members
        for i in range(3):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            ProjectMember.objects.create(
                project=self.project,
                user=user,
                role='EDITOR',
                status='ACTIVE'
            )
        
        # Get statistics
        stats = self.project.get_project_statistics()
        
        self.assertIn('member_count', stats)
        self.assertIn('role_distribution', stats)
        self.assertEqual(stats['member_count'], 3)
    
    def test_cross_workspace_project_access(self):
        """Test project access across different workspaces."""
        # Create another workspace and project
        other_user = User.objects.create_user(
            username='otherowner',
            email='other@example.com',
            password='testpass123'
        )
        
        other_workspace = Workspace.objects.create(
            name='Other Workspace',
            workspace_type='PERSONAL',
            owner=other_user
        )
        
        other_project = Project.objects.create(
            name='Other Project',
            workspace=other_workspace,
            owner=other_user,
            visibility='PUBLIC'
        )
        
        # Owner of first workspace should not have edit access to other project
        self.assertTrue(other_project.can_user_view(self.owner))  # Public
        self.assertFalse(other_project.can_user_edit(self.owner))  # Different owner
        self.assertFalse(other_project.can_user_manage_members(self.owner))  # Different owner
