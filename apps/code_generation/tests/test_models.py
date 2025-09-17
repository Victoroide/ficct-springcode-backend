"""
Tests for Code Generation app models.
Comprehensive testing of GenerationRequest, GenerationTemplate, GeneratedProject, and GenerationHistory models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
import uuid

from ..models import GenerationRequest, GenerationTemplate, GeneratedProject, GenerationHistory
from apps.projects.models import Project, Workspace
from apps.uml_diagrams.models import UMLDiagram
from base.test_base import BaseTestCase

User = get_user_model()


class GenerationRequestModelTestCase(BaseTestCase):
    """Test cases for GenerationRequest model."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
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
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user,
            diagram_data={
                'classes': [
                    {'id': '1', 'name': 'User', 'attributes': [], 'methods': []},
                    {'id': '2', 'name': 'Order', 'attributes': [], 'methods': []}
                ],
                'relationships': []
            }
        )
    
    def test_generation_request_creation(self):
        """Test basic generation request creation."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            generation_type='FULL_PROJECT'
        )
        
        self.assertEqual(request.project, self.project)
        self.assertEqual(request.diagram, self.diagram)
        self.assertEqual(request.requested_by, self.user)
        self.assertEqual(request.generation_type, 'FULL_PROJECT')
        self.assertEqual(request.status, 'PENDING')
        self.assertEqual(request.progress_percentage, 0)
        self.assertIsInstance(request.id, uuid.UUID)
    
    def test_generation_request_str_representation(self):
        """Test generation request string representation."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            generation_type='ENTITIES_ONLY'
        )
        
        expected_str = f"Generation {request.id} - JPA Entities Only"
        self.assertEqual(str(request), expected_str)
    
    def test_start_generation(self):
        """Test starting generation process."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        self.assertIsNone(request.started_at)
        
        request.start_generation()
        
        self.assertEqual(request.status, 'PROCESSING')
        self.assertIsNotNone(request.started_at)
    
    def test_complete_generation(self):
        """Test completing generation process."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        request.start_generation()
        
        output_path = '/tmp/generated_project'
        files_count = 25
        download_url = 'https://example.com/download/project.zip'
        
        request.complete_generation(output_path, files_count, download_url)
        
        self.assertEqual(request.status, 'COMPLETED')
        self.assertEqual(request.output_path, output_path)
        self.assertEqual(request.generated_files_count, files_count)
        self.assertEqual(request.progress_percentage, 100)
        self.assertEqual(request.download_url, download_url)
        self.assertIsNotNone(request.completed_at)
        self.assertIsNotNone(request.download_expires_at)
    
    def test_fail_generation(self):
        """Test failing generation process."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        request.start_generation()
        
        error_details = {
            'error_type': 'TEMPLATE_ERROR',
            'message': 'Invalid template syntax',
            'stack_trace': 'Template error at line 15...'
        }
        
        request.fail_generation(error_details)
        
        self.assertEqual(request.status, 'FAILED')
        self.assertEqual(request.error_details, error_details)
        self.assertIsNotNone(request.completed_at)
    
    def test_cancel_generation(self):
        """Test canceling generation process."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        request.start_generation()
        
        request.cancel_generation()
        
        self.assertEqual(request.status, 'CANCELLED')
        self.assertIsNotNone(request.completed_at)
    
    def test_cancel_generation_invalid_status(self):
        """Test canceling generation with invalid status."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        request.complete_generation('/tmp/output', 10)
        
        old_status = request.status
        request.cancel_generation()
        
        # Should not change status if already completed
        self.assertEqual(request.status, old_status)
    
    def test_update_progress(self):
        """Test updating generation progress."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        details = {'current_step': 'Generating entities', 'files_processed': 5}
        request.update_progress(45, details)
        
        self.assertEqual(request.progress_percentage, 45)
        self.assertEqual(request.progress_details['current_step'], 'Generating entities')
        self.assertEqual(request.progress_details['files_processed'], 5)
    
    def test_update_progress_bounds(self):
        """Test progress percentage bounds validation."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        # Test lower bound
        request.update_progress(-10)
        self.assertEqual(request.progress_percentage, 0)
        
        # Test upper bound
        request.update_progress(150)
        self.assertEqual(request.progress_percentage, 100)
    
    def test_is_download_expired(self):
        """Test download expiration check."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        # No download URL set
        self.assertFalse(request.is_download_expired())
        
        # Set future expiration
        request.download_expires_at = timezone.now() + timedelta(hours=1)
        self.assertFalse(request.is_download_expired())
        
        # Set past expiration
        request.download_expires_at = timezone.now() - timedelta(hours=1)
        self.assertTrue(request.is_download_expired())
    
    def test_get_generation_duration(self):
        """Test generation duration calculation."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        # No duration if not started
        self.assertEqual(request.get_generation_duration(), 0)
        
        # Set start and end times
        start_time = timezone.now() - timedelta(minutes=5)
        end_time = timezone.now()
        request.started_at = start_time
        request.completed_at = end_time
        
        duration = request.get_generation_duration()
        self.assertAlmostEqual(duration, 300, delta=10)  # ~5 minutes
    
    def test_get_springboot_config(self):
        """Test SpringBoot configuration retrieval."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            generation_config={
                'group_id': 'com.custom.example',
                'java_version': '21'
            }
        )
        
        config = request.get_springboot_config()
        
        # Should contain default values
        self.assertIn('spring_boot_version', config)
        self.assertIn('dependencies', config)
        self.assertIn('features', config)
        
        # Should override with custom values
        self.assertEqual(config['group_id'], 'com.custom.example')
        self.assertEqual(config['java_version'], '21')
        
        # Should have project-based artifact_id
        expected_artifact_id = self.project.name.lower().replace(' ', '-')
        self.assertEqual(config['artifact_id'], expected_artifact_id)
    
    def test_get_selected_uml_classes(self):
        """Test UML classes selection."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            selected_classes=['1']  # Only select first class
        )
        
        selected_classes = request.get_selected_uml_classes()
        
        self.assertEqual(len(selected_classes), 1)
        self.assertEqual(selected_classes[0]['name'], 'User')
    
    def test_get_all_uml_classes_when_none_selected(self):
        """Test returning all UML classes when none specifically selected."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            selected_classes=[]
        )
        
        selected_classes = request.get_selected_uml_classes()
        
        self.assertEqual(len(selected_classes), 2)  # Both User and Order
    
    def test_estimate_generation_time(self):
        """Test generation time estimation."""
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            generation_type='FULL_PROJECT'
        )
        
        estimated_time = request.estimate_generation_time()
        
        # Should include base time + class time + relationship time + full project time
        expected_time = 5 + (2 * 2) + (0 * 1) + 10  # base + classes + relationships + full project
        self.assertEqual(estimated_time, expected_time)
    
    def test_cleanup_expired_downloads(self):
        """Test cleanup of expired download links."""
        # Create request with expired download
        expired_request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            download_url='https://example.com/expired.zip',
            download_expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Create request with valid download
        valid_request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            download_url='https://example.com/valid.zip',
            download_expires_at=timezone.now() + timedelta(hours=1)
        )
        
        cleaned_count = GenerationRequest.cleanup_expired_downloads()
        
        self.assertEqual(cleaned_count, 1)
        
        expired_request.refresh_from_db()
        valid_request.refresh_from_db()
        
        self.assertEqual(expired_request.download_url, '')
        self.assertIsNone(expired_request.download_expires_at)
        self.assertNotEqual(valid_request.download_url, '')
        self.assertIsNotNone(valid_request.download_expires_at)


