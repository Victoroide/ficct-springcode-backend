"""
Comprehensive Unit Tests for Collaboration Endpoints

Tests for ALL collaboration endpoints including CollaborationSessionViewSet,
SessionParticipantViewSet, and UMLChangeEventViewSet with full CRUD operations.
"""

import json
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from base.test_base import BaseTestCase
from base.test_factories import EnterpriseUserFactory
from apps.collaboration.models import CollaborationSession, SessionParticipant, UMLChangeEvent
from apps.projects.models import Project

User = get_user_model()


class CollaborationSessionViewSetTestCase(BaseTestCase):
    """Test cases for CollaborationSessionViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for collaboration',
            owner=self.test_user
        )
        
        # Create test collaboration session
        self.session = CollaborationSession.objects.create(
            name='Test Session',
            project=self.project,
            created_by=self.test_user,
            is_active=True
        )
        
        # Base URL for sessions
        self.base_url = '/api/v1/sessions/'
    
    def test_list_sessions_success(self):
        """Test GET /api/v1/sessions/ returns list of sessions."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        # If paginated, check results key
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertIsInstance(response.data['results'], list)
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_list_sessions_unauthenticated(self):
        """Test sessions list without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_session_success(self):
        """Test POST /api/v1/sessions/ creates new session."""
        data = {
            'name': 'New Collaboration Session',
            'project': self.project.id,
            'description': 'New session for testing',
            'is_active': True
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Collaboration Session')
        self.assertEqual(response.data['project'], self.project.id)
    
    def test_create_session_missing_required_fields(self):
        """Test creating session with missing required fields."""
        data = {
            'name': 'Incomplete Session'
            # Missing project
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_session_invalid_project(self):
        """Test creating session with invalid project ID."""
        data = {
            'name': 'Invalid Project Session',
            'project': 99999,  # Non-existent project
            'description': 'Session with invalid project'
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_session_success(self):
        """Test GET /api/v1/sessions/{id}/ returns specific session."""
        url = f'{self.base_url}{self.session.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.session.id)
        self.assertEqual(response.data['name'], self.session.name)
    
    def test_retrieve_session_not_found(self):
        """Test retrieving non-existent session."""
        url = f'{self.base_url}99999/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_session_success(self):
        """Test PUT/PATCH /api/v1/sessions/{id}/ updates session."""
        url = f'{self.base_url}{self.session.id}/'
        data = {
            'name': 'Updated Session Name',
            'description': 'Updated description',
            'is_active': False
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Session Name')
        self.assertEqual(response.data['description'], 'Updated description')
        self.assertFalse(response.data['is_active'])
    
    def test_update_session_partial(self):
        """Test partial update of session."""
        url = f'{self.base_url}{self.session.id}/'
        data = {
            'name': 'Partially Updated Session'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Partially Updated Session')
        # Other fields should remain unchanged
        self.assertEqual(response.data['project'], self.project.id)
    
    def test_update_session_not_found(self):
        """Test updating non-existent session."""
        url = f'{self.base_url}99999/'
        data = {'name': 'Updated Name'}
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_session_success(self):
        """Test DELETE /api/v1/sessions/{id}/ deletes session."""
        # Create a session to delete
        session_to_delete = CollaborationSession.objects.create(
            name='Session to Delete',
            project=self.project,
            created_by=self.test_user
        )
        
        url = f'{self.base_url}{session_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify session is deleted
        self.assertFalse(
            CollaborationSession.objects.filter(id=session_to_delete.id).exists()
        )
    
    def test_delete_session_not_found(self):
        """Test deleting non-existent session."""
        url = f'{self.base_url}99999/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_session_permissions(self):
        """Test session access permissions."""
        # Create another user
        other_user = EnterpriseUserFactory()
        
        # Create session owned by other user
        other_project = Project.objects.create(
            name='Other Project',
            description='Project owned by other user',
            owner=other_user
        )
        
        other_session = CollaborationSession.objects.create(
            name='Other Session',
            project=other_project,
            created_by=other_user
        )
        
        # Try to access other user's session
        url = f'{self.base_url}{other_session.id}/'
        response = self.client.get(url)
        
        # Depending on permission logic, this might be 403 or 404
        self.assertIn(response.status_code, [403, 404])


class SessionParticipantViewSetTestCase(BaseTestCase):
    """Test cases for SessionParticipantViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and session
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for collaboration',
            owner=self.test_user
        )
        
        self.session = CollaborationSession.objects.create(
            name='Test Session',
            project=self.project,
            created_by=self.test_user,
            is_active=True
        )
        
        # Create test participant
        self.participant = SessionParticipant.objects.create(
            session=self.session,
            user=self.test_user,
            role='owner',
            joined_at='2024-01-01T00:00:00Z'
        )
        
        # Base URL for participants
        self.base_url = '/api/v1/participants/'
    
    def test_list_participants_success(self):
        """Test GET /api/v1/participants/ returns list of participants."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        # If paginated, check results key
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertIsInstance(response.data['results'], list)
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_participant_success(self):
        """Test POST /api/v1/participants/ creates new participant."""
        # Create another user to add as participant
        new_user = EnterpriseUserFactory()
        
        data = {
            'session': self.session.id,
            'user': new_user.id,
            'role': 'viewer'
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session'], self.session.id)
        self.assertEqual(response.data['user'], new_user.id)
        self.assertEqual(response.data['role'], 'viewer')
    
    def test_create_participant_duplicate(self):
        """Test creating duplicate participant."""
        data = {
            'session': self.session.id,
            'user': self.test_user.id,
            'role': 'editor'
        }
        
        response = self.client.post(self.base_url, data)
        
        # Should fail due to unique constraint
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_participant_success(self):
        """Test GET /api/v1/participants/{id}/ returns specific participant."""
        url = f'{self.base_url}{self.participant.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.participant.id)
        self.assertEqual(response.data['user'], self.test_user.id)
    
    def test_update_participant_role(self):
        """Test updating participant role."""
        url = f'{self.base_url}{self.participant.id}/'
        data = {
            'role': 'editor'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'editor')
    
    def test_delete_participant_success(self):
        """Test DELETE /api/v1/participants/{id}/ removes participant."""
        # Create a participant to delete
        new_user = EnterpriseUserFactory()
        participant_to_delete = SessionParticipant.objects.create(
            session=self.session,
            user=new_user,
            role='viewer'
        )
        
        url = f'{self.base_url}{participant_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify participant is deleted
        self.assertFalse(
            SessionParticipant.objects.filter(id=participant_to_delete.id).exists()
        )


class UMLChangeEventViewSetTestCase(BaseTestCase):
    """Test cases for UMLChangeEventViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project and session
        self.project = Project.objects.create(
            name='Test Project',
            description='Test project for collaboration',
            owner=self.test_user
        )
        
        self.session = CollaborationSession.objects.create(
            name='Test Session',
            project=self.project,
            created_by=self.test_user,
            is_active=True
        )
        
        # Create test change event
        self.change_event = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.test_user,
            event_type='element_created',
            element_type='class',
            element_id='class_123',
            change_data={'name': 'TestClass', 'attributes': []},
            timestamp='2024-01-01T00:00:00Z'
        )
        
        # Base URL for events
        self.base_url = '/api/v1/events/'
    
    def test_list_events_success(self):
        """Test GET /api/v1/events/ returns list of change events."""
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
        
        # If paginated, check results key
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertIsInstance(response.data['results'], list)
            self.assertGreaterEqual(len(response.data['results']), 1)
        else:
            self.assertGreaterEqual(len(response.data), 1)
    
    def test_create_event_success(self):
        """Test POST /api/v1/events/ creates new change event."""
        data = {
            'session': self.session.id,
            'event_type': 'element_modified',
            'element_type': 'class',
            'element_id': 'class_456',
            'change_data': {
                'name': 'ModifiedClass',
                'attributes': ['attr1', 'attr2']
            }
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session'], self.session.id)
        self.assertEqual(response.data['event_type'], 'element_modified')
        self.assertEqual(response.data['element_type'], 'class')
        self.assertEqual(response.data['element_id'], 'class_456')
    
    def test_create_event_invalid_event_type(self):
        """Test creating event with invalid event type."""
        data = {
            'session': self.session.id,
            'event_type': 'invalid_event_type',
            'element_type': 'class',
            'element_id': 'class_789',
            'change_data': {}
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_event_missing_required_fields(self):
        """Test creating event with missing required fields."""
        data = {
            'session': self.session.id,
            'event_type': 'element_created'
            # Missing element_type, element_id
        }
        
        response = self.client.post(self.base_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_retrieve_event_success(self):
        """Test GET /api/v1/events/{id}/ returns specific event."""
        url = f'{self.base_url}{self.change_event.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.change_event.id)
        self.assertEqual(response.data['event_type'], 'element_created')
        self.assertEqual(response.data['element_id'], 'class_123')
    
    def test_update_event_success(self):
        """Test PUT/PATCH /api/v1/events/{id}/ updates event."""
        url = f'{self.base_url}{self.change_event.id}/'
        data = {
            'change_data': {
                'name': 'UpdatedClass',
                'attributes': ['new_attr']
            }
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['change_data']['name'],
            'UpdatedClass'
        )
    
    def test_delete_event_success(self):
        """Test DELETE /api/v1/events/{id}/ deletes event."""
        # Create an event to delete
        event_to_delete = UMLChangeEvent.objects.create(
            session=self.session,
            user=self.test_user,
            event_type='element_deleted',
            element_type='class',
            element_id='class_to_delete',
            change_data={}
        )
        
        url = f'{self.base_url}{event_to_delete.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify event is deleted
        self.assertFalse(
            UMLChangeEvent.objects.filter(id=event_to_delete.id).exists()
        )
    
    def test_filter_events_by_session(self):
        """Test filtering events by session."""
        # Create another session and event
        other_session = CollaborationSession.objects.create(
            name='Other Session',
            project=self.project,
            created_by=self.test_user
        )
        
        UMLChangeEvent.objects.create(
            session=other_session,
            user=self.test_user,
            event_type='element_created',
            element_type='interface',
            element_id='interface_123',
            change_data={}
        )
        
        # Filter by session
        response = self.client.get(f'{self.base_url}?session={self.session.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only events from the specified session are returned
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            events = data['results']
        else:
            events = data
        
        for event in events:
            self.assertEqual(event['session'], self.session.id)
    
    def test_filter_events_by_event_type(self):
        """Test filtering events by event type."""
        # Create events with different types
        UMLChangeEvent.objects.create(
            session=self.session,
            user=self.test_user,
            event_type='element_deleted',
            element_type='class',
            element_id='deleted_class',
            change_data={}
        )
        
        # Filter by event type
        response = self.client.get(f'{self.base_url}?event_type=element_created')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only events with specified type are returned
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            events = data['results']
        else:
            events = data
        
        for event in events:
            self.assertEqual(event['event_type'], 'element_created')


class CollaborationErrorHandlingTestCase(BaseTestCase):
    """Test cases for collaboration error handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in requests."""
        response = self.client.post(
            '/api/v1/sessions/',
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_method_not_allowed(self):
        """Test method not allowed responses."""
        # Assuming some endpoints don't support certain methods
        response = self.client.trace('/api/v1/sessions/')
        
        # Should return method not allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_large_payload_handling(self):
        """Test handling of large payloads."""
        # Create a large change_data payload
        large_data = {
            'session': 1,
            'event_type': 'element_created',
            'element_type': 'class',
            'element_id': 'large_class',
            'change_data': {
                'large_field': 'x' * 10000  # 10KB string
            }
        }
        
        response = self.client.post('/api/v1/events/', large_data, format='json')
        
        # Should handle gracefully, either success or appropriate error
        self.assertIn(response.status_code, [201, 400, 413])


class CollaborationPermissionsTestCase(BaseTestCase):
    """Test cases for collaboration permissions."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access endpoints."""
        endpoints = [
            '/api/v1/sessions/',
            '/api/v1/participants/',
            '/api/v1/events/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test that authenticated users can access endpoints."""
        self.client.force_authenticate(user=self.test_user)
        
        endpoints = [
            '/api/v1/sessions/',
            '/api/v1/participants/',
            '/api/v1/events/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should not return 401/403
            self.assertNotIn(response.status_code, [401, 403])


class CollaborationIntegrationTestCase(BaseTestCase):
    """Integration test cases for collaboration workflow."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Create test project
        self.project = Project.objects.create(
            name='Integration Test Project',
            description='Project for integration testing',
            owner=self.test_user
        )
    
    def test_complete_collaboration_workflow(self):
        """Test complete collaboration workflow."""
        # 1. Create collaboration session
        session_data = {
            'name': 'Integration Test Session',
            'project': self.project.id,
            'description': 'Session for integration testing',
            'is_active': True
        }
        
        session_response = self.client.post('/api/v1/sessions/', session_data)
        self.assertEqual(session_response.status_code, status.HTTP_201_CREATED)
        session_id = session_response.data['id']
        
        # 2. Add participant to session
        participant_data = {
            'session': session_id,
            'user': self.test_user.id,
            'role': 'owner'
        }
        
        participant_response = self.client.post('/api/v1/participants/', participant_data)
        self.assertEqual(participant_response.status_code, status.HTTP_201_CREATED)
        
        # 3. Create change event
        event_data = {
            'session': session_id,
            'event_type': 'element_created',
            'element_type': 'class',
            'element_id': 'integration_class',
            'change_data': {
                'name': 'IntegrationTestClass',
                'attributes': ['id', 'name']
            }
        }
        
        event_response = self.client.post('/api/v1/events/', event_data)
        self.assertEqual(event_response.status_code, status.HTTP_201_CREATED)
        
        # 4. Verify all components are created and linked
        # Check session exists
        session_check = self.client.get(f'/api/v1/sessions/{session_id}/')
        self.assertEqual(session_check.status_code, status.HTTP_200_OK)
        
        # Check participant exists
        participants_check = self.client.get(f'/api/v1/participants/?session={session_id}')
        self.assertEqual(participants_check.status_code, status.HTTP_200_OK)
        
        # Check event exists
        events_check = self.client.get(f'/api/v1/events/?session={session_id}')
        self.assertEqual(events_check.status_code, status.HTTP_200_OK)
