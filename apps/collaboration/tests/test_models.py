"""
Tests for Collaboration app models - CollaborationSession, SessionParticipant, UMLChangeEvent.
"""

"""
Comprehensive tests for Collaboration models.

Tests all model functionality including validation, methods, and business logic.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid
import json

from ..models import CollaborationSession, SessionParticipant, UMLChangeEvent
from apps.projects.models import Project, Workspace
from apps.uml_diagrams.models import UMLDiagram

User = get_user_model()


class CollaborationSessionModelTestCase(TestCase):
    """Test cases for CollaborationSession model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.participant = User.objects.create_user(
            username='participant',
            email='participant@example.com',
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
        
        self.diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=self.project,
            created_by=self.owner
        )
    
    def test_session_creation(self):
        """Test basic session creation."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Team Design Session',
            created_by=self.owner,
            max_participants=10
        )
        
        self.assertEqual(session.diagram, self.diagram)
        self.assertEqual(session.session_name, 'Team Design Session')
        self.assertEqual(session.created_by, self.owner)
        self.assertEqual(session.status, 'ACTIVE')
        self.assertEqual(session.max_participants, 10)
    
    def test_session_str_representation(self):
        """Test session string representation."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Design Review',
            created_by=self.owner
        )
        
        expected_str = f'Design Review - {self.diagram.name}'
        self.assertEqual(str(session), expected_str)
    
    def test_session_settings_default(self):
        """Test default session settings."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Test Session',
            created_by=self.owner
        )
        
        self.assertIsNotNone(session.settings)
        self.assertIn('auto_save_interval', session.settings)
        self.assertIn('conflict_resolution', session.settings)
        self.assertIn('permissions', session.settings)
    
    def test_session_participant_management(self):
        """Test session participant management."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Test Session',
            created_by=self.owner
        )
        
        # Add participants
        participant1 = SessionParticipant.objects.create(
            session=session,
            user=self.participant,
            role='EDITOR'
        )
        
        participant2_user = User.objects.create_user(
            username='participant2',
            email='participant2@example.com',
            password='testpass123'
        )
        
        participant2 = SessionParticipant.objects.create(
            session=session,
            user=participant2_user,
            role='VIEWER'
        )
        
        self.assertEqual(session.get_participant_count(), 2)
        self.assertEqual(session.get_active_participant_count(), 2)
        self.assertTrue(session.is_user_participant(self.participant))
        self.assertTrue(session.is_user_participant(participant2_user))
    
    def test_session_capacity_limits(self):
        """Test session capacity enforcement."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Limited Session',
            created_by=self.owner,
            max_participants=1
        )
        
        # Add first participant
        SessionParticipant.objects.create(
            session=session,
            user=self.participant,
            role='EDITOR'
        )
        
        # Session should be at capacity
        self.assertTrue(session.is_at_capacity())
        
        # Should not be able to add another participant
        self.assertFalse(session.can_add_participant())
    
    def test_session_permissions(self):
        """Test session permission checking."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Test Session',
            created_by=self.owner
        )
        
        # Creator should have full permissions
        self.assertTrue(session.can_user_edit(self.owner))
        self.assertTrue(session.can_user_manage_participants(self.owner))
        
        # Non-participant should have no permissions
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.assertFalse(session.can_user_edit(other_user))
        self.assertFalse(session.can_user_view(other_user))
    
    def test_session_activity_tracking(self):
        """Test session activity tracking."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Test Session',
            created_by=self.owner
        )
        
        original_activity = session.last_activity_at
        
        session.update_activity()
        
        self.assertGreater(session.last_activity_at, original_activity)
    
    def test_session_end(self):
        """Test session ending."""
        session = CollaborationSession.objects.create(
            diagram=self.diagram,
            session_name='Test Session',
            created_by=self.owner
        )
        
        session.end_session()
        
        self.assertEqual(session.status, 'ENDED')
        self.assertIsNotNone(session.ended_at)


class SessionParticipantModelTestCase(TestCase):
    """Test cases for SessionParticipant model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.user = User.objects.create_user(
            username='participant',
            email='participant@example.com',
            password='testpass123'
        )
        
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.owner
        )
        
        project = Project.objects.create(
            name='Test Project',
            workspace=workspace,
            owner=self.owner
        )
        
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.owner
        )
        
        self.session = CollaborationSession.objects.create(
            diagram=diagram,
            session_name='Test Session',
            created_by=self.owner
        )
    
    def test_participant_creation(self):
        """Test basic participant creation."""
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        self.assertEqual(participant.session, self.session)
        self.assertEqual(participant.user, self.user)
        self.assertEqual(participant.role, 'EDITOR')
        self.assertEqual(participant.status, 'ACTIVE')
    
    def test_participant_str_representation(self):
        """Test participant string representation."""
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='VIEWER'
        )
        
        expected_str = f'{self.user.username} - {self.session.session_name} (VIEWER)'
        self.assertEqual(str(participant), expected_str)
    
    def test_participant_unique_constraint(self):
        """Test unique constraint on session-user combination."""
        SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        # Should not be able to create duplicate participation
        with self.assertRaises(IntegrityError):
            SessionParticipant.objects.create(
                session=self.session,
                user=self.user,
                role='VIEWER'
            )
    
    def test_participant_permissions(self):
        """Test participant permission methods."""
        editor = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        viewer = SessionParticipant.objects.create(
            session=self.session,
            user=User.objects.create_user(
                username='viewer',
                email='viewer@example.com',
                password='testpass123'
            ),
            role='VIEWER'
        )
        
        # Editor permissions
        self.assertTrue(editor.can_edit())
        self.assertTrue(editor.can_view())
        self.assertFalse(editor.can_manage_participants())
        
        # Viewer permissions
        self.assertFalse(viewer.can_edit())
        self.assertTrue(viewer.can_view())
        self.assertFalse(viewer.can_manage_participants())
    
    def test_participant_activity_tracking(self):
        """Test participant activity tracking."""
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        original_activity = participant.last_activity_at
        
        participant.update_activity()
        
        self.assertGreater(participant.last_activity_at, original_activity)
    
    def test_participant_cursor_tracking(self):
        """Test participant cursor position tracking."""
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        cursor_position = {'x': 100, 'y': 200, 'element_id': 'class1'}
        
        participant.update_cursor_position(cursor_position)
        
        self.assertEqual(participant.cursor_position, cursor_position)
    
    def test_participant_leave_session(self):
        """Test participant leaving session."""
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.user,
            role='EDITOR'
        )
        
        participant.leave_session()
        
        self.assertEqual(participant.status, 'LEFT')
        self.assertIsNotNone(participant.left_at)


