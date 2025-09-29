# AI Assistant for UML Diagram System

## Overview

The AI Assistant provides contextual help and guidance for users working with UML diagrams in the collaborative UML diagram editor system. It leverages Azure OpenAI to provide intelligent responses in Spanish about UML best practices, system functionality, and diagram improvements.

## Features

- **Contextual Help**: Provides help based on current diagram state and user context
- **Multiple Context Types**: Supports general, diagram-specific, and code generation help
- **Diagram Analysis**: AI-powered analysis of diagram complexity and completeness
- **Spanish Language Support**: All responses and guidance provided in Spanish
- **Rate Limited**: Protected against abuse with configurable rate limiting
- **Anonymous Access**: No authentication required, aligns with system's anonymous architecture

## API Endpoints

### 1. Ask AI Assistant
**POST** `/api/ai-assistant/ask/`

Ask general questions about UML diagrams and system functionality.

**Request Body:**
```json
{
    "question": "¿Cómo puedo crear una relación de herencia entre clases?",
    "context_type": "general",
    "diagram_id": "optional-uuid"
}
```

**Response:**
```json
{
    "answer": "Para crear herencia en UML, debes...",
    "suggestions": ["Crear clase padre", "Añadir métodos abstractos"],
    "related_features": ["uml_editing", "diagram_validation"],
    "context_type": "general",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### 2. Ask About Specific Diagram
**POST** `/api/ai-assistant/ask-about-diagram/{diagram_id}/`

Get help about a specific diagram with context-aware assistance.

**Parameters:**
- `diagram_id` (UUID): The ID of the diagram to analyze

**Request Body:**
```json
{
    "question": "¿Cómo puedo mejorar este diagrama?",
    "context_type": "diagram"
}
```

### 3. Get Diagram Analysis
**GET** `/api/ai-assistant/analysis/{diagram_id}/`

Get AI-powered analysis of a specific diagram.

**Response:**
```json
{
    "complexity_score": 45,
    "completeness": "medium",
    "springboot_ready": true,
    "collaboration_active": false,
    "recommendations": [
        "Considerar añadir más relaciones entre clases",
        "Definir métodos en las clases principales"
    ]
}
```

### 4. Get System Statistics
**GET** `/api/ai-assistant/statistics/`

Get current system statistics for context.

**Response:**
```json
{
    "total_diagrams": 1247,
    "diagrams_today": 23,
    "system_status": "operational"
}
```

### 5. Health Check
**GET** `/api/ai-assistant/health/`

Check if the AI assistant service is operational.

## Context Types

### General (`general`)
- General help about UML diagrams and system functionality
- Best practices and guidelines
- System navigation and features

### Diagram-Specific (`diagram`)
- Analysis of current diagram state
- Improvement suggestions based on existing classes and relationships
- Context-aware guidance

### Code Generation (`code-generation`)
- Help with SpringBoot code generation requirements
- Best practices for code-ready UML diagrams
- JPA and Spring Boot configuration guidance

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# Azure OpenAI Configuration
OPENAI_AZURE_API_KEY=your_azure_openai_api_key_here
OPENAI_AZURE_API_VERSION=2024-02-15-preview
OPENAI_AZURE_API_BASE=https://your-resource-name.openai.azure.com/

# AI Assistant Settings
AI_ASSISTANT_ENABLED=True
AI_ASSISTANT_RATE_LIMIT=30/hour
AI_ASSISTANT_DEFAULT_MODEL=paralex-gpt-4o
```

### Django Settings

The following settings are automatically configured when the app is installed:

```python
# In settings.py
LOCAL_APPS = [
    # ... other apps
    'apps.ai_assistant',
]

# OpenAI Configuration
OPENAI_AZURE_API_KEY = env('OPENAI_AZURE_API_KEY', default='')
OPENAI_AZURE_API_VERSION = env('OPENAI_AZURE_API_VERSION', default='2024-02-15-preview')
OPENAI_AZURE_API_BASE = env('OPENAI_AZURE_API_BASE', default='')

# AI Assistant Configuration
AI_ASSISTANT_ENABLED = env.bool('AI_ASSISTANT_ENABLED', default=True)
AI_ASSISTANT_RATE_LIMIT = env('AI_ASSISTANT_RATE_LIMIT', default='30/hour')
AI_ASSISTANT_DEFAULT_MODEL = env('AI_ASSISTANT_DEFAULT_MODEL', default='paralex-gpt-4o')
```

## Installation

