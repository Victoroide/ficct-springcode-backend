"""
Tests for UML Diagrams app models - UMLDiagram, UMLElement, UMLRelationship.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
import json

from ..models import UMLDiagram, UMLElement, UMLRelationship

User = get_user_model()


class UMLDiagramModelTestCase(TestCase):
    """Test cases for UMLDiagram model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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
    
    def test_diagram_creation(self):
        """Test basic diagram creation."""
        diagram = UMLDiagram.objects.create(
            name='User Management Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user
        )
        
        self.assertEqual(diagram.name, 'User Management Diagram')
        self.assertEqual(diagram.diagram_type, 'CLASS')
        self.assertEqual(diagram.project, self.project)
        self.assertEqual(diagram.created_by, self.user)
        self.assertEqual(diagram.status, 'DRAFT')
    
    def test_diagram_str_representation(self):
        """Test diagram string representation."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='SEQUENCE',
            project=self.project,
            created_by=self.user
        )
        
        expected_str = f'Test Diagram (SEQUENCE) - {self.project.name}'
        self.assertEqual(str(diagram), expected_str)
    
    def test_diagram_metadata_default(self):
        """Test default metadata structure."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user
        )
        
        self.assertIsNotNone(diagram.metadata)
        self.assertIn('canvas', diagram.metadata)
        self.assertIn('zoom_level', diagram.metadata)
        self.assertIn('theme', diagram.metadata)
    
    def test_diagram_element_count(self):
        """Test element counting methods."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user
        )

        UMLElement.objects.create(
            diagram=diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        UMLElement.objects.create(
            diagram=diagram,
            element_type='CLASS',
            name='Order',
            position_x=300,
            position_y=100,
            created_by=self.user
        )
        
        self.assertEqual(diagram.get_element_count(), 2)
        self.assertEqual(diagram.get_class_count(), 2)
        self.assertEqual(diagram.get_interface_count(), 0)
    
    def test_diagram_validation(self):
        """Test diagram validation methods."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user,
            diagram_data={
                'elements': [
                    {
                        'id': 'class1',
                        'type': 'class',
                        'name': 'User',
                        'attributes': ['id: Long', 'name: String'],
                        'methods': ['getId(): Long', 'setName(String): void']
                    }
                ],
                'relationships': []
            }
        )

        try:
            diagram.validate_diagram()
        except Exception:
            self.fail("Diagram validation raised exception for valid diagram")
    
    def test_diagram_export_data(self):
        """Test diagram export functionality."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user,
            diagram_data={'elements': [], 'relationships': []}
        )
        
        export_data = diagram.get_export_data()
        
        self.assertIn('name', export_data)
        self.assertIn('diagram_type', export_data)
        self.assertIn('diagram_data', export_data)
        self.assertIn('metadata', export_data)
        self.assertIn('created_at', export_data)
    
    def test_diagram_activity_update(self):
        """Test diagram activity tracking."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user
        )
        
        original_activity = diagram.last_modified_at
        
        diagram.update_activity()
        
        self.assertGreater(diagram.last_modified_at, original_activity)
    
    def test_diagram_collaboration_settings(self):
        """Test collaboration settings."""
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.user,
            collaboration_settings={
                'real_time_editing': True,
                'allow_comments': True,
                'auto_save_interval': 30
            }
        )
        
        self.assertTrue(diagram.collaboration_settings['real_time_editing'])
        self.assertTrue(diagram.collaboration_settings['allow_comments'])
        self.assertEqual(diagram.collaboration_settings['auto_save_interval'], 30)


