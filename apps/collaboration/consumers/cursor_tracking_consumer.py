"""
WebSocket consumer for real-time cursor tracking in collaborative editing.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from ..models import UserCursor, CollaborationSession

User = get_user_model()
logger = logging.getLogger('collaboration')


class CursorTrackingConsumer(AsyncWebsocketConsumer):
    """
    Lightweight WebSocket consumer for real-time cursor position tracking.
    
    Optimized for high-frequency cursor updates with minimal latency.
    """
    
    async def connect(self):
        """Establish cursor tracking connection."""
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
        self.user = self.scope['user']
        self.room_group_name = f'cursors_{self.project_id}_{self.diagram_id}'
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        try:
            # Join cursor tracking group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Initialize cursor position
            await self.initialize_cursor()
            
            logger.info(f"Cursor tracking established for {self.user.corporate_email}")
            
        except Exception as e:
            logger.error(f"Failed to establish cursor tracking: {str(e)}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Clean up cursor tracking on disconnect."""
        if hasattr(self, 'room_group_name'):
            # Deactivate cursor
            await self.deactivate_cursor()
            
            # Leave group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Broadcast cursor removal
            await self.broadcast_cursor_removed()
    
    async def receive(self, text_data):
        """Handle cursor position updates."""
        try:
            data = json.loads(text_data)
            
            if data.get('type') == 'cursor_move':
                await self.handle_cursor_move(data)
            elif data.get('type') == 'viewport_update':
                await self.handle_viewport_update(data)
            elif data.get('type') == 'element_select':
                await self.handle_element_select(data)
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in cursor tracking")
        except Exception as e:
            logger.error(f"Error in cursor tracking: {str(e)}")
    
    async def handle_cursor_move(self, data):
        """Handle cursor position updates."""
        try:
            position_data = data.get('position', {})
            x = position_data.get('x', 0)
            y = position_data.get('y', 0)
            selected_element = data.get('selected_element')
            
            # Update cursor position in database
            await self.update_cursor_position(x, y, selected_element)
            
            # Broadcast to other participants
            await self.broadcast_cursor_move({
                'user_id': str(self.user.id),
                'user_name': self.user.full_name,
                'position_x': x,
                'position_y': y,
                'selected_element_id': selected_element,
                'timestamp': data.get('timestamp')
            })
            
        except Exception as e:
            logger.error(f"Error handling cursor move: {str(e)}")
    
    async def handle_viewport_update(self, data):
        """Handle viewport zoom/pan updates."""
        try:
            viewport = data.get('viewport', {})
            zoom = viewport.get('zoom', 1.0)
            center_x = viewport.get('center_x', 0)
            center_y = viewport.get('center_y', 0)
            
            await self.update_viewport(zoom, center_x, center_y)
            
        except Exception as e:
            logger.error(f"Error handling viewport update: {str(e)}")
    
    async def handle_element_select(self, data):
        """Handle element selection updates."""
        try:
            element_id = data.get('element_id')
            
            await self.update_selected_element(element_id)
            
            # Broadcast selection change
            await self.broadcast_element_select({
                'user_id': str(self.user.id),
                'user_name': self.user.full_name,
                'selected_element_id': element_id
            })
            
        except Exception as e:
            logger.error(f"Error handling element select: {str(e)}")
    
    # Group message handlers
    
    async def cursor_moved(self, event):
        """Handle cursor move broadcast from group."""
        cursor_data = event['cursor_data']
        
        # Don't echo own cursor movements
        if cursor_data.get('user_id') != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'cursor_move',
                'cursor_data': cursor_data
            }))
    
    async def element_selected(self, event):
        """Handle element selection broadcast."""
        selection_data = event['selection_data']
        
        if selection_data.get('user_id') != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'element_select',
                'selection_data': selection_data
            }))
    
    async def cursor_removed(self, event):
        """Handle cursor removal broadcast."""
        await self.send(text_data=json.dumps({
            'type': 'cursor_remove',
            'user_id': event['user_id']
        }))
    
    # Database operations
    
    @database_sync_to_async
    def initialize_cursor(self):
        """Initialize cursor position in database."""
        try:
            session = CollaborationSession.objects.filter(
                project_id=self.project_id,
                diagram_id=self.diagram_id,
                status='ACTIVE'
            ).first()
            
            if session:
                cursor, created = UserCursor.objects.get_or_create(
                    session=session,
                    user=self.user,
                    diagram=session.diagram,
                    defaults={
                        'is_active': True,
                        'cursor_color': self.get_user_cursor_color()
                    }
                )
                
                if not created:
                    cursor.is_active = True
                    cursor.save()
                
                return cursor
                
        except Exception as e:
            logger.error(f"Error initializing cursor: {str(e)}")
            return None
    
    @database_sync_to_async
    def update_cursor_position(self, x: float, y: float, selected_element: str = None):
        """Update cursor position in database."""
        try:
            UserCursor.objects.filter(
                user=self.user,
                is_active=True
            ).update(
                position_x=x,
                position_y=y,
                selected_element_id=selected_element or ''
            )
        except Exception as e:
            logger.error(f"Error updating cursor position: {str(e)}")
    
    @database_sync_to_async
    def update_viewport(self, zoom: float, center_x: float, center_y: float):
        """Update viewport information."""
        try:
            UserCursor.objects.filter(
                user=self.user,
                is_active=True
            ).update(
                viewport_zoom=zoom,
                viewport_center_x=center_x,
                viewport_center_y=center_y
            )
        except Exception as e:
            logger.error(f"Error updating viewport: {str(e)}")
    
    @database_sync_to_async
    def update_selected_element(self, element_id: str):
        """Update selected element."""
        try:
            UserCursor.objects.filter(
                user=self.user,
                is_active=True
            ).update(
                selected_element_id=element_id or ''
            )
        except Exception as e:
            logger.error(f"Error updating selected element: {str(e)}")
    
    @database_sync_to_async
    def deactivate_cursor(self):
        """Deactivate user cursor on disconnect."""
        try:
            UserCursor.objects.filter(
                user=self.user,
                is_active=True
            ).update(is_active=False)
        except Exception as e:
            logger.error(f"Error deactivating cursor: {str(e)}")
    
    # Broadcasting methods
    
    async def broadcast_cursor_move(self, cursor_data):
        """Broadcast cursor movement to group."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cursor_moved',
                'cursor_data': cursor_data
            }
        )
    
    async def broadcast_element_select(self, selection_data):
        """Broadcast element selection to group."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'element_selected',
                'selection_data': selection_data
            }
        )
    
    async def broadcast_cursor_removed(self):
        """Broadcast cursor removal to group."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cursor_removed',
                'user_id': str(self.user.id)
            }
        )
    
    def get_user_cursor_color(self) -> str:
        """Generate consistent cursor color for user."""
        colors = [
            '#3B82F6', '#EF4444', '#10B981', '#F59E0B',
            '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
        ]
        # Use user ID hash to consistently assign color
        color_index = hash(str(self.user.id)) % len(colors)
        return colors[color_index]