class GenerationTemplateModelTestCase(BaseTestCase):
    """Test cases for GenerationTemplate model."""
    
    def test_template_creation(self):
        """Test basic template creation."""
        template = GenerationTemplate.objects.create(
            name='Entity Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} {}'
        )
        
        self.assertEqual(template.name, 'Entity Template')
        self.assertEqual(template.category, 'ENTITY')
        self.assertEqual(template.template_type, 'BASIC')
        self.assertEqual(template.author, self.user)
        self.assertFalse(template.is_public)
        self.assertTrue(template.is_active)
    
    def test_template_str_representation(self):
        """Test template string representation."""
        template = GenerationTemplate.objects.create(
            name='Repository Template',
            category='REPOSITORY',
            template_type='ADVANCED',
            author=self.user
        )
        
        expected_str = 'Repository Template (REPOSITORY)'
        self.assertEqual(str(template), expected_str)
    
    def test_template_validation(self):
        """Test template validation methods."""
        template = GenerationTemplate.objects.create(
            name='Valid Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} { {{ attributes }} }'
        )
        
        # Should not raise exception for valid template
        try:
            template.validate_template()
        except Exception:
            self.fail("Template validation raised exception for valid template")
    
    def test_template_rendering(self):
        """Test template rendering with variables."""
        template = GenerationTemplate.objects.create(
            name='Test Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} { private Long {{ id_field }}; }'
        )
        
        variables = {'class_name': 'User', 'id_field': 'userId'}
        rendered = template.render_template(variables)
        
        expected = 'public class User { private Long userId; }'
        self.assertEqual(rendered, expected)
    
    def test_template_clone(self):
        """Test template cloning functionality."""
        original = GenerationTemplate.objects.create(
            name='Original Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user,
            template_content='public class {{ class_name }} {}',
            variables={'class_name': 'string'},
            is_public=True
        )
        
        cloned = original.clone_template('Cloned Template', self.user)
        
        self.assertEqual(cloned.name, 'Cloned Template')
        self.assertEqual(cloned.template_content, original.template_content)
        self.assertEqual(cloned.variables, original.variables)
        self.assertEqual(cloned.category, original.category)
        self.assertEqual(cloned.template_type, original.template_type)
        self.assertEqual(cloned.author, self.user)
        self.assertNotEqual(cloned.id, original.id)
    
    def test_template_usage_tracking(self):
        """Test template usage statistics."""
        template = GenerationTemplate.objects.create(
            name='Popular Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user
        )
        
        initial_usage = template.usage_count
        
        template.increment_usage()
        
        self.assertEqual(template.usage_count, initial_usage + 1)
        self.assertIsNotNone(template.last_used_at)
    
    def test_template_version_increment(self):
        """Test template version management."""
        template = GenerationTemplate.objects.create(
            name='Versioned Template',
            category='ENTITY',
            template_type='BASIC',
            author=self.user
        )
        
        initial_version = template.version
        
        template.increment_version()
        
        self.assertEqual(template.version, initial_version + 1)


