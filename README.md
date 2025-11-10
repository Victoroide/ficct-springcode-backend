# FICCT UML Collaborative Tool - Architecture Overview

**Last Updated:** 2025-11-09  
**Architecture Type:** Anonymous Session-Based Collaboration Platform with AI Vision

---

## SYSTEM OVERVIEW

A **lean Django backend** providing anonymous UML diagram creation, real-time collaboration, AI-powered assistance, and **image-to-UML extraction** using Amazon Nova Pro **without authentication requirements**.

---

## CORE PRINCIPLES

1. **Anonymous Access:** No user registration or login required
2. **Session-Based:** Django sessions track diagram ownership
3. **Real-Time:** WebSocket collaboration with Redis
4. **AI-Powered:** Azure OpenAI (o-series) + Amazon Bedrock Nova Pro
5. **Vision-Enabled:** Extract UML diagrams from images
6. **Minimal:** Only essential services, no bloat

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
- **Azure OpenAI API** - Text processing with o-series models (o1, o1-mini, o4-mini)
- **Amazon Bedrock (Nova Pro)** - Image-to-UML extraction and vision processing
- **AWS SDK (boto3/botocore)** - Bedrock integration
- **tiktoken** - Token management and cost estimation

**Cost Efficiency:**
- Nova Pro: $0.80 input / $3.20 output per 1M tokens
- Typical image processing: $0.001-0.003 per image
- 66% cheaper than GPT-4 Vision for diagram extraction

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
│   ├── ai_assistant/          # AI-powered features
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── services/
│   │   │   ├── openai_service.py          # Azure OpenAI with o-series support
│   │   │   ├── ai_assistant_service.py     # Contextual AI assistance
│   │   │   ├── command_processor_service.py # Direct OpenAI approach
│   │   │   └── nova_vision_service.py      # Amazon Bedrock integration
│   │   └── urls.py
│   │
│   └── flutter_projects/      # Flutter metadata management
│       ├── models/
│       │   └── flutter_project.py          # Project configuration storage
│       ├── serializers/
│       │   └── flutter_project_serializer.py
│       ├── viewsets/
│       │   └── flutter_project_viewset.py
│       ├── validators/
│       │   └── flutter_validators.py       # Package name validation
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
POST   /api/ai-assistant/process-command/          # Create new or modify existing diagrams
GET    /api/ai-assistant/supported-commands/       # Command documentation
GET    /api/ai-assistant/health/                   # Service health
```

### Image Processing (Amazon Nova Pro)
```
POST   /api/ai-assistant/diagrams/from-image/      # Extract UML from image
POST   /api/diagrams/{id}/update-from-image/       # Merge image with existing
```

### Flutter Project Metadata
```
POST   /api/flutter-projects/                      # Create project
GET    /api/flutter-projects/                      # List projects
GET    /api/flutter-projects/{id}/                 # Get project details
PATCH  /api/flutter-projects/{id}/                 # Update project
DELETE /api/flutter-projects/{id}/                 # Delete project
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

### Natural Language Processing (Unified Endpoint)
```
User: "Create class User with attributes name string and age int"
AI: Generates React Flow compatible JSON nodes (direct OpenAI API)

User: "Add method save to User class" (with diagram_id)
AI: Modifies existing diagram preserving layout
```

### Bilingual Command Support
- **Spanish:** "crea clase Usuario con atributos nombre string, edad int"
- **English:** "create class User with attributes name string, age int"
- **French:** "créer classe Utilisateur avec attributs nom string, age int"

**Processing Approach:**
- Single endpoint handles both: creation and modification
- Direct OpenAI API call (no pattern matching)
- Unified prompts for all languages
- React Flow JSON generation with intelligent positioning
- Pass `diagram_id` + `current_diagram_data` to modify existing diagrams

### Image-to-UML Extraction (Amazon Nova Pro)
```
Input: Upload diagram image (PNG/JPG/JPEG, max 20MB)
Output: Complete React Flow JSON with classes, attributes, methods, relationships
Cost: $0.001-0.003 per image (66% cheaper than GPT-4 Vision)
```

**Supported Elements:**
- Classes with attributes and methods
- Relationships (inheritance, association, composition)
- Visibility modifiers (public, private, protected)
- Data types and multiplicities

### Create or Modify with Single Endpoint
```
# Create new diagram
User: "Create class User with name and age"
AI: Generates new diagram JSON

# Modify existing diagram
User: "Add method calculateAge to User class" (with diagram_id)
AI: Modifies existing diagram preserving layout and other elements
```

---

## SECOND PARTIAL IMPLEMENTATION

