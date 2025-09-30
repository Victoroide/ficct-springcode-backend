# FICCT UML Collaborative Tool - Architecture Overview

**Last Updated:** 2025-09-30  
**Architecture Type:** Anonymous Session-Based Collaboration Platform

---

## SYSTEM OVERVIEW

A **lean Django backend** providing anonymous UML diagram creation, real-time collaboration, and AI-powered assistance **without authentication requirements**.

---

## CORE PRINCIPLES

1. **Anonymous Access:** No user registration or login required
2. **Session-Based:** Django sessions track diagram ownership
3. **Real-Time:** WebSocket collaboration with Redis
4. **AI-Powered:** OpenAI integration for intelligent assistance
5. **Minimal:** Only essential services, no bloat

---

## TECHNOLOGY STACK

### Backend Framework
- **Django 4.x** - Web framework
- **Django REST Framework** - API layer
- **drf-spectacular** - API documentation

### Real-Time Communication
- **Django Channels** - WebSocket support
- **channels-redis** - Channel layer backend
- **Redis** - Message broker and caching

### AI Integration
- **OpenAI API** - Natural language processing
- **tiktoken** - Token management

### Database
- **PostgreSQL** - Primary database
- **Redis** - Session storage and WebSocket channels

### Deployment
- **Gunicorn** - WSGI server
- **Daphne** - ASGI server for WebSockets
- **Whitenoise** - Static file serving
- **Docker + docker-compose** - Containerization

---

## APPLICATION STRUCTURE

```
ficct-springcode-backend/
├── apps/
│   ├── uml_diagrams/          # Diagram management
│   │   ├── models/
│   │   │   └── uml_diagram.py # ONLY model used
│   │   ├── viewsets/
│   │   │   └── anonymous_diagram_viewset.py  # ONLY viewset
│   │   ├── serializers/
│   │   │   └── anonymous_diagram_serializer.py
│   │   ├── services/
│   │   └── urls.py
│   │
│   ├── websockets/            # Real-time collaboration
│   │   ├── consumers.py       # WebSocket consumers
│   │   ├── routing.py         # WebSocket URL routing
│   │   └── middleware.py      # Session extraction
│   │
│   └── ai_assistant/          # AI-powered features
│       ├── views.py
│       ├── serializers.py
│       ├── services/
│       │   ├── openai_service.py
│       │   ├── ai_assistant_service.py
│       │   └── command_processor_service.py
│       └── urls.py
│
├── base/                      # Project configuration
│   ├── settings.py            # Django settings
│   ├── urls.py                # Main URL routing
│   ├── asgi.py                # ASGI config (WebSockets)
│   ├── wsgi.py                # WSGI config (HTTP)
│   └── swagger/
│       └── anonymous_documentation.py
│
├── static/                    # Frontend assets
├── templates/                 # HTML templates
├── docker-compose.yml         # Container orchestration
├── Dockerfile                 # Container definition
├── requirements.txt           # Python dependencies
└── .env.example               # Configuration template
```

---

## API ENDPOINTS

### Diagram Management (Anonymous)
```
GET    /api/diagrams/              # List all diagrams
POST   /api/diagrams/              # Create new diagram
GET    /api/diagrams/{id}/         # Get diagram details
PATCH  /api/diagrams/{id}/         # Update diagram
DELETE /api/diagrams/{id}/         # Delete diagram
GET    /api/diagrams/{id}/stats/   # Get diagram statistics
POST   /api/diagrams/{id}/export/  # Export to PlantUML
```

### AI Assistant
```
POST   /api/ai-assistant/ask/                      # Ask question
POST   /api/ai-assistant/ask-about-diagram/{id}/   # Diagram-specific question
GET    /api/ai-assistant/analysis/{id}/            # Analyze diagram
POST   /api/ai-assistant/process-command/          # Natural language UML
GET    /api/ai-assistant/supported-commands/       # Command documentation
GET    /api/ai-assistant/health/                   # Service health
```

### WebSocket Collaboration
```
WS     /ws/diagrams/{id}/{session}/    # Real-time diagram updates
WS     /ws/diagrams/{id}/chat/         # Real-time chat
```

