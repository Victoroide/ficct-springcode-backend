from drf_spectacular.utils import OpenApiExample

WEBSOCKET_DIAGRAM_MESSAGES = {
    'connect': OpenApiExample(
        'WebSocket Connect',
        value={
            'diagram_id': 'uuid-here',
            'url': 'ws://localhost/ws/diagram/uuid-here/'
        }
    ),
    'diagram_state': OpenApiExample(
        'Diagram State Message',
        value={
            'type': 'diagram_state',
            'session_id': 'session123',
            'nickname': 'Guest_1234',
            'content': {
                'classes': [
                    {
                        'id': 'class1',
                        'name': 'User',
                        'attributes': ['id: Long', 'name: String'],
                        'methods': ['login()', 'logout()']
                    }
                ],
                'relationships': []
            },
            'active_sessions': [
                {
                    'session_id': 'session123',
                    'nickname': 'Guest_1234',
                    'cursor_position': {'x': 100, 'y': 200}
                }
            ]
        }
    ),
    'diagram_update': OpenApiExample(
        'Diagram Update Message',
        value={
            'type': 'diagram_update',
            'session_id': 'session123',
            'nickname': 'Guest_1234',
            'update_data': {
                'content': {
                    'classes': [
                        {
                            'id': 'class1',
                            'name': 'User',
                            'attributes': ['id: Long', 'name: String', 'email: String'],
                            'methods': ['login()', 'logout()', 'updateProfile()']
                        }
                    ]
                }
            }
        }
    ),
    'cursor_position': OpenApiExample(
        'Cursor Position Update',
        value={
            'type': 'cursor_position',
            'session_id': 'session123',
            'nickname': 'Guest_1234',
            'position': {'x': 150, 'y': 250}
        }
    ),
    'user_joined': OpenApiExample(
        'User Joined Notification',
        value={
            'type': 'user_joined',
            'session_id': 'session456',
            'nickname': 'Guest_5678'
        }
    ),
    'user_left': OpenApiExample(
        'User Left Notification',
        value={
            'type': 'user_left',
            'session_id': 'session456',
            'nickname': 'Guest_5678'
        }
    )
}

WEBSOCKET_CHAT_MESSAGES = {
    'connect': OpenApiExample(
        'Chat WebSocket Connect',
        value={
            'diagram_id': 'uuid-here',
            'url': 'ws://localhost/ws/diagram/uuid-here/chat/'
        }
    ),
    'chat_message': OpenApiExample(
        'Chat Message',
        value={
            'type': 'chat_message',
            'session_id': 'session123',
            'nickname': 'Guest_1234',
            'message': 'Hello everyone! Any thoughts on this diagram?',
            'timestamp': '2025-09-28T01:15:30Z'
        }
    ),
    'user_joined': OpenApiExample(
        'User Joined Chat Notification',
        value={
            'type': 'user_joined',
            'session_id': 'session456',
            'nickname': 'Guest_5678'
        }
    ),
    'user_left': OpenApiExample(
        'User Left Chat Notification',
        value={
            'type': 'user_left',
            'session_id': 'session456',
            'nickname': 'Guest_5678'
        }
    )
}

WEBSOCKET_DOCUMENTATION = {
    'diagram_websocket': {
        'title': 'UML Diagram WebSocket',
        'description': (
            'WebSocket connection for real-time UML diagram collaboration.\n\n'
            '### Connection\n'
            'Connect to: `ws://domain/ws/diagram/{uuid}/`\n\n'
            '### Features\n'
            '- Real-time diagram updates\n'
            '- Cursor position tracking\n'
            '- User presence notifications\n\n'
            '### No Authentication Required\n'
            'Anonymous access with auto-generated guest nicknames.'
        ),
        'examples': WEBSOCKET_DIAGRAM_MESSAGES
    },
    'chat_websocket': {
        'title': 'UML Diagram Chat WebSocket',
        'description': (
            'WebSocket connection for real-time chat during diagram collaboration.\n\n'
            '### Connection\n'
            'Connect to: `ws://domain/ws/diagram/{uuid}/chat/`\n\n'
            '### Features\n'
            '- Real-time chat messages\n'
            '- User presence notifications\n'
            '- Temporary chat history (not persisted)\n\n'
            '### No Authentication Required\n'
            'Anonymous access with auto-generated guest nicknames.'
        ),
        'examples': WEBSOCKET_CHAT_MESSAGES
    }
}