### Overview
Second Partial exam implementation added advanced AI vision capabilities, simplified command processing architecture, o-series model support, and Flutter project metadata management.

### Image-to-UML Processing (Amazon Nova Pro)

**Feature:** Extract UML class diagrams from hand-drawn or digital images using Amazon Bedrock Nova Pro vision model.

**Capabilities:**
- Upload PNG, JPG, JPEG images (max 20MB)
- Automatic class detection with attributes and methods
- Relationship extraction (inheritance, associations, compositions)
- Visibility modifier recognition (public/private/protected)
- React Flow JSON generation with intelligent positioning

**API Endpoints:**
```bash
# Extract diagram from image
POST /api/ai-assistant/diagrams/from-image/
Content-Type: multipart/form-data
Body: image file + diagram_type

# Merge image with existing diagram
POST /api/diagrams/{id}/update-from-image/
Content-Type: multipart/form-data
Body: image file
```

**Cost Efficiency:**
- $0.80 per 1M input tokens / $3.20 per 1M output tokens
- Typical image: $0.001-0.003 per extraction
- 66% cheaper than GPT-4 Vision alternative
- No local OCR dependencies (Tesseract, EasyOCR, YOLO removed)

**Technical Implementation:**
- Service: `nova_vision_service.py` (Amazon Bedrock SDK integration)
- Model: `amazon.nova-pro-v1:0`
- Region: `us-east-1` (configurable)
- Format: Base64 image encoding with detailed extraction prompts

### Bilingual Natural Language Commands

**Feature:** Process UML creation commands in Spanish, English, and French without pattern matching.

**Architecture Simplification:**
- **Before:** Pattern-based regex → Fallback to OpenAI
- **After:** Direct OpenAI API calls only (simplified)
- Unified prompts work across all supported languages
- No maintenance of language-specific regex patterns

**Example Commands:**
```bash
# Spanish
"crea clase Usuario con atributos nombre string, edad int"

# English  
"create class User with attributes name string, age int"

# French
"créer classe Utilisateur avec attributs nom string, age int"
```

**Service:** `command_processor_service.py` (direct OpenAI approach)

### o-Series Model Support

**Feature:** Full compatibility with Azure OpenAI o-series reasoning models.

**Supported Models:**
- `o1` - Full reasoning capabilities
- `o1-mini` - Cost-efficient reasoning
- `o4-mini` - Latest mini reasoning model

**Automatic Parameter Filtering:**
```python
# Detects o-series models and removes unsupported parameters:
- temperature (not supported in o-series)
- response_format (not supported in o-series)
- max_tokens → max_completion_tokens (parameter name change)
- system role → user role (system messages converted)
```

**Configuration:**
```env
AI_ASSISTANT_DEFAULT_MODEL=o4-mini  # or o1, o1-mini
```

**Implementation:** `openai_service.py` (auto-detection and parameter filtering)

### Flutter Project Metadata Management

**Feature:** Store Flutter mobile app project configuration for code generation context.

**Data Model:**
```python
class FlutterProject(models.Model):
    id = UUIDField(primary_key=True)
    session_id = CharField()  # Anonymous session-based
    project_name = CharField(max_length=200)
    package_name = CharField()  # e.g., com.example.app
    description = TextField()
    
    # Configuration
    theme_config = JSONField()      # Colors, fonts, styles
    navigation_type = CharField()   # drawer, tabs, bottom_nav
    state_management = CharField()  # provider, bloc, riverpod
    
    created_at = DateTimeField()
    updated_at = DateTimeField()
```

**Validation:**
- Package name format: `com.domain.app` (3+ segments with dots)
- Session-based ownership (anonymous)
- JSON schema validation for theme_config

**API Endpoints:**
```bash
POST   /api/flutter-projects/          # Create project
GET    /api/flutter-projects/          # List user's projects
GET    /api/flutter-projects/{id}/     # Get project details
PATCH  /api/flutter-projects/{id}/     # Update configuration
DELETE /api/flutter-projects/{id}/     # Delete project
```

**Use Case:** Stores Flutter project settings for future code generation features, providing context about theme, navigation, and architecture preferences.

### Unified Command Processing

**Feature:** Single endpoint for both creating new diagrams and modifying existing ones.

**Endpoint:**
```bash
# Create new diagram
POST /api/ai-assistant/process-command/
{
  "command": "Create class User with name string and age int"
}

# Modify existing diagram
POST /api/ai-assistant/process-command/
{
  "command": "Add method calculateAge to User class",
  "diagram_id": "uuid",
  "current_diagram_data": { "nodes": [...], "edges": [...] }
}
```

