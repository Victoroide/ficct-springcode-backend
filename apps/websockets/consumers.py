"""
WebSocket consumers for UML Diagram collaboration.

Provides real-time collaboration features including:
- Diagram editing synchronization
- Chat functionality
- User presence tracking
- Public diagram access
"""

import json
import uuid
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from apps.uml_diagrams.models import UMLDiagram
from apps.audit.services.audit_service import AuditService


class UMLDiagramConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time UML diagram collaboration.
    
    Features:
    - Real-time diagram updates
    - User presence tracking
    - Change broadcasting
    - Public diagram support
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
        self.diagram_group_name = f'diagram_{self.diagram_id}'
        self.user = self.scope['user']
        
        # Validate diagram access
        diagram = await self.get_diagram()
        if not diagram:
            await self.close(code=4004)  # Not found
            return
        
        # Check permissions
        if not await self.has_diagram_access(diagram):
            await self.close(code=4003)  # Forbidden
            return
        
        # Join diagram group
        await self.channel_layer.group_add(
            self.diagram_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify group of new user
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'user_joined',
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Send current diagram state
        await self.send(text_data=json.dumps({
            'type': 'diagram_state',
            'diagram_data': diagram.diagram_data,
            'layout_config': diagram.layout_config,
            'version': diagram.version_number,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Notify group of user leaving
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'user_left',
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Leave diagram group
        await self.channel_layer.group_discard(
            self.diagram_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'diagram_update':
                await self.handle_diagram_update(data)
            elif message_type == 'cursor_position':
                await self.handle_cursor_position(data)
            elif message_type == 'element_select':
                await self.handle_element_select(data)
            else:
                await self.send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            await self.send_error(f'Server error: {str(e)}')
    
    async def handle_diagram_update(self, data):
        """Handle diagram update from client."""
        diagram = await self.get_diagram()
        if not diagram:
            await self.send_error('Diagram not found')
            return
        
        # Update diagram data
        update_data = data.get('update_data', {})
        if 'diagram_data' in update_data:
            await self.update_diagram_data(diagram, update_data['diagram_data'])
        
        # Broadcast to all clients except sender
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'diagram_update_broadcast',
                'update_data': update_data,
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_cursor_position(self, data):
        """Handle cursor position updates."""
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'cursor_position_broadcast',
                'position': data.get('position', {}),
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_element_select(self, data):
        """Handle element selection updates."""
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'element_select_broadcast',
                'element_id': data.get('element_id'),
                'selected': data.get('selected', True),
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )
    
    # Group message handlers
    async def user_joined(self, event):
        """Send user joined notification."""
        await self.send(text_data=json.dumps(event))
    
    async def user_left(self, event):
        """Send user left notification."""
        await self.send(text_data=json.dumps(event))
    
    async def diagram_update_broadcast(self, event):
        """Broadcast diagram updates."""
        # Don't send to the sender
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'diagram_update',
                'update_data': event['update_data'],
                'user_id': event['user_id'],
                'timestamp': event['timestamp']
            }))
    
    async def cursor_position_broadcast(self, event):
        """Broadcast cursor position updates."""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'cursor_position',
                'position': event['position'],
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'timestamp': event['timestamp']
            }))
    
    async def element_select_broadcast(self, event):
        """Broadcast element selection updates."""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'element_select',
                'element_id': event['element_id'],
                'selected': event['selected'],
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'timestamp': event['timestamp']
            }))
    
    # Helper methods
    @database_sync_to_async
    def get_diagram(self):
        """Get diagram from database."""
        try:
            return UMLDiagram.objects.get(id=self.diagram_id)
        except UMLDiagram.DoesNotExist:
            return None
    
    @database_sync_to_async
    def has_diagram_access(self, diagram):
        """Check if user has access to diagram."""
        if diagram.is_public:
            return True
        
        if isinstance(self.user, AnonymousUser):
            return False
        
        return (diagram.owner == self.user or 
                diagram.created_by == self.user or
                diagram.visibility in ['ORGANIZATION', 'PUBLIC'])
    
    @database_sync_to_async
    def update_diagram_data(self, diagram, new_data):
        """Update diagram data in database."""
        diagram.diagram_data = new_data
        diagram.version_number += 1
        diagram.last_modified_by = self.user if not isinstance(self.user, AnonymousUser) else None
        diagram.save()
        
        # Log the change
        if not isinstance(self.user, AnonymousUser):
            AuditService.log_user_action(
                user=self.user,
                action_type='DIAGRAM_UPDATE',
                resource_type='UMLDiagram',
                resource_id=diagram.id,
                details={'version': diagram.version_number}
            )
    
    async def send_error(self, message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))


class DiagramChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for diagram chat functionality.
    
    Features:
    - Real-time chat messages
    - User presence in chat
    - Temporary messages (not persisted)
    - Public diagram chat support
    """
    
    async def connect(self):
        """Handle WebSocket connection for chat."""
        self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
        self.chat_group_name = f'chat_{self.diagram_id}'
        self.user = self.scope['user']
        
        # Validate diagram access
        diagram = await self.get_diagram()
        if not diagram:
            await self.close(code=4004)
            return
        
        if not await self.has_diagram_access(diagram):
            await self.close(code=4003)
            return
        
        # Join chat group
        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify chat of new user
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'user_joined_chat',
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat()
            }
        )
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'user_left_chat',
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle chat messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing_indicator':
                await self.handle_typing_indicator(data)
            else:
                await self.send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            await self.send_error(f'Server error: {str(e)}')
    
    async def handle_chat_message(self, data):
        """Handle chat message from client."""
        message = data.get('message', '').strip()
        if not message:
            return
        
        # Broadcast message to all chat participants
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'chat_message_broadcast',
                'message': message,
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat(),
                'message_id': str(uuid.uuid4())
            }
        )
    
    async def handle_typing_indicator(self, data):
        """Handle typing indicator."""
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'typing_indicator_broadcast',
                'is_typing': data.get('is_typing', False),
                'user_id': str(self.user.id) if not isinstance(self.user, AnonymousUser) else 'anonymous',
                'user_name': getattr(self.user, 'full_name', 'Anonymous User'),
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )
    
    # Group message handlers
    async def user_joined_chat(self, event):
        """Send user joined chat notification."""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp']
        }))
    
    async def user_left_chat(self, event):
        """Send user left chat notification."""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp']
        }))
    
    async def chat_message_broadcast(self, event):
        """Broadcast chat message."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id']
        }))
    
    async def typing_indicator_broadcast(self, event):
        """Broadcast typing indicator."""
        # Don't send to sender
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'is_typing': event['is_typing'],
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'timestamp': event['timestamp']
            }))
    
    # Helper methods
    @database_sync_to_async
    def get_diagram(self):
        """Get diagram from database."""
        try:
            return UMLDiagram.objects.get(id=self.diagram_id)
        except UMLDiagram.DoesNotExist:
            return None
    
    @database_sync_to_async
    def has_diagram_access(self, diagram):
        """Check if user has access to diagram."""
        if diagram.is_public:
            return True
        
        if isinstance(self.user, AnonymousUser):
            return False
        
        return (diagram.owner == self.user or 
                diagram.created_by == self.user or
                diagram.visibility in ['ORGANIZATION', 'PUBLIC'])
    
    async def send_error(self, message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))
