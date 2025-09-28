import json
import uuid
import random
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.uml_diagrams.models import UMLDiagram

logger = logging.getLogger('django')

_active_connections = {}

class AnonymousUMLDiagramConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        logger.info(f"WebSocket connection attempt for: {self.scope.get('path')}")
        
        try:
            self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
            self.session_id = self.scope['url_route']['kwargs'].get('session_id', str(uuid.uuid4()))
            logger.info(f"Connecting - Diagram: {self.diagram_id}, Session: {self.session_id}")
            
            await self.accept()
            logger.info("WebSocket connection accepted!")
            
            if self.diagram_id not in _active_connections:
                _active_connections[self.diagram_id] = []
            _active_connections[self.diagram_id].append(self)
            
            try:
                await self.add_session_to_diagram()
                logger.info(f"Added to room {self.diagram_id}. Active connections: {len(_active_connections[self.diagram_id])}")
            except Exception as db_error:
                logger.warning(f"Database session tracking failed: {db_error} (connection still active)")
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            try:
                await self.close(code=4000)
            except:
                pass

    async def disconnect(self, close_code):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            logger.info(f"Disconnecting session {session_id} (code: {close_code})")
            
            if hasattr(self, 'diagram_id') and self.diagram_id in _active_connections:
                if self in _active_connections[self.diagram_id]:
                    _active_connections[self.diagram_id].remove(self)
                    logger.info(f"Removed from room {self.diagram_id}. Remaining: {len(_active_connections[self.diagram_id])}")
                
                if not _active_connections[self.diagram_id]:
                    _active_connections.pop(self.diagram_id, None)
                    logger.info(f"Cleaned up empty room {self.diagram_id}")
            
            try:
                await self.remove_session_from_diagram()
            except Exception as db_error:
                logger.warning(f"Database session cleanup failed: {db_error}")
                    
        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}")

    async def receive(self, text_data):
        try:
            logger.info(f"Received message from session {getattr(self, 'session_id', 'unknown')}")
            
            if hasattr(self, 'diagram_id') and self.diagram_id in _active_connections:
                forwarded_count = 0
                failed_peers = []
                
                for peer in _active_connections[self.diagram_id]:
                    if peer is not self:
                        try:
                            await peer.send(text_data=text_data)
                            forwarded_count += 1
                        except Exception as send_error:
                            logger.error(f"Failed to send to peer: {send_error}")
                            failed_peers.append(peer)
                
                for failed_peer in failed_peers:
                    try:
                        _active_connections[self.diagram_id].remove(failed_peer)
                    except ValueError:
                        pass
                
                logger.info(f"Forwarded to {forwarded_count} peers in room {self.diagram_id}")
                                
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
    
    @database_sync_to_async
    def add_session_to_diagram(self):
        try:
            diagram = UMLDiagram.objects.get(id=self.diagram_id)
            diagram.add_active_session(self.session_id, f"Guest_{random.randint(1000, 9999)}")
            return True
        except UMLDiagram.DoesNotExist:
            diagram = UMLDiagram.objects.create(
                id=self.diagram_id,
                title=f"Diagram {self.diagram_id[:8]}",
                content=json.dumps({"nodes": [], "edges": []}),
                session_id=self.session_id
            )
            diagram.add_active_session(self.session_id, f"Guest_{random.randint(1000, 9999)}")
            return True
        except Exception as e:
            logger.error(f"Database session add failed: {e}")
            return False
    
    @database_sync_to_async  
    def remove_session_from_diagram(self):
        try:
            diagram = UMLDiagram.objects.get(id=self.diagram_id)
            diagram.remove_active_session(self.session_id)
            return True
        except UMLDiagram.DoesNotExist:
            logger.warning(f"Diagram {self.diagram_id} not found during session cleanup")
            return False
        except Exception as e:
            logger.error(f"Database session remove failed: {e}")
            return False


class AnonymousDiagramChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"Chat WebSocket connection attempt for: {self.scope.get('path')}")
        
        try:
            self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
            logger.info(f"Chat Diagram ID: {self.diagram_id}")
            
            self.session_id = str(uuid.uuid4())
            self.nickname = f"Guest_{random.randint(1000, 9999)}"
            
            await self.accept()
            logger.info("Chat WebSocket connection accepted!")
            
            chat_room_id = f"chat_{self.diagram_id}"
            if chat_room_id not in _active_connections:
                _active_connections[chat_room_id] = []
            _active_connections[chat_room_id].append(self)
            
            logger.info(f"Added to chat room {chat_room_id}. Room size: {len(_active_connections[chat_room_id])}")
            
        except Exception as e:
            logger.error(f"Chat connection failed: {str(e)}")
            try:
                await self.close(code=4000)
            except:
                pass

    async def disconnect(self, close_code):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            logger.info(f"Chat WebSocket disconnect for {session_id} (code: {close_code})")
            
            chat_room_id = f"chat_{self.diagram_id}"
            if hasattr(self, 'diagram_id') and chat_room_id in _active_connections:
                if self in _active_connections[chat_room_id]:
                    _active_connections[chat_room_id].remove(self)
                    logger.info(f"Removed from chat room {chat_room_id}. Room size: {len(_active_connections[chat_room_id])}")
                
                if not _active_connections[chat_room_id]:
                    _active_connections.pop(chat_room_id, None)
                    logger.info(f"Removed empty chat room {chat_room_id}")
                    
        except Exception as e:
            logger.error(f"Error in chat disconnect: {str(e)}")

    async def receive(self, text_data):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            logger.info(f"Received chat message from {session_id}")
            
            chat_room_id = f"chat_{self.diagram_id}"
            if hasattr(self, 'diagram_id') and chat_room_id in _active_connections:
                forwarded_count = 0
                for peer in _active_connections[chat_room_id]:
                    if peer is not self:
                        try:
                            await peer.send(text_data=text_data)
                            forwarded_count += 1
                        except Exception as send_error:
                            logger.error(f"Failed to send chat to peer: {send_error}")
                            try:
                                _active_connections[chat_room_id].remove(peer)
                            except ValueError:
                                pass
                
                logger.info(f"Forwarded chat message to {forwarded_count} peers in room {chat_room_id}")
                                
        except Exception as e:
            logger.error(f"Error in chat receive: {str(e)}")
            try:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Chat server error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }))
            except:
                pass