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
        
        try:
            self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
            self.session_id = self.scope['url_route']['kwargs'].get('session_id', str(uuid.uuid4()))
            
            await self.accept()
            
            if self.diagram_id not in _active_connections:
                _active_connections[self.diagram_id] = []
            _active_connections[self.diagram_id].append(self)
            
            try:
                await self.add_session_to_diagram()
            except Exception as db_error:
                pass
            
        except Exception as e:
            try:
                await self.close(code=4000)
            except:
                pass

    async def disconnect(self, close_code):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            
            if hasattr(self, 'diagram_id') and self.diagram_id in _active_connections:
                if self in _active_connections[self.diagram_id]:
                    _active_connections[self.diagram_id].remove(self)
                
                if not _active_connections[self.diagram_id]:
                    _active_connections.pop(self.diagram_id, None)
            
            try:
                await self.remove_session_from_diagram()
            except Exception as db_error:
                pass
                    
        except Exception as e:
            pass

    async def receive(self, text_data):
        try:
            
            if hasattr(self, 'diagram_id') and self.diagram_id in _active_connections:
                forwarded_count = 0
                failed_peers = []
                
                for peer in _active_connections[self.diagram_id]:
                    if peer is not self:
                        try:
                            await peer.send(text_data=text_data)
                            forwarded_count += 1
                        except Exception as send_error:
                            failed_peers.append(peer)
                
                for failed_peer in failed_peers:
                    try:
                        _active_connections[self.diagram_id].remove(failed_peer)
                    except ValueError:
                        pass
                                
        except Exception as e:
            pass
    
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
            return False
    
    @database_sync_to_async  
    def remove_session_from_diagram(self):
        try:
            diagram = UMLDiagram.objects.get(id=self.diagram_id)
            diagram.remove_active_session(self.session_id)
            return True
        except UMLDiagram.DoesNotExist:
            return False
        except Exception as e:
            return False


class AnonymousDiagramChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        
        try:
            self.diagram_id = self.scope['url_route']['kwargs']['diagram_id']
            
            self.session_id = str(uuid.uuid4())
            self.nickname = f"Guest_{random.randint(1000, 9999)}"
            
            await self.accept()
            
            chat_room_id = f"chat_{self.diagram_id}"
            if chat_room_id not in _active_connections:
                _active_connections[chat_room_id] = []
            _active_connections[chat_room_id].append(self)
            
        except Exception as e:
            try:
                await self.close(code=4000)
            except:
                pass

    async def disconnect(self, close_code):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            
            chat_room_id = f"chat_{self.diagram_id}"
            if hasattr(self, 'diagram_id') and chat_room_id in _active_connections:
                if self in _active_connections[chat_room_id]:
                    _active_connections[chat_room_id].remove(self)
                
                if not _active_connections[chat_room_id]:
                    _active_connections.pop(chat_room_id, None)
                    
        except Exception as e:
            pass

    async def receive(self, text_data):
        try:
            session_id = getattr(self, 'session_id', 'unknown')
            
            chat_room_id = f"chat_{self.diagram_id}"
            if hasattr(self, 'diagram_id') and chat_room_id in _active_connections:
                forwarded_count = 0
                for peer in _active_connections[chat_room_id]:
                    if peer is not self:
                        try:
                            await peer.send(text_data=text_data)
                            forwarded_count += 1
                        except Exception as send_error:
                            try:
                                _active_connections[chat_room_id].remove(peer)
                            except ValueError:
                                pass
                                
        except Exception as e:
            try:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Chat server error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }))
            except:
                pass