### System
```
GET    /api/health/        # Health check
GET    /api/               # API information
GET    /docs/              # Swagger UI
GET    /api/schema/        # OpenAPI schema
```

---

## DATA MODELS

### UMLDiagram (Primary Model)
```python
class UMLDiagram(models.Model):
    id = UUIDField(primary_key=True)
    title = CharField(max_length=200)
    description = TextField()
    
    session_id = CharField(max_length=64, db_index=True)
    diagram_type = CharField(choices=DiagramType.choices)
    
    content = JSONField()           # Complete diagram data
    layout_config = JSONField()     # Layout settings
    active_sessions = JSONField()   # Active collaborators
    
    created_at = DateTimeField()
    last_modified = DateTimeField()
```

**Diagram Types:**
- `CLASS` - Class Diagram
- `SEQUENCE` - Sequence Diagram
- `USE_CASE` - Use Case Diagram
- `ACTIVITY` - Activity Diagram
- `STATE` - State Diagram
- `COMPONENT` - Component Diagram
- `DEPLOYMENT` - Deployment Diagram

### Content Structure (JSON)
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "class",
      "position": {"x": 100, "y": 100},
      "data": {
        "name": "User",
        "attributes": [
          {"name": "id", "type": "int", "visibility": "private"}
        ],
        "methods": [
          {"name": "save", "returnType": "void", "visibility": "public"}
        ]
      }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2",
      "relationshipType": "ASSOCIATION",
      "multiplicity": "1..*"
    }
  ]
}
```

---

## WEBSOCKET PROTOCOL

### Connection
```javascript
const ws = new WebSocket(
  `ws://localhost:8001/ws/diagrams/${diagramId}/${sessionId}/`
);
```

### Message Types

**Incoming (Server → Client):**
```json
{
  "type": "diagram_change",
  "diagram_id": "uuid",
  "session_id": "session_uuid",
  "content": { "nodes": [...], "edges": [...] },
  "timestamp": "2025-09-30T12:00:00Z"
}

{
  "type": "user_joined",
  "session_id": "session_uuid",
  "nickname": "Guest_1234",
  "timestamp": "2025-09-30T12:00:00Z"
}

{
  "type": "user_left",
  "session_id": "session_uuid",
  "timestamp": "2025-09-30T12:00:00Z"
}
```

**Outgoing (Client → Server):**
```json
{
  "type": "update_diagram",
  "content": { "nodes": [...], "edges": [...] }
}

{
  "type": "ping",
  "timestamp": "2025-09-30T12:00:00Z"
}
```

---

## SESSION MANAGEMENT

### How It Works
1. **User visits frontend** → Django creates anonymous session
2. **User creates diagram** → `session_id` stored with diagram
3. **User returns later** → Same session = access to "my diagrams"
4. **Session expires (24h)** → Diagram remains, but loses "ownership" tracking

### Session Storage
- **Development:** Database-backed sessions
- **Production:** Redis-backed sessions (faster, scalable)

---

## AI ASSISTANT FEATURES

### Natural Language Processing
```
User: "Create class User with attributes name string and age int"
AI: Generates React Flow compatible JSON nodes
```

### Supported Commands (Multi-language)
- **English:** "Create class...", "Add attribute...", "User has many Orders"
- **Spanish:** "Crear clase...", "Añadir atributo...", "Usuario tiene muchos Pedidos"
- **French:** "Créer classe...", "Ajouter attribut..."
- **German:** "Klasse erstellen...", "Attribut hinzufügen..."

### Processing Modes
1. **Pattern-based** - Fast regex matching for common patterns
2. **AI-powered** - OpenAI API for complex natural language

---

## CONFIGURATION

### Environment Variables (.env)
```env
# Core
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Assistant
OPENAI_AZURE_API_KEY=your-key
OPENAI_AZURE_API_BASE=https://your-resource.openai.azure.com/
AI_ASSISTANT_ENABLED=True
AI_ASSISTANT_DEFAULT_MODEL=gpt-4

# Sessions
SESSION_COOKIE_AGE=86400  # 24 hours
```

---

## DEPLOYMENT

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Run development server
python manage.py runserver

# Run WebSocket server (separate terminal)
daphne -b 0.0.0.0 -p 8001 base.asgi:application
```

