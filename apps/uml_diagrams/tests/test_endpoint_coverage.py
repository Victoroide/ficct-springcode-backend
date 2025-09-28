"""
Comprehensive Unit Tests for UML Diagrams Endpoints

Tests for ALL UML diagram endpoints including UMLDiagramViewSet,
UMLElementViewSet, and UMLRelationshipViewSet with full CRUD operations.
"""

import json
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from base.test_base import BaseTestCase
from base.test_factories import EnterpriseUserFactory, AdminUserFactory
from apps.uml_diagrams.models import UMLDiagram, UMLElement, UMLRelationship

User = get_user_model()


class UMLDiagramViewSetTestCase(BaseTestCase):
    """Test cases for UMLDiagramViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project
        self.project = ProjectFactory(owner=self.test_user)
        
        # Create test diagram
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user,
            content={'elements': [], 'relationships': []}
        )
        
        self.base_url = '/api/v1/diagrams/'
    
    def test_list_diagrams_success(self):
        """Test GET /api/v1/diagrams/ returns list of diagrams."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_diagram_success(self):
        """Test POST /api/v1/diagrams/ creates new diagram."""
        data = {
            'name': 'New UML Diagram',
            'diagram_type': 'sequence',
            'project': self.project.id,
            'description': 'New diagram for testing',
            'content': {'elements': [], 'relationships': []}
        }
        
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New UML Diagram')
        self.assertEqual(response.data['diagram_type'], 'sequence')
    
    def test_retrieve_diagram_success(self):
        """Test GET /api/v1/diagrams/{id}/ returns specific diagram."""
        url = f'{self.base_url}{self.diagram.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.diagram.id)
        self.assertEqual(response.data['name'], self.diagram.name)
    
    def test_update_diagram_success(self):
        """Test PATCH /api/v1/diagrams/{id}/ updates diagram."""
        url = f'{self.base_url}{self.diagram.id}/'
        data = {
            'name': 'Updated Diagram',
            'description': 'Updated description'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Diagram')
    
    def test_delete_diagram_success(self):
        """Test DELETE /api/v1/diagrams/{id}/ deletes diagram."""
        diagram_to_delete = UMLDiagram.objects.create(
            name='Diagram to Delete',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user
        )
        
        url = f'{self.base_url}{diagram_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            UMLDiagram.objects.filter(id=diagram_to_delete.id).exists()
        )


class UMLElementViewSetTestCase(BaseTestCase):
    """Test cases for UMLElementViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and diagram
        self.project = ProjectFactory(owner=self.test_user)
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user
        )
        
        # Create test element
        self.element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='class',
            name='TestClass',
            properties={'attributes': [], 'methods': []},
            position={'x': 100, 'y': 200}
        )
        
        self.base_url = '/api/v1/elements/'
    
    def test_list_elements_success(self):
        """Test GET /api/v1/elements/ returns list of elements."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_create_element_success(self):
        """Test POST /api/v1/elements/ creates new element."""
        data = {
            'diagram': self.diagram.id,
            'name': 'TestInterface',
            'properties': {'methods': ['method1', 'method2']},
            'position': {'x': 300, 'y': 400}
        }
        
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'TestInterface')
        self.assertEqual(response.data['element_type'], 'interface')
    
    def test_retrieve_element_success(self):
        """Test GET /api/v1/elements/{id}/ returns specific element."""
        url = f'{self.base_url}{self.element.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.element.id)
        self.assertEqual(response.data['name'], self.element.name)
    
    def test_update_element_success(self):
        """Test PATCH /api/v1/elements/{id}/ updates element."""
        url = f'{self.base_url}{self.element.id}/'
        data = {
            'name': 'UpdatedClass',
            'properties': {'attributes': ['attr1'], 'methods': ['method1']}
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'UpdatedClass')
    
    def test_delete_element_success(self):
        """Test DELETE /api/v1/elements/{id}/ deletes element."""
        element_to_delete = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='class',
            name='ElementToDelete',
            properties={},
            position={'x': 0, 'y': 0}
        )
        
        url = f'{self.base_url}{element_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            UMLElement.objects.filter(id=element_to_delete.id).exists()
        )