**Behavior:**
- **Without diagram_id**: Creates new diagram from scratch
- **With diagram_id + current_diagram_data**: Modifies existing diagram
- Preserves unchanged elements and positions when modifying
- Updates only affected nodes/edges

**Benefits:**
- Single endpoint for all command processing
- Maintains user's custom positioning
- Faster processing (smaller context)
- Preserves manual refinements

### Dependency Changes

**Added:**
- `boto3` - AWS SDK for Bedrock
- `botocore` - AWS SDK core functionality

**Removed:**
- `pytesseract` - Local OCR (replaced by Nova Pro)
- `opencv-python` - Image processing (not needed)
- `easyocr` - OCR alternative (not needed)
- `ultralytics` - YOLO detection (not needed)
- `dashscope` - Qwen attempt (failed, removed)

**Result:** Simplified dependencies, cloud-based vision processing, no local ML models required.

### Redis Database Separation

**Configuration Enhancement:**
```python
# Before: Single Redis database
REDIS_URL=redis://host:6379/0

# After: Separated databases for different purposes
CACHE_REDIS_URL=redis://host:6379/0         # Django cache
CHANNEL_LAYERS_REDIS_URL=redis://host:6379/1  # WebSocket channels  
THROTTLE_REDIS_URL=redis://host:6379/2      # Rate limiting
```

**Benefits:**
- Isolated data per service
- Independent scaling
- Clearer monitoring
- No data collision

### Technical Achievements

**Architecture:**
- ✅ Simplified command processing (removed pattern matching)
- ✅ Cloud-based vision (no local ML dependencies)
- ✅ o-series model compatibility (parameter filtering)
- ✅ Bilingual support without regex maintenance

**Cost Optimization:**
- ✅ Nova Pro 66% cheaper than GPT-4 Vision
- ✅ $0.001-0.003 per image extraction
- ✅ Efficient token usage with o4-mini model

**Maintainability:**
- ✅ Fewer dependencies to update
- ✅ No pattern regex to maintain
- ✅ Cloud services handle model updates
- ✅ Cleaner service architecture

### Migration Notes

**No Breaking Changes:**
- All existing endpoints remain functional
- Backward compatible with previous diagrams
- Session management unchanged
- WebSocket protocol unchanged

**New Capabilities:**
- Image upload endpoints added
- Flutter projects endpoints added
- Unified command endpoint (create + modify)
- o-series models automatically detected

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

# Redis (Separated Databases)
CACHE_REDIS_URL=redis://default:PASSWORD@host:port/0         # Cache
CHANNEL_LAYERS_REDIS_URL=redis://default:PASSWORD@host:port/1  # WebSockets
THROTTLE_REDIS_URL=redis://default:PASSWORD@host:port/2      # Rate limiting

# Azure OpenAI (o-series models)
OPENAI_AZURE_API_KEY=your-key
OPENAI_AZURE_API_BASE=https://your-resource.openai.azure.com/
OPENAI_AZURE_API_VERSION=2024-02-15-preview
AI_ASSISTANT_ENABLED=True
AI_ASSISTANT_DEFAULT_MODEL=o4-mini  # Supports: o1, o1-mini, o4-mini

# AWS Bedrock (Image Processing)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

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

### AI Command Processing (Create New)
```bash
curl -X POST http://localhost:8000/api/ai-assistant/process-command/ \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Create class User with name string and age int"
  }'
```

### AI Command Processing (Modify Existing)
```bash
curl -X POST http://localhost:8000/api/ai-assistant/process-command/ \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Add method save to User class",
    "diagram_id": "uuid-here",
    "current_diagram_data": {
      "nodes": [...],
      "edges": [...]
    }
  }'
```

### Image-to-UML Extraction
```bash
curl -X POST http://localhost:8000/api/ai-assistant/diagrams/from-image/ \
  -F "image=@diagram.png" \
  -F "diagram_type=CLASS"
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
- Verify model name: `o4-mini`, `o1`, or `o1-mini`
- Review logs for OpenAI API errors
- Check Azure OpenAI API version compatibility

### Image Processing Issues (AWS Bedrock)
- Verify AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Check region: `AWS_DEFAULT_REGION=us-east-1`
- Ensure Bedrock access enabled in AWS account
- Verify image format: PNG, JPG, JPEG only
- Check image size: max 20MB
- Review logs for Bedrock API errors

### Database Connection Errors
- Verify `DATABASE_URL` format
- Ensure PostgreSQL is running
- Run migrations: `python manage.py migrate`

### Redis Connection Issues
- Verify separated Redis URLs are configured
- Check Redis is accessible on all databases (0, 1, 2)
- Ensure authentication credentials are correct
- Test connection: `redis-cli -u <REDIS_URL> ping`

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