class UMLElementModelTestCase(TestCase):
    """Test cases for UMLElement model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
    
    def test_element_creation(self):
        """Test basic element creation."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=150,
            width=200,
            height=300,
            created_by=self.user
        )
        
        self.assertEqual(element.name, 'User')
        self.assertEqual(element.element_type, 'CLASS')
        self.assertEqual(element.position_x, 100)
        self.assertEqual(element.position_y, 150)
        self.assertEqual(element.width, 200)
        self.assertEqual(element.height, 300)
    
    def test_element_str_representation(self):
        """Test element string representation."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='INTERFACE',
            name='UserService',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        expected_str = f'UserService (INTERFACE) - {self.diagram.name}'
        self.assertEqual(str(element), expected_str)
    
    def test_element_properties_default(self):
        """Test default element properties."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        self.assertIsNotNone(element.properties)
        self.assertIn('attributes', element.properties)
        self.assertIn('methods', element.properties)
        self.assertIn('visibility', element.properties)
    
    def test_class_element_properties(self):
        """Test class element specific properties."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user,
            properties={
                'attributes': [
                    {'name': 'id', 'type': 'Long', 'visibility': 'private'},
                    {'name': 'username', 'type': 'String', 'visibility': 'private'}
                ],
                'methods': [
                    {'name': 'getId', 'return_type': 'Long', 'visibility': 'public'},
                    {'name': 'setUsername', 'parameters': ['String username'], 'visibility': 'public'}
                ],
                'is_abstract': False,
                'stereotype': None
            }
        )
        
        self.assertEqual(len(element.properties['attributes']), 2)
        self.assertEqual(len(element.properties['methods']), 2)
        self.assertFalse(element.properties['is_abstract'])
    
    def test_element_bounds_validation(self):
        """Test element bounds validation."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            width=200,
            height=150,
            created_by=self.user
        )
        
        bounds = element.get_bounds()
        
        self.assertEqual(bounds['left'], 100)
        self.assertEqual(bounds['top'], 100)
        self.assertEqual(bounds['right'], 300)  # 100 + 200
        self.assertEqual(bounds['bottom'], 250)  # 100 + 150
    
    def test_element_collision_detection(self):
        """Test element collision detection."""
        element1 = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            width=200,
            height=150,
            created_by=self.user
        )
        
        element2 = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='Order',
            position_x=250,
            position_y=150,
            width=200,
            height=150,
            created_by=self.user
        )

        self.assertTrue(element1.overlaps_with(element2))
    
    def test_element_move(self):
        """Test element movement."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        element.move_to(200, 250)
        
        self.assertEqual(element.position_x, 200)
        self.assertEqual(element.position_y, 250)
    
    def test_element_resize(self):
        """Test element resizing."""
        element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            width=200,
            height=150,
            created_by=self.user
        )
        
        element.resize(300, 250)
        
        self.assertEqual(element.width, 300)
        self.assertEqual(element.height, 250)


class UMLRelationshipModelTestCase(TestCase):
    """Test cases for UMLRelationship model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
        
        self.source_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        self.target_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='Order',
            position_x=400,
            position_y=100,
            created_by=self.user
        )
    
    def test_relationship_creation(self):
        """Test basic relationship creation."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='ASSOCIATION',
            created_by=self.user
        )
        
        self.assertEqual(relationship.source_element, self.source_element)
        self.assertEqual(relationship.target_element, self.target_element)
        self.assertEqual(relationship.relationship_type, 'ASSOCIATION')
        self.assertEqual(relationship.diagram, self.diagram)
    
    def test_relationship_str_representation(self):
        """Test relationship string representation."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='INHERITANCE',
            created_by=self.user
        )
        
        expected_str = f'User -> Order (INHERITANCE)'
        self.assertEqual(str(relationship), expected_str)
    
    def test_relationship_properties_default(self):
        """Test default relationship properties."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='ASSOCIATION',
            created_by=self.user
        )
        
        self.assertIsNotNone(relationship.properties)
        self.assertIn('source_multiplicity', relationship.properties)
        self.assertIn('target_multiplicity', relationship.properties)
        self.assertIn('source_role', relationship.properties)
        self.assertIn('target_role', relationship.properties)
    
    def test_association_relationship_properties(self):
        """Test association relationship specific properties."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='ASSOCIATION',
            created_by=self.user,
            properties={
                'source_multiplicity': '1',
                'target_multiplicity': '*',
                'source_role': 'user',
                'target_role': 'orders',
                'navigability': 'bidirectional'
            }
        )
        
        self.assertEqual(relationship.properties['source_multiplicity'], '1')
        self.assertEqual(relationship.properties['target_multiplicity'], '*')
        self.assertEqual(relationship.properties['source_role'], 'user')
        self.assertEqual(relationship.properties['target_role'], 'orders')
    
    def test_self_relationship_prevention(self):
        """Test prevention of self-relationships."""
        with self.assertRaises(ValidationError):
            relationship = UMLRelationship(
                diagram=self.diagram,
                source_element=self.source_element,
                target_element=self.source_element,
                relationship_type='ASSOCIATION',
                created_by=self.user
            )
            relationship.full_clean()
    
    def test_relationship_validation(self):
        """Test relationship validation based on type."""

        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='INHERITANCE',
            created_by=self.user
        )

        try:
            relationship.validate_relationship()
        except Exception:
            self.fail("Relationship validation raised exception for valid inheritance")
    
    def test_relationship_path_calculation(self):
        """Test relationship path calculation for rendering."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='ASSOCIATION',
            created_by=self.user
        )
        
        path = relationship.calculate_connection_path()
        
        self.assertIn('start_point', path)
        self.assertIn('end_point', path)
        self.assertIn('control_points', path)
    
    def test_relationship_label_positioning(self):
        """Test relationship label positioning."""
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=self.source_element,
            target_element=self.target_element,
            relationship_type='ASSOCIATION',
            created_by=self.user,
            label='manages'
        )
        
        label_position = relationship.get_label_position()
        
        self.assertIn('x', label_position)
        self.assertIn('y', label_position)



class UMLDiagramComplexInteractionsTestCase(TestCase):
    """Test complex interactions between UML diagram components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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
        
        self.diagram = UMLDiagram.objects.create(
            name='Complex Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
    
    def test_diagram_element_cascade_delete(self):
        """Test cascade delete from diagram to elements and relationships."""

        user_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        order_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='Order',
            position_x=400,
            position_y=100,
            created_by=self.user
        )

        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=user_element,
            target_element=order_element,
            relationship_type='ASSOCIATION',
            created_by=self.user
        )
        
        element_id = user_element.id
        relationship_id = relationship.id

        self.diagram.delete()

        with self.assertRaises(UMLElement.DoesNotExist):
            UMLElement.objects.get(id=element_id)
        
        with self.assertRaises(UMLRelationship.DoesNotExist):
            UMLRelationship.objects.get(id=relationship_id)
    
    def test_element_relationship_cleanup(self):
        """Test relationship cleanup when element is deleted."""
        user_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        order_element = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='Order',
            position_x=400,
            position_y=100,
            created_by=self.user
        )
        
        relationship = UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=user_element,
            target_element=order_element,
            relationship_type='ASSOCIATION',
            created_by=self.user
        )
        
        relationship_id = relationship.id

        user_element.delete()

        with self.assertRaises(UMLRelationship.DoesNotExist):
            UMLRelationship.objects.get(id=relationship_id)
    
    def test_diagram_statistics_aggregation(self):
        """Test diagram statistics calculation."""

        UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user
        )
        
        UMLElement.objects.create(
            diagram=self.diagram,
            element_type='INTERFACE',
            name='UserService',
            position_x=400,
            position_y=100,
            created_by=self.user
        )
        
        UMLElement.objects.create(
            diagram=self.diagram,
            element_type='ABSTRACT_CLASS',
            name='BaseEntity',
            position_x=700,
            position_y=100,
            created_by=self.user
        )
        
        stats = self.diagram.get_diagram_statistics()
        
        self.assertEqual(stats['total_elements'], 3)
        self.assertEqual(stats['element_types']['CLASS'], 1)
        self.assertEqual(stats['element_types']['INTERFACE'], 1)
        self.assertEqual(stats['element_types']['ABSTRACT_CLASS'], 1)
    
    def test_diagram_validation_comprehensive(self):
        """Test comprehensive diagram validation."""

        user_class = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='User',
            position_x=100,
            position_y=100,
            created_by=self.user,
            properties={
                'attributes': [
                    {'name': 'id', 'type': 'Long', 'visibility': 'private'},
                    {'name': 'username', 'type': 'String', 'visibility': 'private'}
                ],
                'methods': [
                    {'name': 'getId', 'return_type': 'Long', 'visibility': 'public'}
                ]
            }
        )
        
        order_class = UMLElement.objects.create(
            diagram=self.diagram,
            element_type='CLASS',
            name='Order',
            position_x=400,
            position_y=100,
            created_by=self.user,
            properties={
                'attributes': [
                    {'name': 'id', 'type': 'Long', 'visibility': 'private'},
                    {'name': 'userId', 'type': 'Long', 'visibility': 'private'}
                ]
            }
        )
        
        UMLRelationship.objects.create(
            diagram=self.diagram,
            source_element=user_class,
            target_element=order_class,
            relationship_type='ASSOCIATION',
            created_by=self.user,
            properties={
                'source_multiplicity': '1',
                'target_multiplicity': '*'
            }
        )

        validation_result = self.diagram.validate_complete_diagram()
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        self.assertGreater(len(validation_result['warnings']), -1)  # May have warnings