class UMLChangeEventModelTestCase(TestCase):
    """Test cases for UMLChangeEvent model."""
    
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
        
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.user
        )
        
        self.session = CollaborationSession.objects.create(
            diagram=diagram,
            session_name='Test Session',
            created_by=self.user
        )
    
    def test_change_event_creation(self):
        """Test basic change event creation."""
        change_data = {
            'action': 'create_element',
            'element_type': 'class',
            'element_id': 'class1',
            'properties': {
                'name': 'User',
                'position': {'x': 100, 'y': 100}
            }
        }
        
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_CREATED',
            change_data=change_data
        )
        
        self.assertEqual(event.session, self.session)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.event_type, 'ELEMENT_CREATED')
        self.assertEqual(event.change_data, change_data)
    
    def test_change_event_str_representation(self):
        """Test change event string representation."""
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_MODIFIED',
            change_data={'element_id': 'class1'}
        )
        
        expected_str = f'{self.user.username} - ELEMENT_MODIFIED at {event.timestamp}'
        self.assertEqual(str(event), expected_str)
    
    def test_element_creation_event(self):
        """Test element creation event."""
        change_data = {
            'action': 'create_element',
            'element_type': 'class',
            'element_id': 'user_class',
            'properties': {
                'name': 'User',
                'position': {'x': 150, 'y': 200},
                'size': {'width': 200, 'height': 150}
            }
        }
        
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_CREATED',
            change_data=change_data
        )
        
        self.assertEqual(event.change_data['action'], 'create_element')
        self.assertEqual(event.change_data['element_id'], 'user_class')
        self.assertEqual(event.change_data['properties']['name'], 'User')
    
    def test_element_modification_event(self):
        """Test element modification event."""
        change_data = {
            'action': 'modify_element',
            'element_id': 'user_class',
            'changes': {
                'name': {'old': 'User', 'new': 'UserEntity'},
                'position': {
                    'old': {'x': 100, 'y': 100},
                    'new': {'x': 150, 'y': 120}
                }
            }
        }
        
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_MODIFIED',
            change_data=change_data
        )
        
        self.assertEqual(event.change_data['action'], 'modify_element')
        self.assertIn('changes', event.change_data)
        self.assertIn('name', event.change_data['changes'])
    
    def test_relationship_creation_event(self):
        """Test relationship creation event."""
        change_data = {
            'action': 'create_relationship',
            'relationship_id': 'rel1',
            'source_element_id': 'user_class',
            'target_element_id': 'order_class',
            'relationship_type': 'association',
            'properties': {
                'multiplicity': {'source': '1', 'target': '*'}
            }
        }
        
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='RELATIONSHIP_CREATED',
            change_data=change_data
        )
        
        self.assertEqual(event.event_type, 'RELATIONSHIP_CREATED')
        self.assertEqual(event.change_data['relationship_type'], 'association')
    
    def test_change_event_ordering(self):
        """Test change event ordering by timestamp."""
        # Create events with slight time differences
        event1 = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_CREATED',
            change_data={'element_id': 'class1'}
        )
        
        event2 = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_MODIFIED',
            change_data={'element_id': 'class1'}
        )
        
        events = UMLChangeEvent.objects.filter(session=self.session).order_by('timestamp')
        
        self.assertEqual(events.first(), event1)
        self.assertEqual(events.last(), event2)
    
    def test_change_event_filtering_by_type(self):
        """Test filtering change events by type."""
        UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_CREATED',
            change_data={'element_id': 'class1'}
        )
        
        UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_MODIFIED',
            change_data={'element_id': 'class1'}
        )
        
        UMLChangeEvent.objects.create(
            session=self.session,
            user=self.user,
            event_type='RELATIONSHIP_CREATED',
            change_data={'relationship_id': 'rel1'}
        )
        
        element_events = UMLChangeEvent.objects.filter(
            session=self.session,
            event_type__startswith='ELEMENT'
        )
        
        self.assertEqual(element_events.count(), 2)
    
    def test_change_event_validation(self):
        """Test change event data validation."""
        # Valid event should not raise exception
        valid_event = UMLChangeEvent(
            session=self.session,
            user=self.user,
            event_type='ELEMENT_CREATED',
            change_data={
                'action': 'create_element',
                'element_id': 'valid_class'
            }
        )
        
        try:
            valid_event.full_clean()
        except ValidationError:
            self.fail("Valid change event raised ValidationError")


