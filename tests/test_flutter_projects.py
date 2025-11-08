"""
Tests for Flutter metadata CRUD API.

Tests all CRUD operations, validations, and rate limiting.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.flutter_projects.models import FlutterProject
import uuid


class TestFlutterProjectsCRUD(TestCase):
    """Test Flutter projects CRUD operations."""
    
    def setUp(self):
        """Set up test client and sample data."""
        self.client = APIClient()
        self.session_id = "test-session-123"
        self.diagram_id = str(uuid.uuid4())
        
        self.valid_project_data = {
            "diagram_id": self.diagram_id,
            "session_id": self.session_id,
            "project_name": "erp_inventory",
            "package_name": "com.example.erp_inventory",
            "config": {
                "theme": "material3",
                "primary_color": "#6200EE",
                "navigation_type": "drawer",
                "state_management": "provider",
                "enable_dark_mode": True
            },
            "metadata": {
                "description": "ERP Inventory System",
                "version": "1.0.0",
                "classes_count": 5
            }
        }
    
    def test_create_flutter_project(self):
        """Test: Create Flutter project with valid data."""
        response = self.client.post(
            '/api/flutter-projects/',
            self.valid_project_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['project_name'] == "erp_inventory"
        assert FlutterProject.objects.count() == 1
    
    def test_list_projects_by_session(self):
        """Test: List projects filtered by session_id."""
        FlutterProject.objects.create(**self.valid_project_data)
        
        other_session_data = self.valid_project_data.copy()
        other_session_data['session_id'] = "other-session"
        other_session_data['diagram_id'] = str(uuid.uuid4())
        FlutterProject.objects.create(**other_session_data)
        
        response = self.client.get(
            f'/api/flutter-projects/?session_id={self.session_id}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['session_id'] == self.session_id
    
    def test_get_project_detail(self):
        """Test: Get single project by ID."""
        project = FlutterProject.objects.create(**self.valid_project_data)
        
        response = self.client.get(f'/api/flutter-projects/{project.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(project.id)
        assert 'config' in response.data
        assert 'metadata' in response.data
    
    def test_update_project_configuration(self):
        """Test: Update project config with PATCH."""
        project = FlutterProject.objects.create(**self.valid_project_data)
        
        update_data = {
            "config": {
                "theme": "cupertino",
                "primary_color": "#FF5722",
                "navigation_type": "bottom_nav"
            }
        }
        
        response = self.client.patch(
            f'/api/flutter-projects/{project.id}/',
            update_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['config']['theme'] == "cupertino"
        
        project.refresh_from_db()
        assert project.config['theme'] == "cupertino"
    
    def test_delete_project(self):
        """Test: Delete Flutter project."""
        project = FlutterProject.objects.create(**self.valid_project_data)
        
        response = self.client.delete(f'/api/flutter-projects/{project.id}/')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert FlutterProject.objects.count() == 0


class TestFlutterProjectsValidation(TestCase):
    """Test validation rules for Flutter projects."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.base_data = {
            "diagram_id": str(uuid.uuid4()),
            "session_id": "test-session",
            "config": {},
            "metadata": {}
        }
    
    def test_invalid_package_name(self):
        """Test: Reject invalid package_name format."""
        invalid_data = self.base_data.copy()
        invalid_data['project_name'] = "valid_project"
        invalid_data['package_name'] = "InvalidPackage"
        
        response = self.client.post(
            '/api/flutter-projects/',
            invalid_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'package_name' in str(response.data).lower()
    
    def test_invalid_project_name(self):
        """Test: Reject invalid project_name (not snake_case)."""
        invalid_data = self.base_data.copy()
        invalid_data['project_name'] = "invalid-project-name"
        invalid_data['package_name'] = "com.example.app"
        
        response = self.client.post(
            '/api/flutter-projects/',
            invalid_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_theme(self):
        """Test: Reject invalid theme option."""
        invalid_data = self.base_data.copy()
        invalid_data['project_name'] = "test_project"
        invalid_data['package_name'] = "com.example.test"
        invalid_data['config'] = {"theme": "invalid_theme"}
        
        response = self.client.post(
            '/api/flutter-projects/',
            invalid_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_color_format(self):
        """Test: Reject invalid hex color format."""
        invalid_data = self.base_data.copy()
        invalid_data['project_name'] = "test_project"
        invalid_data['package_name'] = "com.example.test"
        invalid_data['config'] = {"primary_color": "not-a-hex-color"}
        
        response = self.client.post(
            '/api/flutter-projects/',
            invalid_data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestFlutterProjectsRateLimiting(TestCase):
    """Test rate limiting enforcement."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.session_id = "rate-limit-test"
    
    @pytest.mark.skip(reason="Rate limiting requires time delays in tests")
    def test_rate_limit_enforcement(self):
        """Test: Enforce 50 requests per hour limit."""
        project_data = {
            "diagram_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "project_name": "test_project",
            "package_name": "com.example.test",
            "config": {},
            "metadata": {}
        }
        
        for i in range(51):
            response = self.client.post(
                '/api/flutter-projects/',
                project_data,
                format='json'
            )
            
            if i < 50:
                assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
            else:
                assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                assert 'Retry-After' in response or 'retry' in str(response.data).lower()


class TestFlutterProjectsActions(TestCase):
    """Test custom actions (export, statistics)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        self.project = FlutterProject.objects.create(
            diagram_id=uuid.uuid4(),
            session_id="test-session",
            project_name="test_app",
            package_name="com.example.test_app",
            config={
                "theme": "material3",
                "primary_color": "#6200EE",
                "navigation_type": "drawer",
                "state_management": "provider"
            },
            metadata={
                "description": "Test App",
                "version": "1.0.0",
                "classes_count": 3
            }
        )
    
    def test_export_configuration(self):
        """Test: Export project configuration."""
        response = self.client.get(
            f'/api/flutter-projects/{self.project.id}/export_config/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'config' in response.data or 'theme' in str(response.data)
    
    def test_statistics_endpoint(self):
        """Test: Get Flutter projects statistics."""
        FlutterProject.objects.create(
            diagram_id=uuid.uuid4(),
            session_id="test-session-2",
            project_name="another_app",
            package_name="com.example.another",
            config={"theme": "cupertino"},
            metadata={}
        )
        
        response = self.client.get('/api/flutter-projects/statistics/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total' in str(response.data).lower() or 'count' in str(response.data).lower()