### Docker Production
```bash
# Build and start all services
docker-compose up -d

# Services:
# - web_wsgi (port 8000) - HTTP API
# - postgres - Database
# - redis - Sessions & WebSocket channels
```

### Environment-Specific Settings
- **DEBUG=True** - Development with detailed errors
- **DEBUG=False** - Production with security hardening
- **REDIS_URL** - Required for WebSocket scaling
- **DATABASE_URL** - PostgreSQL connection string

---

## RATE LIMITING

### Anonymous User Limits
- **API Requests:** 200/hour per IP
- **AI Assistant:** 30/hour per IP
- **WebSocket:** No rate limit (connection-based)

### Implementation
```python
# Applied automatically via DRF throttling
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',
    },
}
```

---

## SECURITY FEATURES

### Built-in Protections
- ✅ CORS protection (configured origins)
- ✅ CSRF protection (session-based)
- ✅ XSS filtering (Django defaults)
- ✅ Content type sniffing protection
- ✅ HSTS headers (production)
- ✅ Rate limiting (anti-spam)
- ✅ SQL injection protection (ORM)

### No Authentication Needed
- ❌ No user accounts
- ❌ No passwords
- ❌ No JWT tokens
- ❌ No OAuth
- ✅ Session-based anonymous tracking only

---

## MONITORING & LOGGING

### Log Files
```
logs/
├── django.log      # General application logs
└── security.log    # Security-related events
```

### Health Check
```bash
# Basic health check
curl http://localhost:8000/api/health/

# Response
{
  "status": "healthy",
  "timestamp": "2025-09-30T12:00:00Z",
  "version": "1.0.0"
}
```

---

## TESTING

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=apps --cov-report=html

# Specific app
pytest apps/uml_diagrams/tests/
```

### Test Structure
```
apps/
├── uml_diagrams/tests/
│   ├── test_models.py
│   └── test_viewsets.py
├── ai_assistant/tests.py
└── websockets/tests/
```

---

## COMMON TASKS

### Create New Diagram
```bash
curl -X POST http://localhost:8000/api/diagrams/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My UML Diagram",
    "diagram_type": "CLASS",
    "content": {"nodes": [], "edges": []}
  }'
```

### Update Diagram
```bash
curl -X PATCH http://localhost:8000/api/diagrams/{id}/ \
  -H "Content-Type: application/json" \
  -d '{
    "content": {
      "nodes": [...],
      "edges": [...]
    }
  }'
```

### AI Command Processing
```bash
curl -X POST http://localhost:8000/api/ai-assistant/process-command/ \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Create class User with name string and age int"
  }'
```

---

## TROUBLESHOOTING

### WebSocket Connection Issues
- Check Redis is running: `redis-cli ping`
- Verify ASGI server is up on port 8001
- Check CORS settings allow WebSocket origin

### AI Assistant Not Working
- Verify `OPENAI_AZURE_API_KEY` is set
- Check `AI_ASSISTANT_ENABLED=True`
- Review logs for OpenAI API errors

### Database Connection Errors
- Verify `DATABASE_URL` format
- Ensure PostgreSQL is running
- Run migrations: `python manage.py migrate`

---

## PERFORMANCE TIPS

1. **Use Redis for sessions** (faster than database)
2. **Enable query optimization** (select_related, prefetch_related)
3. **Implement pagination** for large diagram lists
4. **Cache static responses** with Whitenoise
5. **Scale horizontally** with multiple ASGI workers

---

## CONTRIBUTING

### Code Style
- Follow PEP 8 for Python code
- Use Black for formatting
- Add type hints where appropriate
- Write docstrings for public methods

### Pull Request Process
1. Create feature branch
2. Add tests for new features
3. Update documentation
4. Run `python manage.py check`
5. Ensure tests pass
6. Submit PR with clear description

---

## SUPPORT & DOCUMENTATION

- **API Docs:** http://localhost:8000/docs/
- **Source Code:** GitHub repository
- **Issues:** GitHub issues tracker

---

**Architecture Status:** ✅ OPTIMIZED AND PRODUCTION-READY

This architecture provides a **lean, focused backend** for anonymous collaborative UML diagramming with real-time features and AI assistance, eliminating all unnecessary complexity.