1. **Add to Requirements**
   The following dependencies are required:
   ```
   openai
   tiktoken
   python-dotenv
   ```

2. **Configure Environment**
   Copy the environment variables to your `.env` file and update with your Azure OpenAI credentials.

3. **Update URLs**
   The AI assistant URLs are automatically included in the main URL configuration.

4. **Test Installation**
   ```bash
   python manage.py check
   python manage.py test apps.ai_assistant
   ```

## Usage Examples

### Frontend Integration

```javascript
// Ask general question
const askAI = async (question) => {
    const response = await fetch('/api/ai-assistant/ask/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: question,
            context_type: 'general'
        })
    });
    
    const data = await response.json();
    return data.answer;
};

// Ask about specific diagram
const askAboutDiagram = async (diagramId, question) => {
    const response = await fetch(`/api/ai-assistant/ask-about-diagram/${diagramId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: question,
            context_type: 'diagram'
        })
    });
    
    return await response.json();
};

// Get diagram analysis
const analyzeDiagram = async (diagramId) => {
    const response = await fetch(`/api/ai-assistant/analysis/${diagramId}/`);
    return await response.json();
};
```

### Common Use Cases

1. **New User Onboarding**
   ```json
   {
       "question": "¿Cómo empiezo a crear mi primer diagrama UML?",
       "context_type": "general"
   }
   ```

2. **Diagram Improvement**
   ```json
   {
       "question": "¿Qué relaciones debería añadir a este diagrama?",
       "context_type": "diagram"
   }
   ```

3. **Code Generation Help**
   ```json
   {
       "question": "¿Está mi diagrama listo para generar código SpringBoot?",
       "context_type": "code-generation"
   }
   ```

## Architecture

### Components

1. **OpenAIService**: Base service for Azure OpenAI API interaction
2. **AIAssistantService**: Main service with UML-specific context and prompts
3. **Views**: REST API endpoints with proper error handling and rate limiting
4. **Serializers**: Request/response validation and formatting

### Context Building

The AI Assistant builds intelligent context from:

- **System Context**: UML best practices, system capabilities, SpringBoot generation
- **Diagram Context**: Current classes, relationships, complexity analysis
- **User Context**: Question type, session information

### Error Handling

- Graceful degradation when OpenAI service is unavailable
- Proper HTTP status codes for different error conditions
- Rate limiting to prevent abuse
- Comprehensive logging for debugging

## Security

- **Rate Limiting**: 30 requests per hour by default (configurable)
- **Input Validation**: All requests validated with Django serializers
- **No Authentication Required**: Aligns with anonymous system architecture
- **Error Message Sanitization**: No sensitive information leaked in errors

## Monitoring

### Logging

The AI Assistant logs important events:

```python
import logging

logger = logging.getLogger('ai_assistant')

# Question processing
logger.info(f"AI Assistant question processed: {question[:50]}...")

# Errors
logger.error(f"Error in AI service: {error}")
```

### Health Checks

Use the health endpoint to monitor service status:

```bash
curl -X GET http://localhost:8000/api/ai-assistant/health/
```

## Troubleshooting

### Common Issues

1. **OpenAI API Key Issues**
   - Verify `OPENAI_AZURE_API_KEY` is set correctly
   - Check Azure OpenAI resource is active
   - Ensure API version is compatible

2. **Rate Limiting**
   - Check current rate limit settings
   - Monitor rate limit headers in responses
   - Adjust `AI_ASSISTANT_RATE_LIMIT` if needed

3. **Context Building Errors**
   - Verify diagram exists before asking diagram-specific questions
   - Check diagram content structure is valid

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
LOGGING = {
    'loggers': {
        'apps.ai_assistant': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Contributing

When extending the AI Assistant:

1. **Add new context types** by updating the prompt templates in `AIAssistantService`
2. **Extend analysis capabilities** by modifying the `get_diagram_analysis` method
3. **Add new endpoints** following the existing pattern with proper documentation
4. **Update tests** to cover new functionality

## Integration with System

The AI Assistant seamlessly integrates with the existing anonymous UML diagram system:

- **No Authentication**: Works with the system's AllowAny permission model
- **Session-Based Context**: Uses diagram session IDs for context building
- **Real-Time Collaboration**: Can provide help during active collaboration sessions
- **Swagger Documentation**: Automatically included in API documentation

This implementation provides a comprehensive AI-powered help system that enhances the user experience while maintaining the simplicity and anonymous nature of the UML diagram platform.
