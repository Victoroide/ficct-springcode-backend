"""
Comprehensive tests for UML Diagrams ViewSets.

Tests all UML diagram endpoints including CRUD operations, validation,
export functionality, and diagram-specific actions with full coverage.
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
import json
import uuid

from base.test_base import EnterpriseTestCase
from base.test_factories import (
    EnterpriseUserFactory, 
    ProjectFactory, 
    WorkspaceFactory,
    UMLDiagramFactory,
    UMLElementFactory,
    UMLRelationshipFactory
)
from apps.uml_diagrams.models import UMLDiagram

User = get_user_model()


class UMLDiagramViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for UMLDiagramViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for UML diagram tests."""
        super().setUpTestData()

        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)

        cls.class_diagram = UMLDiagramFactory(
            project=cls.project,
            name='User Management Classes',
            diagram_type='CLASS',
            created_by=cls.test_user,
            last_modified_by=cls.test_user
        )
        
        cls.sequence_diagram = UMLDiagramFactory(
            project=cls.project,
            name='Login Sequence',
            diagram_type='SEQUENCE',
            created_by=cls.test_user,
            last_modified_by=cls.test_user
        )

        cls.other_user = EnterpriseUserFactory(email='other@ficct-enterprise.com')
        cls.other_workspace = WorkspaceFactory(owner=cls.other_user)
        cls.other_project = ProjectFactory(workspace=cls.other_workspace, owner=cls.other_user)
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.diagrams_url = reverse('uml_diagrams:umldiagram-list')
        self.diagram_detail_url = reverse('uml_diagrams:umldiagram-detail', args=[self.class_diagram.id])
    
    def test_list_uml_diagrams(self):
        """Test listing UML diagrams."""
        response = self.client.get(self.diagrams_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 2)

        diagram_data = response_data['results'][0]
        self.assertIn('id', diagram_data)
        self.assertIn('name', diagram_data)
        self.assertIn('diagram_type', diagram_data)
        self.assertIn('status', diagram_data)
        self.assertIn('project', diagram_data)
    
    def test_retrieve_uml_diagram(self):
        """Test retrieving a specific UML diagram."""
        response = self.client.get(self.diagram_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.class_diagram.id))
        self.assertEqual(response_data['name'], 'User Management Classes')
        self.assertEqual(response_data['diagram_type'], 'CLASS')
        self.assertEqual(response_data['project']['id'], str(self.project.id))
    
    def test_create_uml_diagram(self):
        """Test creating a new UML diagram."""
        data = {
            'project': str(self.project.id),
            'name': 'New Activity Diagram',
            'description': 'User registration activity flow',
            'diagram_type': 'ACTIVITY',
            'visibility': 'TEAM',
            'diagram_data': {
                'activities': [],
                'transitions': []
            },
            'tags': ['activity', 'registration', 'user-flow']
        }
        
        response = self.client.post(self.diagrams_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['name'], 'New Activity Diagram')
        self.assertEqual(response_data['diagram_type'], 'ACTIVITY')
        self.assertEqual(response_data['created_by']['id'], str(self.test_user.id))
        self.assertEqual(response_data['status'], 'DRAFT')
        self.assertEqual(response_data['version_number'], 1)
    
    def test_create_diagram_invalid_project(self):
        """Test creating diagram with invalid project."""
        data = {
            'project': str(uuid.uuid4()),  # Non-existent project
            'name': 'Invalid Project Diagram',
            'diagram_type': 'CLASS'
        }
        
        response = self.client.post(self.diagrams_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_uml_diagram(self):
        """Test updating UML diagram."""
        data = {
            'name': 'Updated User Classes',
            'description': 'Updated user management class diagram',
            'status': 'IN_REVIEW',
            'diagram_data': {
                'classes': [
                    {
                        'id': str(uuid.uuid4()),
                        'name': 'User',
                        'attributes': ['id', 'email', 'password'],
                        'methods': ['login()', 'logout()']
                    }
                ]
            }
        }
        
        response = self.client.patch(self.diagram_detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['name'], 'Updated User Classes')
        self.assertEqual(response_data['status'], 'IN_REVIEW')
        self.assertEqual(len(response_data['diagram_data']['classes']), 1)
        self.assertEqual(response_data['diagram_data']['classes'][0]['name'], 'User')
    
    def test_delete_uml_diagram(self):
        """Test deleting UML diagram."""
        response = self.client.delete(self.diagram_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(
            UMLDiagram.objects.filter(id=self.class_diagram.id).exists()
        )
    
    def test_filter_diagrams_by_type(self):
        """Test filtering diagrams by type."""
        response = self.client.get(f'{self.diagrams_url}?diagram_type=CLASS')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for diagram in response_data['results']:
            self.assertEqual(diagram['diagram_type'], 'CLASS')
    
    def test_filter_diagrams_by_status(self):
        """Test filtering diagrams by status."""

        self.sequence_diagram.status = 'APPROVED'
        self.sequence_diagram.save()
        
        response = self.client.get(f'{self.diagrams_url}?status=APPROVED')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for diagram in response_data['results']:
            self.assertEqual(diagram['status'], 'APPROVED')
    
    def test_search_diagrams(self):
        """Test searching diagrams by name and description."""
        response = self.client.get(f'{self.diagrams_url}?search=User')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        self.assertTrue(len(response_data['results']) >= 1)
        found_user_diagram = any(
            'User' in diagram['name'] or 'User' in diagram.get('description', '')
            for diagram in response_data['results']
        )
        self.assertTrue(found_user_diagram)
    
    def test_order_diagrams(self):
        """Test ordering diagrams by different fields."""
        response = self.client.get(f'{self.diagrams_url}?ordering=name')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        names = [diagram['name'] for diagram in response_data['results']]
        self.assertEqual(names, sorted(names))
    
    @patch('apps.uml_diagrams.models.UMLDiagram.get_export_data')
    def test_export_diagram_data(self, mock_export):
        """Test exporting diagram data."""
        mock_export.return_value = {
            'diagram_id': str(self.class_diagram.id),
            'name': self.class_diagram.name,
            'classes': [],
            'relationships': [],
            'export_format': 'json',
            'exported_at': '2024-01-15T10:00:00Z'
        }
        
        export_url = reverse('uml_diagrams:umldiagram-export-data', args=[self.class_diagram.id])
        response = self.client.get(export_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['diagram_id'], str(self.class_diagram.id))
        self.assertEqual(response_data['name'], self.class_diagram.name)
        self.assertIn('classes', response_data)
        self.assertIn('relationships', response_data)
        mock_export.assert_called_once()
    
    @patch('apps.uml_diagrams.models.UMLDiagram.get_diagram_statistics')
    def test_diagram_statistics(self, mock_stats):
        """Test retrieving diagram statistics."""
        mock_stats.return_value = {
            'total_classes': 5,
            'total_relationships': 8,
            'diagram_complexity': 'Medium',
            'validation_score': 85,
            'last_modified': '2024-01-15T10:00:00Z',
            'version_count': 3
        }
        
        stats_url = reverse('uml_diagrams:umldiagram-statistics', args=[self.class_diagram.id])
        response = self.client.get(stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['total_classes'], 5)
        self.assertEqual(response_data['total_relationships'], 8)
        self.assertEqual(response_data['diagram_complexity'], 'Medium')
        self.assertEqual(response_data['validation_score'], 85)
        mock_stats.assert_called_once()
    
    @patch('apps.uml_diagrams.models.UMLDiagram.validate_complete_diagram')
    def test_validate_diagram(self, mock_validate):
        """Test diagram validation."""
        mock_validate.return_value = {
            'is_valid': True,
            'validation_score': 92,
            'warnings': [],
            'errors': [],
            'suggestions': [
                'Consider adding more descriptive method names',
                'Add proper access modifiers to attributes'
            ],
            'architectural_patterns': ['Repository Pattern', 'MVC Pattern']
        }
        
        validate_url = reverse('uml_diagrams:umldiagram-validate-diagram', args=[self.class_diagram.id])
        response = self.client.post(validate_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['is_valid'])
        self.assertEqual(response_data['validation_score'], 92)
        self.assertIn('suggestions', response_data)
        self.assertIn('architectural_patterns', response_data)
        mock_validate.assert_called_once()
    
    def test_unauthorized_access(self):
        """Test unauthorized access to other user's diagrams."""

        other_diagram = UMLDiagramFactory(
            project=self.other_project,
            created_by=self.other_user,
            last_modified_by=self.other_user
        )

        other_diagram_url = reverse('uml_diagrams:umldiagram-detail', args=[other_diagram.id])
        response = self.client.get(other_diagram_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_access(self):
        """Test unauthenticated access to diagrams."""
        self.logout_user()
        
        response = self.client.get(self.diagrams_url)
        self.assert_unauthorized(response)


class UMLElementViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for UMLElementViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for UML element tests."""
        super().setUpTestData()
        
        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)
        cls.diagram = UMLDiagramFactory(
            project=cls.project,
            diagram_type='CLASS',
            created_by=cls.test_user,
            last_modified_by=cls.test_user
        )

        cls.user_class = UMLElementFactory(
            diagram=cls.diagram,
            element_type='class',
            name='User'
        )
        
        cls.product_class = UMLElementFactory(
            diagram=cls.diagram,
            element_type='class',
            name='Product'
        )
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.elements_url = reverse('uml_diagrams:umlelement-list')
        self.element_detail_url = reverse('uml_diagrams:umlelement-detail', args=[self.user_class.id])
    
    def test_list_elements(self):
        """Test listing UML elements."""
        response = self.client.get(self.elements_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 2)
    
    def test_retrieve_element(self):
        """Test retrieving a specific UML element."""
        response = self.client.get(self.element_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.user_class.id))
        self.assertEqual(response_data['name'], 'User')
        self.assertEqual(response_data['element_type'], 'class')
    
    def test_create_element(self):
        """Test creating a new UML element."""
        data = {
            'diagram': str(self.diagram.id),
            'element_type': 'class',
            'name': 'Order',
            'properties': {
                'attributes': ['id', 'total', 'created_at'],
                'methods': ['calculateTotal()', 'processPayment()'],
                'visibility': 'public'
            },
            'position_x': 200,
            'position_y': 150
        }
        
        response = self.client.post(self.elements_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['name'], 'Order')
        self.assertEqual(response_data['element_type'], 'class')
        self.assertEqual(response_data['position_x'], 200)
        self.assertEqual(response_data['position_y'], 150)
    
    def test_update_element(self):
        """Test updating UML element."""
        data = {
            'name': 'EnterpriseUser',
            'properties': {
                'attributes': ['id', 'email', 'role', 'department'],
                'methods': ['authenticate()', 'authorize()', 'getPermissions()']
            },
            'position_x': 100,
            'position_y': 200
        }
        
        response = self.client.patch(self.element_detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['name'], 'EnterpriseUser')
        self.assertEqual(response_data['position_x'], 100)
        self.assertEqual(response_data['position_y'], 200)
    
    def test_delete_element(self):
        """Test deleting UML element."""
        response = self.client.delete(self.element_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        from apps.uml_diagrams.models import UMLElement
        self.assertFalse(
            UMLElement.objects.filter(id=self.user_class.id).exists()
        )
    
    def test_filter_elements_by_diagram(self):
        """Test filtering elements by diagram."""
        response = self.client.get(f'{self.elements_url}?diagram={self.diagram.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for element in response_data['results']:
            self.assertEqual(element['diagram']['id'], str(self.diagram.id))
    
    def test_filter_elements_by_type(self):
        """Test filtering elements by type."""

        UMLElementFactory(
            diagram=self.diagram,
            element_type='interface',
            name='UserRepository'
        )
        
        response = self.client.get(f'{self.elements_url}?element_type=class')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for element in response_data['results']:
            self.assertEqual(element['element_type'], 'class')


class UMLRelationshipViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for UMLRelationshipViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for UML relationship tests."""
        super().setUpTestData()
        
        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)
        cls.diagram = UMLDiagramFactory(
            project=cls.project,
            diagram_type='CLASS',
            created_by=cls.test_user,
            last_modified_by=cls.test_user
        )

        cls.user_element = UMLElementFactory(
            diagram=cls.diagram,
            element_type='class',
            name='User'
        )
        
        cls.order_element = UMLElementFactory(
            diagram=cls.diagram,
            element_type='class',
            name='Order'
        )

        cls.user_order_relationship = UMLRelationshipFactory(
            diagram=cls.diagram,
            source_element=cls.user_element,
            target_element=cls.order_element,
            relationship_type='association'
        )
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.relationships_url = reverse('uml_diagrams:umlrelationship-list')
        self.relationship_detail_url = reverse(
            'uml_diagrams:umlrelationship-detail', 
            args=[self.user_order_relationship.id]
        )
    
    def test_list_relationships(self):
        """Test listing UML relationships."""
        response = self.client.get(self.relationships_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 1)
    
    def test_retrieve_relationship(self):
        """Test retrieving a specific UML relationship."""
        response = self.client.get(self.relationship_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.user_order_relationship.id))
        self.assertEqual(response_data['relationship_type'], 'association')
        self.assertEqual(response_data['source_element']['id'], str(self.user_element.id))
        self.assertEqual(response_data['target_element']['id'], str(self.order_element.id))
    
    def test_create_relationship(self):
        """Test creating a new UML relationship."""

        product_element = UMLElementFactory(
            diagram=self.diagram,
            element_type='class',
            name='Product'
        )
        
        data = {
            'diagram': str(self.diagram.id),
            'source_element': str(self.order_element.id),
            'target_element': str(product_element.id),
            'relationship_type': 'composition',
            'properties': {
                'multiplicity': '1..*',
                'role': 'contains'
            }
        }
        
        response = self.client.post(self.relationships_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['relationship_type'], 'composition')
        self.assertEqual(response_data['source_element']['id'], str(self.order_element.id))
        self.assertEqual(response_data['target_element']['id'], str(product_element.id))
    
    def test_update_relationship(self):
        """Test updating UML relationship."""
        data = {
            'relationship_type': 'aggregation',
            'properties': {
                'multiplicity': '1..*',
                'navigability': 'bidirectional'
            }
        }
        
        response = self.client.patch(self.relationship_detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['relationship_type'], 'aggregation')
        self.assertEqual(response_data['properties']['multiplicity'], '1..*')
    
    def test_delete_relationship(self):
        """Test deleting UML relationship."""
        response = self.client.delete(self.relationship_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        from apps.uml_diagrams.models import UMLRelationship
        self.assertFalse(
            UMLRelationship.objects.filter(id=self.user_order_relationship.id).exists()
        )
    
    def test_filter_relationships_by_diagram(self):
        """Test filtering relationships by diagram."""
        response = self.client.get(f'{self.relationships_url}?diagram={self.diagram.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for relationship in response_data['results']:
            self.assertEqual(relationship['diagram']['id'], str(self.diagram.id))
    
    def test_filter_relationships_by_type(self):
        """Test filtering relationships by type."""

        UMLRelationshipFactory(
            diagram=self.diagram,
            source_element=self.user_element,
            target_element=self.order_element,
            relationship_type='inheritance'
        )
        
        response = self.client.get(f'{self.relationships_url}?relationship_type=inheritance')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()

        for relationship in response_data['results']:
            self.assertEqual(relationship['relationship_type'], 'inheritance')
    
    def test_invalid_relationship_creation(self):
        """Test creating relationship with invalid elements."""
        data = {
            'diagram': str(self.diagram.id),
            'source_element': str(uuid.uuid4()),  # Non-existent element
            'target_element': str(self.order_element.id),
            'relationship_type': 'association'
        }
        
        response = self.client.post(self.relationships_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_self_relationship_creation(self):
        """Test creating self-referencing relationship."""
        data = {
            'diagram': str(self.diagram.id),
            'source_element': str(self.user_element.id),
            'target_element': str(self.user_element.id),
            'relationship_type': 'association',
            'properties': {
                'multiplicity': '0..*',
                'role': 'manager'
            }
        }
        
        response = self.client.post(self.relationships_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['source_element']['id'], str(self.user_element.id))
        self.assertEqual(response_data['target_element']['id'], str(self.user_element.id))
