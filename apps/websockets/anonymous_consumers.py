"""
Anonymous WebSocket consumers for UML Diagram collaboration.

Provides real-time collaboration without authentication:
- Session-based identification
- Auto-generated nicknames
- No user authentication required
- Simplified access control
"""

import json
import uuid
import random
import logging
import traceback
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.uml_diagrams.models import UMLDiagram


# Configure logger for WebSocket communication
logger = logging.getLogger('django')


class AnonymousUMLDiagramConsumer(AsyncWebsocketConsumer):
    """
    Anonymous WebSocket consumer for real-time UML diagram collaboration.
    
    Features:
    - Session-based user tracking
    - Auto-generated nicknames
    - Real-time diagram updates
    - No authentication required
    """
    
    async def connect(self):
        """Handle WebSocket connection with extensive diagnostic logging."""
        logger.info("🔗 WebSocket connection attempt started")
        
        try:
            # 1. Inspect scope and extract parameters - Log everything
            logger.info(f"🔍 Scope keys: {list(self.scope.keys())}")
            logger.info(f"🔍 URL route: {self.scope.get('url_route', 'Not found')}")
            logger.info(f"🔍 Path: {self.scope.get('path', 'Not found')}")
            
            # 2. Extract diagram_id from URL route
            try:
                self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
                logger.info(f"📋 Diagram ID extracted: {self.diagram_id}")
            except KeyError as e:
                logger.error(f"❌ Failed to extract diagram_id: {e}")
                logger.error(f"❌ URL route structure: {self.scope.get('url_route')}")
                raise
                
            self.diagram_group_name = f'diagram_{self.diagram_id}'
            logger.info(f"📌 Group name set: {self.diagram_group_name}")
            
            # 3. Generate session info
            self.session_id = str(uuid.uuid4())
            self.nickname = f"Guest_{random.randint(1000, 9999)}"
            logger.info(f"👤 Session generated: {self.session_id}, nickname: {self.nickname}")
            
            # 4. CRITICALLY IMPORTANT: Accept connection FIRST before any database operations
            logger.info("⏳ Accepting WebSocket connection...")
            await self.accept()
            logger.info("✅ WebSocket connection ACCEPTED")
            
            # 5. Now handle diagram setup in a separate method
            await self.handle_diagram_setup()
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            logger.error(f"❌ Exception type: {type(e).__name__}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            # Try to send error if connection was accepted
            try:
                if hasattr(self, 'accepted') and self.accepted:
                    await self.send_error(
                        message=f"Connection setup error: {str(e)}",
                        error_code="CONN_SETUP_ERROR",
                        details={"exception_type": type(e).__name__}
                    )
            except Exception as send_error:
                logger.error(f"❌ Failed to send error message: {send_error}")
                
            # Try to close connection
            try:
                await self.close(code=4000)
                logger.info("🚫 Connection closed after error")
            except Exception as close_error:
                logger.error(f"❌ Failed to close connection: {close_error}")
                
    async def handle_diagram_setup(self):
        """Handle diagram setup after connection is accepted."""
        logger.info("🔄 Starting diagram setup...")
        
        try:
            # Get or create diagram
            logger.info(f"📊 Getting diagram with ID: {self.diagram_id}")
            diagram = await self.get_diagram()
            
            if not diagram:
                logger.error(f"❌ Failed to create or access diagram with ID: {self.diagram_id}")
                await self.send_error('Failed to create or access diagram')
                await self.close(code=4000)
                return
            
            # Log successful retrieval/creation
            logger.info(f"✅ Diagram retrieved/created successfully: {self.diagram_id}")
            if hasattr(diagram, '_was_created') and diagram._was_created:
                logger.info(f"🆕 New diagram created with ID: {self.diagram_id}")
            
            # Update group name if diagram_id changed during creation
            self.diagram_group_name = f'diagram_{self.diagram_id}'
            logger.info(f"📌 Using group name: {self.diagram_group_name}")
            
            # Join diagram group
            logger.info(f"👥 Joining channel group: {self.diagram_group_name}")
            await self.channel_layer.group_add(
                self.diagram_group_name,
                self.channel_name
            )
            logger.info("✅ Joined channel group successfully")
            
            # Add session to diagram's active sessions
            logger.info(f"👤 Adding session {self.session_id} to active sessions")
            await self.add_active_session(diagram)
            
            # Get current user count
            user_count = await self.get_room_user_count()
            
            # Notify group of new user
            logger.info(f"📣 Broadcasting user joined notification (users: {user_count})")
            await self.channel_layer.group_send(
                self.diagram_group_name,
                {
                    'type': 'user_joined',
                    'session_id': self.session_id,
                    'nickname': self.nickname,
                    'timestamp': datetime.now().isoformat(),
                    'user_count': user_count
                }
            )
            
            # Send current diagram state
            logger.info("📤 Sending current diagram state to client")
            await self.send(text_data=json.dumps({
                'type': 'diagram_state',
                'content': diagram.content,
                'layout_config': diagram.layout_config,
                'session_id': self.session_id,
                'nickname': self.nickname,
                'active_sessions': diagram.active_sessions,
                'diagram_id': self.diagram_id,  # Send the actual UUID being used
                'timestamp': datetime.now().isoformat()
            }))
            logger.info("✅ Diagram state sent successfully")
            
        except Exception as e:
            logger.error(f"❌ Diagram setup failed: {str(e)}")
            logger.error(f"❌ Exception type: {type(e).__name__}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            try:
                await self.send_error(
                    message=f"Diagram setup error: {str(e)}",
                    error_code="DIAGRAM_SETUP_ERROR",
                    details={"exception_type": type(e).__name__}
                )
                await self.close(code=4000)
            except Exception as inner_e:
                logger.error(f"❌ Failed to send error and close: {inner_e}")
                # Try harder to close the connection
                try:
                    await self.close()
                except:
                    pass
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection with improved error handling and user count."""
        try:
            logger.info(f"🔒 WebSocket disconnect for {self.session_id} (code: {close_code})")
            
            # Remove session from diagram
            try:
                diagram = await self.get_diagram()
                if diagram:
                    logger.info(f"👤 Removing session {self.session_id} from active sessions")
                    await self.remove_active_session(diagram)
                    
                    # Get updated user count after removing this session
                    user_count = await self.get_room_user_count()
                    logger.info(f"👥 Active users remaining: {user_count}")
                    
                    # Notify group of user leaving
                    logger.info(f"📣 Broadcasting user left notification")
                    await self.channel_layer.group_send(
                        self.diagram_group_name,
                        {
                            'type': 'user_left',
                            'session_id': self.session_id,
                            'nickname': self.nickname,
                            'timestamp': datetime.now().isoformat(),
                            'user_count': user_count,
                            'reason': f"Disconnected (code: {close_code})"
                        }
                    )
            except Exception as diagram_error:
                logger.error(f"❌ Error removing session: {str(diagram_error)}")
            
            # Leave diagram group
            try:
                logger.info(f"🕺 Leaving channel group: {self.diagram_group_name}")
                await self.channel_layer.group_discard(
                    self.diagram_group_name,
                    self.channel_name
                )
                logger.info("✅ Left channel group successfully")
            except Exception as group_error:
                logger.error(f"❌ Error leaving group: {str(group_error)}")
                
        except Exception as e:
            logger.error(f"❌ Unhandled error in disconnect: {str(e)}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket with comprehensive broadcasting."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Enhanced logging for all received messages
            logger.info(f"📨 Received '{message_type}' from {self.session_id} in {self.diagram_group_name}")
            
            # Add sender metadata to avoid echoing back
            data['sender_channel'] = self.channel_name
            data['sender_session'] = self.session_id
            data['sender_nickname'] = self.nickname
            data['timestamp'] = datetime.now().isoformat()
            
            if message_type == 'diagram_update':
                await self.handle_diagram_update(data)
            elif message_type == 'cursor_position':
                await self.handle_cursor_position(data)
            elif message_type == 'element_select':
                await self.handle_element_select(data)
            elif message_type == 'set_nickname':
                await self.handle_set_nickname(data)
            elif message_type == 'ping':
                # Quick response for latency testing
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat(),
                    'session_id': self.session_id
                }))
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type} from {self.session_id}")
                await self.send_error('Unknown message type')
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON from {self.session_id}: {str(e)}")
            await self.send_error(f'Invalid JSON: {str(e)}')
        except Exception as e:
            logger.error(f"❌ Error processing message: {str(e)}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            await self.send_error(f'Server error: {str(e)}')
    
    async def handle_diagram_update(self, data):
        """Handle diagram update from client and broadcast to all connected users."""
        try:
            logger.info(f"📝 Processing diagram update from {self.session_id}")
            
            diagram = await self.get_diagram()
            if not diagram:
                logger.error(f"❌ Diagram not found for update: {self.diagram_id}")
                await self.send_error('Diagram not found')
                return
            
            # Extract update data
            update_data = data.get('update_data', {})
            updated_fields = []
            
            # Update diagram content if provided
            if 'content' in update_data:
                logger.info(f"💾 Saving content update from {self.session_id}")
                await self.update_diagram_content(diagram, update_data['content'])
                updated_fields.append('content')
                
            # Update layout config if provided
            if 'layout_config' in update_data:
                logger.info(f"💾 Saving layout update from {self.session_id}")
                await self.update_diagram_layout(diagram, update_data['layout_config'])
                updated_fields.append('layout_config')
            
            if not updated_fields:
                logger.warning(f"⚠️ No valid update data provided by {self.session_id}")
                await self.send_error('No valid update data provided')
                return
            
            # Broadcast to all clients including confirmation data
            broadcast_data = {
                'type': 'diagram_update_broadcast',
                'update_data': update_data,
                'session_id': self.session_id,
                'nickname': self.nickname,
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name,
                'updated_fields': updated_fields,
                'diagram_id': self.diagram_id
            }
            
            logger.info(f"📣 Broadcasting update to group: {self.diagram_group_name}")
            await self.channel_layer.group_send(
                self.diagram_group_name,
                broadcast_data
            )
            
            # Send acknowledgment to sender
            await self.send(text_data=json.dumps({
                'type': 'update_ack',
                'updated_fields': updated_fields,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }))
            
        except Exception as e:
            logger.error(f"❌ Error in diagram update: {str(e)}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            await self.send_error(f'Failed to update diagram: {str(e)}')
    
    async def handle_cursor_position(self, data):
        """Handle cursor position updates with improved error handling."""
        try:
            position = data.get('position', {})
            if not position:
                logger.warning(f"⚠️ Empty cursor position from {self.session_id}")
                return
                
            logger.debug(f"💠 Broadcasting cursor position from {self.session_id}")
            
            # Broadcast cursor position to all users except sender
            await self.channel_layer.group_send(
                self.diagram_group_name,
                {
                    'type': 'cursor_position_broadcast',
                    'position': position,
                    'session_id': self.session_id,
                    'nickname': self.nickname,
                    'timestamp': datetime.now().isoformat(),
                    'sender_channel': self.channel_name
                }
            )
        except Exception as e:
            logger.error(f"❌ Error in cursor position: {str(e)}")
            # Don't send error to client for cursor updates (non-critical)
    
    async def handle_element_select(self, data):
        """Handle element selection updates with improved error handling."""
        try:
            element_id = data.get('element_id')
            selected = data.get('selected', True)
            
            if not element_id:
                logger.warning(f"⚠️ Empty element selection from {self.session_id}")
                return
                
            logger.debug(f"👆 Broadcasting element selection from {self.session_id}: {element_id} ({selected})")
            
            # Broadcast selection to all users except sender
            await self.channel_layer.group_send(
                self.diagram_group_name,
                {
                    'type': 'element_select_broadcast',
                    'element_id': element_id,
                    'selected': selected,
                    'session_id': self.session_id,
                    'nickname': self.nickname,
                    'timestamp': datetime.now().isoformat(),
                    'sender_channel': self.channel_name
                }
            )
        except Exception as e:
            logger.error(f"❌ Error in element selection: {str(e)}")
            # Don't send error to client for selection updates (non-critical)
    
    async def handle_set_nickname(self, data):
        """Handle nickname change."""
        new_nickname = data.get('nickname', '').strip()
        if new_nickname and len(new_nickname) <= 20:
            old_nickname = self.nickname
            self.nickname = new_nickname
            
            # Update in diagram's active sessions
            diagram = await self.get_diagram()
            if diagram:
                await self.update_active_session_nickname(diagram)
            
            # Notify group of nickname change
            await self.channel_layer.group_send(
                self.diagram_group_name,
                {
                    'type': 'nickname_changed',
                    'session_id': self.session_id,
                    'old_nickname': old_nickname,
                    'new_nickname': self.nickname,
                    'timestamp': datetime.now().isoformat()
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
        """Broadcast diagram updates with enhanced metadata."""
        try:
            # Don't send to the sender
            if event.get('sender_channel') != self.channel_name:
                logger.debug(f"📹 Sending diagram update from {event.get('session_id')} to {self.session_id}")
                
                # Send a complete update message with all metadata
                await self.send(text_data=json.dumps({
                    'type': 'diagram_update',
                    'update_data': event['update_data'],
                    'session_id': event['session_id'],
                    'nickname': event['nickname'],
                    'timestamp': event['timestamp'],
                    'updated_fields': event.get('updated_fields', []),
                    'diagram_id': event.get('diagram_id', self.diagram_id)
                }))
        except Exception as e:
            logger.error(f"❌ Error in diagram_update_broadcast: {str(e)}")
            # Don't propagate errors back to avoid feedback loops
    
    async def cursor_position_broadcast(self, event):
        """Broadcast cursor position updates with error handling."""
        try:
            # Only broadcast to other clients, not the sender
            if event.get('sender_channel') != self.channel_name:
                logger.debug(f"📹 Sending cursor position from {event.get('session_id')} to {self.session_id}")
                
                await self.send(text_data=json.dumps({
                    'type': 'cursor_position',
                    'position': event['position'],
                    'session_id': event['session_id'],
                    'nickname': event['nickname'],
                    'timestamp': event['timestamp']
                }))
        except Exception as e:
            logger.error(f"❌ Error in cursor_position_broadcast: {str(e)}")
            # Don't propagate errors back to avoid feedback loops
    
    async def element_select_broadcast(self, event):
        """Broadcast element selection updates with error handling."""
        try:
            # Only broadcast to other clients, not the sender
            if event.get('sender_channel') != self.channel_name:
                logger.debug(f"📹 Sending element selection from {event.get('session_id')} to {self.session_id}")
                
                await self.send(text_data=json.dumps({
                    'type': 'element_select',
                    'element_id': event['element_id'],
                    'selected': event['selected'],
                    'session_id': event['session_id'],
                    'nickname': event['nickname'],
                    'timestamp': event['timestamp']
                }))
        except Exception as e:
            logger.error(f"❌ Error in element_select_broadcast: {str(e)}")
            # Don't propagate errors back to avoid feedback loops
    
    async def nickname_changed(self, event):
        """Send nickname change notification."""
        try:
            await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"❌ Error in nickname_changed: {str(e)}")
            
    @database_sync_to_async
    def get_room_user_count(self):
        """Get count of users connected to the current diagram."""
        try:
            diagram = UMLDiagram.objects.get(id=self.diagram_id)
            if isinstance(diagram.active_sessions, list):
                return len(diagram.active_sessions)
            return 0
        except Exception as e:
            logger.error(f"❌ Error getting user count: {str(e)}")
            return 0
    
    # Helper methods
    @database_sync_to_async
    def get_diagram(self):
        """Get diagram from database or create if not exists."""
        from django.core.exceptions import ValidationError
        import uuid
        
        try:
            # Try to get existing diagram
            return UMLDiagram.objects.get(id=self.diagram_id)
        except UMLDiagram.DoesNotExist:
            # AUTO-CREATE if diagram doesn't exist
            logger.info(f"Auto-creating diagram with ID: {self.diagram_id}")
            try:
                # Validate UUID format before creating
                uuid.UUID(self.diagram_id)
                diagram = UMLDiagram.objects.create(
                    id=self.diagram_id,
                    title=f"Anonymous Diagram {str(self.diagram_id)[:8]}",
                    diagram_type='CLASS',
                    content='@startuml\n@enduml',
                    layout_config={},
                    session_id=self.session_id,
                    active_sessions=[]
                )
                # Mark as newly created for logging
                diagram._was_created = True
                return diagram
            except (ValueError, ValidationError):
                # If invalid UUID, create new one
                new_id = str(uuid.uuid4())
                logger.warning(f"Invalid UUID: {self.diagram_id}, creating new UUID: {new_id}")
                
                # Update connection to use the new valid UUID
                self.diagram_id = new_id
                self.diagram_group_name = f'diagram_{new_id}'
                
                diagram = UMLDiagram.objects.create(
                    id=new_id,
                    title=f"Anonymous Diagram {new_id[:8]}",
                    diagram_type='CLASS',
                    content='@startuml\n@enduml',
                    layout_config={},
                    session_id=self.session_id,
                    active_sessions=[]
                )
                # Mark as newly created with new UUID for logging
                diagram._was_created = True
                return diagram
        except Exception as e:
            # Log any other exceptions but don't crash
            logger.error(f"Error in get_diagram: {str(e)}")
            return None
    
    @database_sync_to_async
    def update_diagram_content(self, diagram, new_content):
        """Update diagram content in database."""
        diagram.content = new_content
        diagram.session_id = self.session_id  # Track last editor
        diagram.save()
    
    @database_sync_to_async
    def update_diagram_layout(self, diagram, new_layout):
        """Update diagram layout in database."""
        diagram.layout_config = new_layout
        diagram.session_id = self.session_id  # Track last editor
        diagram.save()
    
    @database_sync_to_async
    def add_active_session(self, diagram):
        """Add session to diagram's active sessions."""
        diagram.add_active_session(self.session_id, self.nickname)
    
    @database_sync_to_async
    def remove_active_session(self, diagram):
        """Remove session from diagram's active sessions."""
        diagram.remove_active_session(self.session_id)
    
    @database_sync_to_async
    def update_active_session_nickname(self, diagram):
        """Update nickname in diagram's active sessions."""
        if not isinstance(diagram.active_sessions, list):
            diagram.active_sessions = []
        
        for session in diagram.active_sessions:
            if session.get('session_id') == self.session_id:
                session['nickname'] = self.nickname
                break
        
        diagram.save(update_fields=['active_sessions'])
    
    async def send_error(self, message, error_code=None, details=None):
        """Send enhanced error message to client with debugging info."""
        error_data = {
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'diagram_id': getattr(self, 'diagram_id', 'unknown'),
            'session_id': getattr(self, 'session_id', 'unknown')
        }
        
        if error_code:
            error_data['error_code'] = error_code
        
        if details:
            error_data['details'] = details
        
        await self.send(text_data=json.dumps(error_data))


class AnonymousDiagramChatConsumer(AsyncWebsocketConsumer):
    """
    Anonymous WebSocket consumer for diagram chat functionality.
    
    Features:
    - Session-based chat participation
    - Auto-generated nicknames
    - Temporary messages (not persisted)
    - No authentication required
    """
    
    async def connect(self):
        """Handle WebSocket connection for chat with extensive diagnostic logging."""
        logger.info("🔗 CHAT: WebSocket connection attempt started")
        
        try:
            # 1. Inspect scope and extract parameters - Log everything
            logger.info(f"🔍 CHAT: Scope keys: {list(self.scope.keys())}")
            logger.info(f"🔍 CHAT: URL route: {self.scope.get('url_route', 'Not found')}")
            logger.info(f"🔍 CHAT: Path: {self.scope.get('path', 'Not found')}")
            
            # 2. Extract diagram_id from URL route
            try:
                self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
                logger.info(f"📋 CHAT: Diagram ID extracted: {self.diagram_id}")
            except KeyError as e:
                logger.error(f"❌ CHAT: Failed to extract diagram_id: {e}")
                logger.error(f"❌ CHAT: URL route structure: {self.scope.get('url_route')}")
                raise
                
            self.chat_group_name = f'chat_{self.diagram_id}'
            logger.info(f"📌 CHAT: Group name set: {self.chat_group_name}")
            
            # 3. Generate session info
            self.session_id = str(uuid.uuid4())
            self.nickname = f"Guest_{random.randint(1000, 9999)}"
            logger.info(f"👤 CHAT: Session generated: {self.session_id}, nickname: {self.nickname}")
            
            # 4. CRITICALLY IMPORTANT: Accept connection FIRST before any database operations
            logger.info("⏳ CHAT: Accepting WebSocket connection...")
            await self.accept()
            logger.info("✅ CHAT: WebSocket connection ACCEPTED")
            
            # 5. Now handle diagram setup in a separate method
            await self.handle_chat_setup()
            
        except Exception as e:
            logger.error(f"❌ CHAT: Connection failed: {str(e)}")
            logger.error(f"❌ CHAT: Exception type: {type(e).__name__}")
            logger.error(f"❌ CHAT: Traceback: {traceback.format_exc()}")
            
            # Try to send error if connection was accepted
            try:
                if hasattr(self, 'accepted') and self.accepted:
                    await self.send_error(
                        message=f"Chat connection error: {str(e)}",
                        error_code="CHAT_CONN_ERROR",
                        details={"exception_type": type(e).__name__}
                    )
            except Exception as send_error:
                logger.error(f"❌ CHAT: Failed to send error message: {send_error}")
                
            # Try to close connection
            try:
                await self.close(code=4000)
                logger.info("🚫 CHAT: Connection closed after error")
            except Exception as close_error:
                logger.error(f"❌ CHAT: Failed to close connection: {close_error}")
                
    async def handle_chat_setup(self):
        """Handle chat setup after connection is accepted."""
        logger.info("🔄 CHAT: Starting chat setup...")
        
        try:
            # Get or create diagram
            logger.info(f"📊 CHAT: Getting diagram with ID: {self.diagram_id}")
            diagram = await self.get_diagram()
            
            if not diagram:
                logger.error(f"❌ CHAT: Failed to create or access diagram with ID: {self.diagram_id}")
                await self.send_error('Failed to create or access diagram for chat')
                await self.close(code=4000)
                return
            
            # Log successful retrieval/creation
            logger.info(f"✅ CHAT: Diagram retrieved successfully: {self.diagram_id}")
            if hasattr(diagram, '_was_created') and diagram._was_created:
                logger.info(f"🆕 CHAT: New diagram created with ID: {self.diagram_id}")
            
            # Update group name if diagram_id changed during creation
            self.chat_group_name = f'chat_{self.diagram_id}'
            logger.info(f"📌 CHAT: Using group name: {self.chat_group_name}")
            
            # Join chat group
            logger.info(f"👥 CHAT: Joining channel group: {self.chat_group_name}")
            await self.channel_layer.group_add(
                self.chat_group_name,
                self.channel_name
            )
            logger.info("✅ CHAT: Joined channel group successfully")
            
            # Notify chat of new user
            logger.info("📣 CHAT: Broadcasting user joined notification")
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'user_joined_chat',
                    'session_id': self.session_id,
                    'nickname': self.nickname,
                    'timestamp': datetime.now().isoformat()
                }
            )
            logger.info("✅ CHAT: User joined notification sent")
            
        except Exception as e:
            logger.error(f"❌ CHAT: Setup failed: {str(e)}")
            logger.error(f"❌ CHAT: Exception type: {type(e).__name__}")
            logger.error(f"❌ CHAT: Traceback: {traceback.format_exc()}")
            
            try:
                await self.send_error(
                    message=f"Chat setup error: {str(e)}",
                    error_code="CHAT_SETUP_ERROR",
                    details={
                        "exception_type": type(e).__name__,
                        "diagram_id": self.diagram_id,
                        "chat_group": self.chat_group_name
                    }
                )
                await self.close(code=4000)
            except Exception as inner_e:
                logger.error(f"❌ CHAT: Failed to send error and close: {inner_e}")
                # Try harder to close the connection
                try:
                    await self.close()
                except Exception:
                    pass
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'user_left_chat',
                'session_id': self.session_id,
                'nickname': self.nickname,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle WebSocket message with broadcasting to all connected users."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.info(f"📨 Received message type: {message_type} in room: {self.diagram_group_name}")
            
            # Track the original sender to avoid echo
            data['sender_channel'] = self.channel_name
            data['sender_session'] = self.session_id
            data['timestamp'] = datetime.now().isoformat()
            
            if message_type == 'update_content':
                await self.handle_content_update(data)
            elif message_type == 'update_layout':
                await self.handle_layout_update(data)
            elif message_type == 'set_nickname':
                await self.handle_set_nickname(data)
            elif message_type == 'cursor_position':
                # Just broadcast cursor position without saving
                await self.broadcast_message(data)
            elif message_type == 'selection_change':
                # Just broadcast selection without saving
                await self.broadcast_message(data)
            elif message_type == 'ping':
                # Respond directly to pings without broadcasting
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            else:
                # For unknown types, broadcast anyway but log it
                logger.warning(f"⚠️ Unknown message type: {message_type} from {self.session_id}")
                await self.broadcast_message(data)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON from {self.session_id}: {str(e)}")
            await self.send_error('Invalid JSON: ' + str(e))
        except Exception as e:
            logger.error(f"❌ Error processing message: {str(e)}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            await self.send_error(f'Error processing message: {str(e)}')
            
    async def broadcast_message(self, data):
        """Broadcast message to all users in the diagram group."""
        message_type = data.get('type', 'unknown_type')
        
        logger.info(f"📣 Broadcasting {message_type} to {self.diagram_group_name}")
        
        # Send to the channel group for all users
        await self.channel_layer.group_send(
            self.diagram_group_name,
            {
                'type': 'relay_message',  # This calls relay_message method
                'message': data
            }
        )
        
    async def relay_message(self, event):
        """Relay received message to connected client."""
        try:
            message = event['message']
            sender_channel = message.get('sender_channel')
            
            # Don't echo back to sender
            if sender_channel != self.channel_name:
                logger.debug(f"🔄 Relaying {message.get('type')} to client {self.session_id}")
                await self.send(text_data=json.dumps(message))
        except Exception as e:
            logger.error(f"❌ Error in relay_message: {str(e)}")
            try:
                await self.send_error(f'Server error: {str(e)}')
            except:
                pass
    
    async def handle_chat_message(self, data):
        """Handle chat message from client."""
        message = data.get('message', '').strip()
        if not message or len(message) > 500:  # Max message length
            return
        
        # Broadcast message to all chat participants
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'chat_message_broadcast',
                'message': message,
                'session_id': self.session_id,
                'nickname': self.nickname,
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
                'session_id': self.session_id,
                'nickname': self.nickname,
                'timestamp': datetime.now().isoformat(),
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_set_nickname(self, data):
        """Handle nickname change in chat."""
        new_nickname = data.get('nickname', '').strip()
        if new_nickname and len(new_nickname) <= 20:
            old_nickname = self.nickname
            self.nickname = new_nickname
            
            # Notify chat of nickname change
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'nickname_changed_chat',
                    'session_id': self.session_id,
                    'old_nickname': old_nickname,
                    'new_nickname': self.nickname,
                    'timestamp': datetime.now().isoformat()
                }
            )
    
    # Group message handlers
    async def user_joined_chat(self, event):
        """Send user joined chat notification."""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'session_id': event['session_id'],
            'nickname': event['nickname'],
            'timestamp': event['timestamp']
        }))
    
    async def user_left_chat(self, event):
        """Send user left chat notification."""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'session_id': event['session_id'],
            'nickname': event['nickname'],
            'timestamp': event['timestamp']
        }))
    
    async def chat_message_broadcast(self, event):
        """Broadcast chat message."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'session_id': event['session_id'],
            'nickname': event['nickname'],
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
                'session_id': event['session_id'],
                'nickname': event['nickname'],
                'timestamp': event['timestamp']
            }))
    
    async def nickname_changed_chat(self, event):
        """Send nickname change notification."""
        await self.send(text_data=json.dumps({
            'type': 'nickname_changed',
            'session_id': event['session_id'],
            'old_nickname': event['old_nickname'],
            'new_nickname': event['new_nickname'],
            'timestamp': event['timestamp']
        }))
    
    # Helper methods
    @database_sync_to_async
    def get_diagram(self):
        """Get diagram from database or create if not exists for chat consumer."""
        from django.core.exceptions import ValidationError
        import uuid
        
        try:
            # Try to get existing diagram
            return UMLDiagram.objects.get(id=self.diagram_id)
        except UMLDiagram.DoesNotExist:
            # AUTO-CREATE if diagram doesn't exist
            logger.info(f"Chat consumer: Auto-creating diagram with ID: {self.diagram_id}")
            try:
                # Validate UUID format before creating
                uuid.UUID(self.diagram_id)
                diagram = UMLDiagram.objects.create(
                    id=self.diagram_id,
                    title=f"Chat Diagram {str(self.diagram_id)[:8]}",
                    diagram_type='CLASS',
                    content='@startuml\n@enduml',
                    layout_config={},
                    session_id=self.session_id,
                    active_sessions=[]
                )
                # Mark as newly created for logging
                diagram._was_created = True
                return diagram
            except (ValueError, ValidationError):
                # If invalid UUID, create new one
                new_id = str(uuid.uuid4())
                logger.warning(f"Chat consumer: Invalid UUID: {self.diagram_id}, creating new UUID: {new_id}")
                
                # Update connection to use the new valid UUID
                self.diagram_id = new_id
                self.chat_group_name = f'chat_{new_id}'
                
                diagram = UMLDiagram.objects.create(
                    id=new_id,
                    title=f"Chat Diagram {new_id[:8]}",
                    diagram_type='CLASS',
                    content='@startuml\n@enduml',
                    layout_config={},
                    session_id=self.session_id,
                    active_sessions=[]
                )
                # Mark as newly created with new UUID for logging
                diagram._was_created = True
                return diagram
        except Exception as e:
            # Log any other exceptions but don't crash
            logger.error(f"Chat get_diagram error: {str(e)}")
            return None
    
    async def send_error(self, message, error_code=None, details=None):
        """Send enhanced error message to client with debugging info."""
        error_data = {
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'diagram_id': getattr(self, 'diagram_id', 'unknown'),
            'session_id': getattr(self, 'session_id', 'unknown'),
            'chat_mode': True
        }
        
        if error_code:
            error_data['error_code'] = error_code
        
        if details:
            error_data['details'] = details
        
        await self.send(text_data=json.dumps(error_data))