class GeneratedProjectModelTestCase(BaseTestCase):
    """Test cases for GeneratedProject model."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
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
        
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
        
        self.generation_request = GenerationRequest.objects.create(
            project=project,
            diagram=diagram,
            requested_by=self.user
        )
    
    def test_generated_project_creation(self):
        """Test basic generated project creation."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-spring-app',
            file_path='/tmp/projects/test-spring-app.zip',
            file_size=2048576,  # 2MB
            created_by=self.user
        )
        
        self.assertEqual(project.generation_request, self.generation_request)
        self.assertEqual(project.project_name, 'test-spring-app')
        self.assertEqual(project.file_path, '/tmp/projects/test-spring-app.zip')
        self.assertEqual(project.file_size, 2048576)
        self.assertEqual(project.created_by, self.user)
        self.assertEqual(project.download_count, 0)
    
    def test_generated_project_str_representation(self):
        """Test generated project string representation."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='my-app',
            file_path='/tmp/my-app.zip',
            created_by=self.user
        )
        
        expected_str = f'my-app - {self.user.username}'
        self.assertEqual(str(project), expected_str)
    
    def test_file_size_display(self):
        """Test human-readable file size display."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-app',
            file_path='/tmp/test-app.zip',
            file_size=1024 * 1024 * 5,  # 5MB
            created_by=self.user
        )
        
        size_display = project.get_file_size_display()
        self.assertEqual(size_display, '5.0 MB')
    
    def test_download_tracking(self):
        """Test download count tracking."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-app',
            file_path='/tmp/test-app.zip',
            created_by=self.user
        )
        
        initial_count = project.download_count
        
        project.increment_download_count()
        
        self.assertEqual(project.download_count, initial_count + 1)
        self.assertIsNotNone(project.last_downloaded_at)
    
    def test_file_exists_check(self):
        """Test file existence validation."""
        project = GeneratedProject.objects.create(
            generation_request=self.generation_request,
            project_name='test-app',
            file_path='/nonexistent/path.zip',
            created_by=self.user
        )
        
        # This would typically check actual file system
        # For testing, we assume the method exists and returns False for invalid paths
        self.assertFalse(project.file_exists())


class GenerationHistoryModelTestCase(BaseTestCase):
    """Test cases for GenerationHistory model."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
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
        
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
        
        self.generation_request = GenerationRequest.objects.create(
            project=project,
            diagram=diagram,
            requested_by=self.user
        )
    
    def test_generation_history_creation(self):
        """Test basic generation history creation."""
        history = GenerationHistory.objects.create(
            generation_request=self.generation_request,
            action='STARTED',
            details={'step': 'initialization', 'progress': 0},
            performed_by=self.user
        )
        
        self.assertEqual(history.generation_request, self.generation_request)
        self.assertEqual(history.action, 'STARTED')
        self.assertEqual(history.details['step'], 'initialization')
        self.assertEqual(history.performed_by, self.user)
        self.assertIsNotNone(history.timestamp)
    
    def test_generation_history_str_representation(self):
        """Test generation history string representation."""
        history = GenerationHistory.objects.create(
            generation_request=self.generation_request,
            action='COMPLETED',
            performed_by=self.user
        )
        
        expected_str = f'COMPLETED - {self.generation_request.id} at {history.timestamp}'
        self.assertEqual(str(history), expected_str)
    
    def test_history_timeline(self):
        """Test generation history timeline creation."""
        # Create multiple history entries
        actions = ['STARTED', 'PROCESSING', 'COMPLETED']
        
        for i, action in enumerate(actions):
            GenerationHistory.objects.create(
                generation_request=self.generation_request,
                action=action,
                details={'step': f'step_{i}'},
                performed_by=self.user
            )
        
        timeline = GenerationHistory.objects.filter(
            generation_request=self.generation_request
        ).order_by('timestamp')
        
        self.assertEqual(timeline.count(), 3)
        self.assertEqual(timeline.first().action, 'STARTED')
        self.assertEqual(timeline.last().action, 'COMPLETED')
    
    def test_history_aggregation_by_request(self):
        """Test history aggregation by generation request."""
        # Create another generation request
        other_request = GenerationRequest.objects.create(
            project=self.generation_request.project,
            diagram=self.generation_request.diagram,
            requested_by=self.user
        )
        
        # Create history for both requests
        GenerationHistory.objects.create(
            generation_request=self.generation_request,
            action='STARTED',
            performed_by=self.user
        )
        GenerationHistory.objects.create(
            generation_request=other_request,
            action='STARTED',
            performed_by=self.user
        )
        
        # Check filtering works correctly
        first_history = GenerationHistory.objects.filter(
            generation_request=self.generation_request
        )
        second_history = GenerationHistory.objects.filter(
            generation_request=other_request
        )
        
        self.assertEqual(first_history.count(), 1)
        self.assertEqual(second_history.count(), 1)
        self.assertNotEqual(
            first_history.first().generation_request.id,
            second_history.first().generation_request.id
        )