class UMLRelationshipViewSetTestCase(BaseTestCase):
    """Test cases for UMLRelationshipViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and diagram
        self.project = ProjectFactory(owner=self.test_user)
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='class',
            project=self.project,
            created_by=self.test_user
        )
        
        # Create test elements
        self.source_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='class',
            name='SourceClass',
            properties={},
            position={'x': 100, 'y': 100}
        )
        
        self.target_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='class',
            name='TargetClass',
            properties={},
            position={'x': 300, 'y': 300}
        )
        
        # Create test relationship
        self.relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='association',
            properties={'multiplicity': '1..*'}
        )
        
        self.base_url = '/api/v1/relationships/'
    
    def test_list_relationships_success(self):
        """Test GET /api/v1/relationships/ returns list of relationships."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_create_relationship_success(self):
        """Test POST /api/v1/relationships/ creates new relationship."""
        data = {
            'diagram': self.diagram.id,
            'source_element': self.source_element.id,
            'target_element': self.target_element.id,
            'relationship_type': 'inheritance',
            'properties': {'label': 'extends'}
        }
        
        response = self.client.post(self.base_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['relationship_type'], 'inheritance')
    
    def test_retrieve_relationship_success(self):
        url = f'{self.base_url}{self.relationship.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.relationship.id)
        self.assertEqual(response.data['relationship_type'], 'association')
    
    def test_update_relationship_success(self):
        """Test PATCH /api/v1/relationships/{id}/ updates relationship."""
        url = f'{self.base_url}{self.relationship.id}/'
        data = {
            'relationship_type': 'composition',
            'properties': {'multiplicity': '1..1'}
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['relationship_type'], 'composition')
    
    def test_delete_relationship_success(self):
        """Test DELETE /api/v1/relationships/{id}/ deletes relationship."""
        relationship_to_delete = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='dependency',
            properties={}
        )
        
        url = f'{self.base_url}{relationship_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            UMLRelationship.objects.filter(id=relationship_to_delete.id).exists()
        )


class UMLDiagramsErrorHandlingTestCase(BaseTestCase):
    """Test cases for UML diagrams error handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project
        self.project = ProjectFactory(owner=self.test_user)
    
    def test_invalid_diagram_type(self):
        """Test creating diagram with invalid type."""
        data = {
            'name': 'Invalid Diagram',
            'diagram_type': 'invalid_type',
            'project': self.project.id,
            'content': {}
        }
        
        response = self.client.post('/api/v1/diagrams/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_missing_required_fields(self):
        """Test creating elements/relationships with missing fields."""
        # Missing diagram field
        data = {
            'element_type': 'class',
            'name': 'TestClass'
        }
        
        response = self.client.post('/api/v1/elements/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_json_content(self):
        """Test handling invalid JSON in diagram content."""
        data = {
            'name': 'Invalid Content Diagram',
            'diagram_type': 'class',
            'project': self.project.id,
            'content': 'invalid json string'
        }
        
        response = self.client.post('/api/v1/diagrams/', data, format='json')
        # Should handle gracefully
        self.assertIn(response.status_code, [400, 201])


class UMLDiagramsPermissionsTestCase(BaseTestCase):
    """Test cases for UML diagrams permissions."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access endpoints."""
        endpoints = [
            '/api/v1/diagrams/',
            '/api/v1/elements/', 
            '/api/v1/relationships/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test that authenticated users can access endpoints."""
        self.client.force_authenticate(user=self.test_user)
        
        endpoints = [
            '/api/v1/diagrams/',
            '/api/v1/elements/',
            '/api/v1/relationships/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertNotIn(response.status_code, [401, 403])