class CollaborationModelRelationshipsTestCase(TestCase):
    """Test relationships and interactions between collaboration models."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        
        workspace = Workspace.objects.create(
            name='Test Workspace',
            workspace_type='TEAM',
            owner=self.owner
        )
        
        project = Project.objects.create(
            name='Test Project',
            workspace=workspace,
            owner=self.owner
        )
        
        diagram = UMLDiagram.objects.create(
            name='Test Diagram',
            diagram_type='CLASS',
            project=project,
            created_by=self.owner
        )
        
        self.session = CollaborationSession.objects.create(
            diagram=diagram,
            session_name='Test Session',
            created_by=self.owner
        )
    
    def test_session_cascade_delete_participants(self):
        """Test cascade delete from session to participants."""
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=user1,
            role='EDITOR'
        )
        
        participant_id = participant.id
        
        # Delete session
        self.session.delete()
        
        # Participant should be deleted
        with self.assertRaises(SessionParticipant.DoesNotExist):
            SessionParticipant.objects.get(id=participant_id)
    
    def test_session_cascade_delete_events(self):
        """Test cascade delete from session to change events."""
        event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.owner,
            event_type='ELEMENT_CREATED',
            change_data={'element_id': 'class1'}
        )
        
        event_id = event.id
        
        # Delete session
        self.session.delete()
        
        # Event should be deleted
        with self.assertRaises(UMLChangeEvent.DoesNotExist):
            UMLChangeEvent.objects.get(id=event_id)
    
    def test_collaboration_statistics(self):
        """Test collaboration statistics aggregation."""
        # Add participants
        for i in range(3):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            SessionParticipant.objects.create(
                session=self.session,
                user=user,
                role='EDITOR'
            )
        
        # Add change events
        for i in range(5):
            UMLChangeEvent.objects.create(
                session=self.session,
                user=self.owner,
                event_type='ELEMENT_CREATED',
                change_data={'element_id': f'class{i}'}
            )
        
        stats = self.session.get_session_statistics()
        
        self.assertEqual(stats['participant_count'], 3)
        self.assertEqual(stats['change_event_count'], 5)
        self.assertIn('activity_timeline', stats)
    
    def test_collaborative_editing_workflow(self):
        """Test complete collaborative editing workflow."""
        # Add participant
        editor = User.objects.create_user(
            username='editor',
            email='editor@example.com',
            password='testpass123'
        )
        
        participant = SessionParticipant.objects.create(
            session=self.session,
            user=editor,
            role='EDITOR'
        )
        
        # Simulate editing sequence
        events = [
            {
                'type': 'ELEMENT_CREATED',
                'data': {
                    'action': 'create_element',
                    'element_id': 'user_class',
                    'element_type': 'class'
                }
            },
            {
                'type': 'ELEMENT_MODIFIED',
                'data': {
                    'action': 'modify_element',
                    'element_id': 'user_class',
                    'changes': {'name': {'old': 'User', 'new': 'UserEntity'}}
                }
            },
            {
                'type': 'RELATIONSHIP_CREATED',
                'data': {
                    'action': 'create_relationship',
                    'relationship_id': 'rel1',
                    'source_element_id': 'user_class',
                    'target_element_id': 'order_class'
                }
            }
        ]
        
        created_events = []
        for event_data in events:
            event = UMLChangeEvent.objects.create(
                session=self.session,
                user=editor,
                event_type=event_data['type'],
                change_data=event_data['data']
            )
            created_events.append(event)
            
            # Update participant activity
            participant.update_activity()
        
        # Verify complete workflow
        self.assertEqual(len(created_events), 3)
        self.assertEqual(UMLChangeEvent.objects.filter(session=self.session).count(), 3)
        
        # Check event sequence
        ordered_events = UMLChangeEvent.objects.filter(
            session=self.session
        ).order_by('timestamp')
        
        self.assertEqual(ordered_events[0].event_type, 'ELEMENT_CREATED')
        self.assertEqual(ordered_events[1].event_type, 'ELEMENT_MODIFIED')
        self.assertEqual(ordered_events[2].event_type, 'RELATIONSHIP_CREATED')