class CodeGenerationModelsIntegrationTestCase(BaseTestCase):
    """Integration tests for code generation models."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        self.workspace = Workspace.objects.create(
            name='Integration Workspace',
            workspace_type='PERSONAL',
            owner=self.user
        )
        
        self.project = Project.objects.create(
            name='Integration Project',
            workspace=self.workspace,
            owner=self.user
        )
        
        self.diagram = UMLDiagram.objects.create(
            name='Integration Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user
        )
    
    def test_complete_generation_workflow(self):
        """Test complete generation workflow with all models."""
        # Create generation request
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user,
            generation_type='FULL_PROJECT'
        )
        
        # Start generation and create history
        request.start_generation()
        GenerationHistory.objects.create(
            generation_request=request,
            action='STARTED',
            details={'timestamp': timezone.now().isoformat()},
            performed_by=self.user
        )
        
        # Update progress
        request.update_progress(50, {'current_step': 'Generating entities'})
        GenerationHistory.objects.create(
            generation_request=request,
            action='PROGRESS',
            details={'progress': 50, 'step': 'entities'},
            performed_by=self.user
        )
        
        # Complete generation
        output_path = '/tmp/integration_project.zip'
        files_count = 30
        request.complete_generation(output_path, files_count)
        
        # Create generated project
        generated_project = GeneratedProject.objects.create(
            generation_request=request,
            project_name='integration-spring-app',
            file_path=output_path,
            file_size=3145728,  # 3MB
            created_by=self.user
        )
        
        # Create completion history
        GenerationHistory.objects.create(
            generation_request=request,
            action='COMPLETED',
            details={'files_generated': files_count, 'output_path': output_path},
            performed_by=self.user
        )
        
        # Verify complete workflow
        self.assertEqual(request.status, 'COMPLETED')
        self.assertEqual(request.generated_files_count, files_count)
        self.assertEqual(generated_project.generation_request, request)
        
        # Check history timeline
        history = GenerationHistory.objects.filter(generation_request=request)
        self.assertEqual(history.count(), 3)
        
        actions = list(history.values_list('action', flat=True))
        self.assertIn('STARTED', actions)
        self.assertIn('PROGRESS', actions)
        self.assertIn('COMPLETED', actions)
    
    def test_generation_cleanup_cascade(self):
        """Test cascade deletion behavior."""
        # Create request with related objects
        request = GenerationRequest.objects.create(
            project=self.project,
            diagram=self.diagram,
            requested_by=self.user
        )
        
        generated_project = GeneratedProject.objects.create(
            generation_request=request,
            project_name='test-app',
            file_path='/tmp/test.zip',
            created_by=self.user
        )
        
        history = GenerationHistory.objects.create(
            generation_request=request,
            action='STARTED',
            performed_by=self.user
        )
        
        request_id = request.id
        project_id = generated_project.id
        history_id = history.id
        
        # Delete the request
        request.delete()
        
        # Check that related objects are also deleted
        with self.assertRaises(GenerationRequest.DoesNotExist):
            GenerationRequest.objects.get(id=request_id)
        
        with self.assertRaises(GeneratedProject.DoesNotExist):
            GeneratedProject.objects.get(id=project_id)
        
        with self.assertRaises(GenerationHistory.DoesNotExist):
            GenerationHistory.objects.get(id=history_id)
