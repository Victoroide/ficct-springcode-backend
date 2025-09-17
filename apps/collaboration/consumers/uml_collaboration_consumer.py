"""
WebSocket consumer for real-time UML collaboration.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from ..services import CollaborationService, ConflictResolutionService, BroadcastService
from ..models import CollaborationSession, ChangeEvent, DiagramLock

User = get_user_model()
logger = logging.getLogger('collaboration')


class UMLCollaborationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time UML diagram collaboration.
    
    Handles:
    - Session management and participant tracking
    - Real-time change broadcasting
    - Element locking and conflict resolution
    - Operational transformation for concurrent edits
    """
    
    async def connect(self):
        """Establish collaboration session connection."""
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.diagram_id = self.scope['url_route']['kwargs'].get('diagram_id')
        self.user = self.scope['user']
        self.session = None
        self.room_group_name = f'collaboration_{self.project_id}_{self.diagram_id}'
        
        # Authenticate user
        if not self.user or not self.user.is_authenticated:
            logger.warning(f"Unauthenticated WebSocket connection attempt for project {self.project_id}")
            await self.close(code=4001)
            return
        
        try:
            # Get or create collaboration session
            self.session = await self.get_or_create_session()
            
            # Add user to session
            await self.add_user_to_session()
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Broadcast user joined event
            await self.broadcast_user_joined()
            
            # Send current session state to new participant
            await self.send_session_state()
            
            logger.info(f"User {self.user.corporate_email} joined collaboration session {self.session.id}")
            
        except Exception as e:
            logger.error(f"Failed to establish collaboration connection: {str(e)}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Clean up when user disconnects from collaboration session."""
        if hasattr(self, 'room_group_name'):
            # Remove user from session
            if self.session:
                await self.remove_user_from_session()
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Broadcast user left event
            await self.broadcast_user_left()
            
            logger.info(f"User {self.user.corporate_email} left collaboration session")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Route message to appropriate handler
            handler_map = {
                'diagram_change': self.handle_diagram_change,
                'acquire_lock': self.handle_acquire_lock,
                'release_lock': self.handle_release_lock,
                'cursor_update': self.handle_cursor_update,
                'sync_request': self.handle_sync_request,
                'conflict_resolution': self.handle_conflict_resolution,
                'auto_save': self.handle_auto_save,
            }
            
            handler = handler_map.get(message_type)
            if handler:
                await handler(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send_error("Message processing failed")
    
    async def handle_diagram_change(self, data):
        """Handle real-time diagram changes."""
        try:
            change_data = data.get('change_data', {})
            element_id = change_data.get('element_id')
            event_type = data.get('event_type', 'ELEMENT_UPDATED')
            
            # Check if user can edit this element
            can_edit = await self.check_edit_permission(element_id)
            if not can_edit:
                await self.send_error("Element is locked by another user")
                return
            
            # Create change event
            change_event = await self.create_change_event(
                event_type=event_type,
                element_id=element_id,
                element_type=change_data.get('element_type', 'unknown'),
                change_data=change_data
            )
            
            # Apply operational transformation
            transformed_event = await self.apply_operational_transformation(change_event)
            
            # Broadcast change to all participants
            await self.broadcast_change(transformed_event)
            
            # Auto-save diagram state
            await self.trigger_auto_save()
            
        except Exception as e:
            logger.error(f"Error handling diagram change: {str(e)}")
            await self.send_error("Failed to process diagram change")
    
    async def handle_acquire_lock(self, data):
        """Handle element lock acquisition."""
        try:
            element_id = data.get('element_id')
            lock_type = data.get('lock_type', 'ELEMENT')
            duration = data.get('duration_minutes', 5)
            
            lock = await self.acquire_element_lock(element_id, lock_type, duration)
            
            if lock:
                await self.send(text_data=json.dumps({
                    'type': 'lock_acquired',
                    'element_id': element_id,
                    'lock_id': str(lock.id),
                    'expires_at': lock.expires_at.isoformat()
                }))
                
                # Broadcast lock to other participants
                await self.broadcast_lock_acquired(lock)
            else:
                await self.send_error("Failed to acquire lock - element may already be locked")
                
        except Exception as e:
            logger.error(f"Error acquiring lock: {str(e)}")
            await self.send_error("Lock acquisition failed")
    
    async def handle_release_lock(self, data):
        """Handle element lock release."""
        try:
            element_id = data.get('element_id')
            
            released = await self.release_element_lock(element_id)
            
            if released:
                await self.send(text_data=json.dumps({
                    'type': 'lock_released',
                    'element_id': element_id
                }))
                
                # Broadcast lock release
                await self.broadcast_lock_released(element_id)
            
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            await self.send_error("Lock release failed")
    
    async def handle_cursor_update(self, data):
        """Handle cursor position updates."""
        try:
            cursor_data = data.get('cursor_data', {})
            
            await self.update_cursor_position(cursor_data)
            
            # Broadcast cursor update to other participants
            await self.broadcast_cursor_update(cursor_data)
            
        except Exception as e:
            logger.error(f"Error handling cursor update: {str(e)}")
    
    async def handle_sync_request(self, data):
        """Handle synchronization requests from clients."""
        try:
            last_sequence = data.get('last_sequence_number', 0)
            
            # Get events since last known sequence
            events = await self.get_events_since(last_sequence)
            
            await self.send(text_data=json.dumps({
                'type': 'sync_response',
                'events': [event.get_broadcast_data() for event in events],
                'current_sequence': await self.get_current_sequence()
            }))
            
        except Exception as e:
            logger.error(f"Error handling sync request: {str(e)}")
            await self.send_error("Synchronization failed")
    
    async def handle_conflict_resolution(self, data):
        """Handle conflict resolution decisions."""
        try:
            conflict_id = data.get('conflict_id')
            resolution = data.get('resolution')
            
            await self.resolve_conflict(conflict_id, resolution)
            
        except Exception as e:
            logger.error(f"Error handling conflict resolution: {str(e)}")
            await self.send_error("Conflict resolution failed")
    
    async def handle_auto_save(self, data):
        """Handle auto-save requests."""
        try:
            diagram_data = data.get('diagram_data')
            
            saved = await self.save_diagram_state(diagram_data)
            
            if saved:
                await self.send(text_data=json.dumps({
                    'type': 'auto_save_complete',
                    'timestamp': saved.updated_at.isoformat()
                }))
                
                # Broadcast save notification
                await self.broadcast_diagram_saved()
            
        except Exception as e:
            logger.error(f"Error handling auto-save: {str(e)}")
            await self.send_error("Auto-save failed")
    
    # WebSocket group message handlers
    
    async def change_broadcast(self, event):
        """Handle change broadcast from group."""
        await self.send(text_data=json.dumps({
            'type': 'diagram_change',
            'change_event': event['change_data']
        }))
    
    async def user_joined(self, event):
        """Handle user joined broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_data': event['user_data']
        }))
    
    async def user_left(self, event):
        """Handle user left broadcast.""" 
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id']
        }))
    
    async def lock_acquired(self, event):
        """Handle lock acquired broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'element_locked',
            'lock_data': event['lock_data']
        }))
    
    async def lock_released(self, event):
        """Handle lock released broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'element_unlocked',
            'element_id': event['element_id']
        }))
    
    async def cursor_moved(self, event):
        """Handle cursor movement broadcast."""
        if event.get('user_id') != str(self.user.id):  # Don't echo own cursor
            await self.send(text_data=json.dumps({
                'type': 'cursor_update',
                'cursor_data': event['cursor_data']
            }))
    
    async def diagram_saved(self, event):
        """Handle diagram saved broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'diagram_saved',
            'save_data': event['save_data']
        }))
    
    # Helper methods
    
    async def send_error(self, message: str):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
    
    @database_sync_to_async
    def get_or_create_session(self):
        """Get or create collaboration session."""
        collaboration_service = CollaborationService()
        return collaboration_service.get_or_create_session(
            project_id=self.project_id,
            diagram_id=self.diagram_id,
            user=self.user
        )
    
    @database_sync_to_async  
    def add_user_to_session(self):
        """Add user to collaboration session."""
        return self.session.add_participant(self.user)
    
    @database_sync_to_async
    def remove_user_from_session(self):
        """Remove user from collaboration session."""
        return self.session.remove_participant(self.user)
    
    async def broadcast_user_joined(self):
        """Broadcast user joined event to group."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_data': {
                    'user_id': str(self.user.id),
                    'user_name': self.user.full_name,
                    'user_email': self.user.corporate_email,
                    'joined_at': self.session.created_at.isoformat()
                }
            }
        )
    
    async def broadcast_user_left(self):
        """Broadcast user left event to group."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_left',
                'user_id': str(self.user.id)
            }
        )
    
    async def broadcast_change(self, change_event):
        """Broadcast diagram change to all participants."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'change_broadcast',
                'change_data': change_event.get_broadcast_data()
            }
        )
    
    @database_sync_to_async
    def create_change_event(self, event_type: str, element_id: str, 
                           element_type: str, change_data: dict):
        """Create change event in database."""
        return ChangeEvent.create_event(
            session=self.session,
            diagram=self.session.diagram,
            user=self.user,
            event_type=event_type,
            element_id=element_id,
            element_type=element_type,
            change_data=change_data
        )
    
    @database_sync_to_async
    def apply_operational_transformation(self, change_event):
        """Apply operational transformation to resolve conflicts."""
        conflict_service = ConflictResolutionService()
        return conflict_service.apply_operational_transformation(change_event)
    
    async def send_session_state(self):
        """Send current session state to newly connected participant."""
        session_data = await self.get_session_state()
        await self.send(text_data=json.dumps({
            'type': 'session_state',
            'session_data': session_data
        }))
    
    @database_sync_to_async
    def get_session_state(self):
        """Get current collaboration session state."""
        collaboration_service = CollaborationService()
        return collaboration_service.get_session_state(self.session)
    
    @database_sync_to_async
    def check_edit_permission(self, element_id: str) -> bool:
        """Check if user can edit specified element."""
        return DiagramLock.objects.filter(
            diagram=self.session.diagram,
            element_id=element_id,
            is_active=True
        ).exclude(user=self.user).count() == 0
    
    @database_sync_to_async
    def acquire_element_lock(self, element_id: str, lock_type: str, duration: int):
        """Acquire lock on diagram element."""
        return DiagramLock.acquire_lock(
            session=self.session,
            diagram=self.session.diagram,
            user=self.user,
            element_id=element_id,
            lock_type=lock_type,
            duration_minutes=duration
        )
    
    @database_sync_to_async
    def release_element_lock(self, element_id: str) -> bool:
        """Release lock on diagram element."""
        try:
            lock = DiagramLock.objects.get(
                diagram=self.session.diagram,
                element_id=element_id,
                user=self.user,
                is_active=True
            )
            lock.release_lock()
            return True
        except DiagramLock.DoesNotExist:
            return False
