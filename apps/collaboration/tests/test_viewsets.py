"""
Comprehensive tests for Collaboration ViewSets.

Tests all collaboration endpoints including session management, participant management,
and real-time change events with full coverage.
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
    CollaborationSessionFactory,
    SessionParticipantFactory,
    UMLChangeEventFactory
)
from apps.collaboration.models import CollaborationSession, CollaborationParticipant

User = get_user_model()


class CollaborationSessionViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for CollaborationSessionViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for collaboration session tests."""
        super().setUpTestData()
        
        # Create workspace and project
        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)
        
        # Create UML diagram
        from apps.uml_diagrams.models import UMLDiagram
        cls.diagram = UMLDiagram.objects.create(
            project=cls.project,
            name='Test Diagram',
            diagram_type='class',
            created_by=cls.test_user
        )
        
        # Create collaboration session
        cls.session = CollaborationSessionFactory(
            project=cls.project,
            diagram=cls.diagram,
            host_user=cls.test_user
        )
        
        # Create other users for testing
        cls.participant_user = EnterpriseUserFactory(email='participant@ficct-enterprise.com')
        cls.viewer_user = EnterpriseUserFactory(email='viewer@ficct-enterprise.com')
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.sessions_url = reverse('collaboration:collaborationsession-list')
        self.session_detail_url = reverse('collaboration:collaborationsession-detail', args=[self.session.id])
    
    def test_list_collaboration_sessions(self):
        """Test listing collaboration sessions."""
        response = self.client.get(self.sessions_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 1)
        
        # Check session data structure
        session_data = response_data['results'][0]
        self.assertIn('id', session_data)
        self.assertIn('project', session_data)
        self.assertIn('diagram', session_data)
        self.assertIn('status', session_data)
    
    def test_retrieve_collaboration_session(self):
        """Test retrieving a specific collaboration session."""
        response = self.client.get(self.session_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.session.id))
        self.assertEqual(response_data['project']['id'], str(self.project.id))
        self.assertEqual(response_data['diagram']['id'], str(self.diagram.id))
        self.assertEqual(response_data['status'], 'ACTIVE')
    
    def test_create_collaboration_session(self):
        """Test creating a new collaboration session."""
        # Create another diagram for the new session
        from apps.uml_diagrams.models import UMLDiagram
        new_diagram = UMLDiagram.objects.create(
            project=self.project,
            name='New Test Diagram',
            diagram_type='sequence',
            created_by=self.test_user
        )
        
        data = {
            'project': str(self.project.id),
            'diagram': str(new_diagram.id),
            'session_data': {'mode': 'collaborative', 'max_participants': 10}
        }
        
        response = self.client.post(self.sessions_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['project']['id'], str(self.project.id))
        self.assertEqual(response_data['diagram']['id'], str(new_diagram.id))
        self.assertEqual(response_data['host_user']['id'], str(self.test_user.id))
        self.assertEqual(response_data['status'], 'ACTIVE')
    
    def test_create_collaboration_session_invalid_project(self):
        """Test creating session with invalid project."""
        data = {
            'project': str(uuid.uuid4()),  # Non-existent project
            'diagram': str(self.diagram.id),
            'session_data': {}
        }
        
        response = self.client.post(self.sessions_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_collaboration_session(self):
        """Test updating collaboration session."""
        data = {
            'session_data': {'mode': 'review', 'max_participants': 5},
            'status': 'PAUSED'
        }
        
        response = self.client.patch(self.session_detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['status'], 'PAUSED')
        self.assertEqual(response_data['session_data']['mode'], 'review')
    
    def test_delete_collaboration_session(self):
        """Test deleting collaboration session."""
        response = self.client.delete(self.session_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify session is deleted
        self.assertFalse(
            CollaborationSession.objects.filter(id=self.session.id).exists()
        )
    
    def test_end_session_action(self):
        """Test ending a collaboration session."""
        end_url = reverse('collaboration:collaborationsession-end-session', args=[self.session.id])
        
        response = self.client.post(end_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['status'], 'Session ended')
        
        # Verify session is ended
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'ENDED')
        self.assertIsNotNone(self.session.ended_at)
    
    def test_session_statistics_action(self):
        """Test retrieving session statistics."""
        # Add some participants
        SessionParticipantFactory(session=self.session, user=self.participant_user)
        SessionParticipantFactory(session=self.session, user=self.viewer_user)
        
        # Add some change events
        UMLChangeEventFactory(session=self.session, user=self.test_user)
        UMLChangeEventFactory(session=self.session, user=self.participant_user)
        
        stats_url = reverse('collaboration:collaborationsession-statistics', args=[self.session.id])
        
        response = self.client.get(stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        # Check statistics structure
        self.assertIn('participant_count', response_data)
        self.assertIn('change_events_count', response_data)
        self.assertIn('duration_minutes', response_data)
        self.assertIn('active_participants', response_data)
    
    def test_unauthorized_access(self):
        """Test unauthorized access to collaboration sessions."""
        # Create session owned by different user
        other_user = EnterpriseUserFactory(email='other@ficct-enterprise.com')
        other_workspace = WorkspaceFactory(owner=other_user)
        other_project = ProjectFactory(workspace=other_workspace, owner=other_user)
        
        from apps.uml_diagrams.models import UMLDiagram
        other_diagram = UMLDiagram.objects.create(
            project=other_project,
            name='Other Diagram',
            diagram_type='class',
            created_by=other_user
        )
        
        other_session = CollaborationSessionFactory(
            project=other_project,
            diagram=other_diagram,
            host_user=other_user
        )
        
        # Try to access other user's session
        other_session_url = reverse('collaboration:collaborationsession-detail', args=[other_session.id])
        response = self.client.get(other_session_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_access(self):
        """Test unauthenticated access to collaboration sessions."""
        self.logout_user()
        
        response = self.client.get(self.sessions_url)
        self.assert_unauthorized(response)


class SessionParticipantViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for SessionParticipantViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for session participant tests."""
        super().setUpTestData()
        
        # Create workspace, project, and diagram
        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)
        
        from apps.uml_diagrams.models import UMLDiagram
        cls.diagram = UMLDiagram.objects.create(
            project=cls.project,
            name='Test Diagram',
            diagram_type='class',
            created_by=cls.test_user
        )
        
        cls.session = CollaborationSessionFactory(
            project=cls.project,
            diagram=cls.diagram,
            host_user=cls.test_user
        )
        
        # Create participants
        cls.participant_user = EnterpriseUserFactory(email='participant@ficct-enterprise.com')
        cls.participant = SessionParticipantFactory(
            session=cls.session,
            user=cls.participant_user,
            role='EDITOR'
        )
        
        cls.viewer_user = EnterpriseUserFactory(email='viewer@ficct-enterprise.com')
        cls.viewer = SessionParticipantFactory(
            session=cls.session,
            user=cls.viewer_user,
            role='VIEWER'
        )
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.participants_url = reverse('collaboration:sessionparticipant-list')
        self.participant_detail_url = reverse(
            'collaboration:sessionparticipant-detail', 
            args=[self.participant.id]
        )
    
    def test_list_participants(self):
        """Test listing session participants."""
        response = self.client.get(self.participants_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 2)
    
    def test_retrieve_participant(self):
        """Test retrieving a specific participant."""
        response = self.client.get(self.participant_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.participant.id))
        self.assertEqual(response_data['user']['id'], str(self.participant_user.id))
        self.assertEqual(response_data['role'], 'EDITOR')
        self.assertTrue(response_data['is_active'])
    
    def test_create_participant(self):
        """Test adding a new participant to session."""
        new_user = EnterpriseUserFactory(email='newparticipant@ficct-enterprise.com')
        
        data = {
            'session': str(self.session.id),
            'user': str(new_user.id),
            'role': 'COMMENTER'
        }
        
        response = self.client.post(self.participants_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['user']['id'], str(new_user.id))
        self.assertEqual(response_data['role'], 'COMMENTER')
        self.assertTrue(response_data['is_active'])
    
    def test_update_participant_role(self):
        """Test updating participant role."""
        data = {
            'role': 'VIEWER'
        }
        
        response = self.client.patch(self.participant_detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['role'], 'VIEWER')
    
    def test_remove_participant(self):
        """Test removing participant from session."""
        response = self.client.delete(self.participant_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify participant is removed
        self.assertFalse(
            CollaborationParticipant.objects.filter(id=self.participant.id).exists()
        )
    
    def test_duplicate_participant(self):
        """Test adding duplicate participant to session."""
        data = {
            'session': str(self.session.id),
            'user': str(self.participant_user.id),  # Already a participant
            'role': 'VIEWER'
        }
        
        response = self.client.post(self.participants_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_role(self):
        """Test creating participant with invalid role."""
        new_user = EnterpriseUserFactory(email='invalidrole@ficct-enterprise.com')
        
        data = {
            'session': str(self.session.id),
            'user': str(new_user.id),
            'role': 'INVALID_ROLE'
        }
        
        response = self.client.post(self.participants_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UMLChangeEventViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for UMLChangeEventViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for UML change event tests."""
        super().setUpTestData()
        
        # Create workspace, project, and diagram
        cls.workspace = WorkspaceFactory(owner=cls.test_user)
        cls.project = ProjectFactory(workspace=cls.workspace, owner=cls.test_user)
        
        from apps.uml_diagrams.models import UMLDiagram
        cls.diagram = UMLDiagram.objects.create(
            project=cls.project,
            name='Test Diagram',
            diagram_type='class',
            created_by=cls.test_user
        )
        
        cls.session = CollaborationSessionFactory(
            project=cls.project,
            diagram=cls.diagram,
            host_user=cls.test_user
        )
        
        # Create change events
        cls.change_event = UMLChangeEventFactory(
            session=cls.session,
            user=cls.test_user,
            event_type='create',
            element_type='class'
        )
        
        cls.participant_user = EnterpriseUserFactory(email='participant@ficct-enterprise.com')
        cls.participant_event = UMLChangeEventFactory(
            session=cls.session,
            user=cls.participant_user,
            event_type='update',
            element_type='relationship'
        )
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.events_url = reverse('collaboration:umlchangeevent-list')
        self.event_detail_url = reverse(
            'collaboration:umlchangeevent-detail', 
            args=[self.change_event.id]
        )
    
    def test_list_change_events(self):
        """Test listing change events."""
        response = self.client.get(self.events_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertIn('results', response_data)
        self.assertTrue(len(response_data['results']) >= 2)
    
    def test_retrieve_change_event(self):
        """Test retrieving a specific change event."""
        response = self.client.get(self.event_detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertEqual(response_data['id'], str(self.change_event.id))
        self.assertEqual(response_data['event_type'], 'create')
        self.assertEqual(response_data['element_type'], 'class')
        self.assertEqual(response_data['user']['id'], str(self.test_user.id))
    
    def test_create_change_event(self):
        """Test creating a new change event."""
        data = {
            'session': str(self.session.id),
            'event_type': 'delete',
            'element_type': 'attribute',
            'element_id': str(uuid.uuid4()),
            'changes': {
                'name': 'deleted_attribute',
                'type': 'String'
            }
        }
        
        response = self.client.post(self.events_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertEqual(response_data['event_type'], 'delete')
        self.assertEqual(response_data['element_type'], 'attribute')
        self.assertEqual(response_data['user']['id'], str(self.test_user.id))
        self.assertEqual(response_data['changes']['name'], 'deleted_attribute')
    
    def test_create_change_event_invalid_session(self):
        """Test creating change event with invalid session."""
        data = {
            'session': str(uuid.uuid4()),  # Non-existent session
            'event_type': 'create',
            'element_type': 'class',
            'element_id': str(uuid.uuid4()),
            'changes': {}
        }
        
        response = self.client.post(self.events_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_filter_events_by_session(self):
        """Test filtering change events by session."""
        # Create another session and event
        other_session = CollaborationSessionFactory(
            project=self.project,
            diagram=self.diagram,
            host_user=self.test_user
        )
        UMLChangeEventFactory(session=other_session, user=self.test_user)
        
        # Filter by session
        response = self.client.get(f'{self.events_url}?session={self.session.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        # Should only return events from the specified session
        for event in response_data['results']:
            self.assertEqual(event['session']['id'], str(self.session.id))
    
    def test_filter_events_by_event_type(self):
        """Test filtering change events by event type."""
        # Create events with different types
        UMLChangeEventFactory(
            session=self.session, 
            user=self.test_user, 
            event_type='update'
        )
        UMLChangeEventFactory(
            session=self.session, 
            user=self.test_user, 
            event_type='delete'
        )
        
        # Filter by event type
        response = self.client.get(f'{self.events_url}?event_type=create')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        # Should only return 'create' events
        for event in response_data['results']:
            self.assertEqual(event['event_type'], 'create')
    
    def test_filter_events_by_user(self):
        """Test filtering change events by user."""
        response = self.client.get(f'{self.events_url}?user={self.test_user.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        # Should only return events from the specified user
        for event in response_data['results']:
            self.assertEqual(event['user']['id'], str(self.test_user.id))
    
    def test_order_events_by_timestamp(self):
        """Test ordering change events by timestamp."""
        response = self.client.get(f'{self.events_url}?ordering=-timestamp')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        # Should be ordered by timestamp descending
        timestamps = [event['timestamp'] for event in response_data['results']]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
    
    def test_change_event_validation(self):
        """Test change event field validation."""
        # Missing required fields
        data = {
            'session': str(self.session.id),
            # Missing event_type, element_type, element_id
            'changes': {}
        }
        
        response = self.client.post(self.events_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid event_type
        data = {
            'session': str(self.session.id),
            'event_type': 'invalid_type',
            'element_type': 'class',
            'element_id': str(uuid.uuid4()),
            'changes': {}
        }
        
        response = self.client.post(self.events_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_bulk_create_change_events(self):
        """Test creating multiple change events in batch."""
        events_data = [
            {
                'session': str(self.session.id),
                'event_type': 'create',
                'element_type': 'class',
                'element_id': str(uuid.uuid4()),
                'changes': {'name': 'Class1'}
            },
            {
                'session': str(self.session.id),
                'event_type': 'create',
                'element_type': 'class',
                'element_id': str(uuid.uuid4()),
                'changes': {'name': 'Class2'}
            }
        ]
        
        for event_data in events_data:
            response = self.client.post(self.events_url, event_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all events were created
        response = self.client.get(f'{self.events_url}?session={self.session.id}')
        self.assertTrue(len(response.json()['results']) >= 4)  # 2 original + 2 new
