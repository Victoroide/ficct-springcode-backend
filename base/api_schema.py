"""
Anonymous UML Tool API Schema.

Defines the root API schema view and endpoint overview.
"""

from rest_framework.decorators import api_view, permission_classes, schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample


@extend_schema(
    tags=['System'],
    summary="API Overview",
    description="Get overview of available endpoints in the Anonymous UML Tool API",
    examples=[
        OpenApiExample(
            "API Overview Response",
            value={
                "title": "Anonymous UML Diagram API",
                "version": "1.0.0",
                "description": "Zero-friction UML diagramming platform with anonymous real-time collaboration",
                "endpoints": {
                    "diagrams": {
                        "list": "/api/diagrams/",
                        "create": "/api/diagrams/",
                        "detail": "/api/diagrams/{id}/",
                        "statistics": "/api/diagrams/stats/",
                        "export_plantuml": "/api/diagrams/{id}/export_plantuml/",
                        "clone": "/api/diagrams/{id}/clone/"
                    },
                    "websockets": {
                        "diagram": "ws://domain/ws/diagram/{id}/",
                        "chat": "ws://domain/ws/diagram/{id}/chat/"
                    }
                }
            },
            response_only=True
        )
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_schema_view(request):
    """
    API Schema View.
    
    Returns an overview of all available endpoints in the Anonymous UML Tool API.
    """
    # Generate base URL (works for both http and https)
    base_url = f"{request.scheme}://{request.get_host()}"
    ws_protocol = "wss" if request.scheme == "https" else "ws"
    ws_url = f"{ws_protocol}://{request.get_host()}"
    
    return Response({
        "title": "Anonymous UML Diagram API",
        "version": "1.0.0",
        "description": "Zero-friction UML diagramming platform with anonymous real-time collaboration",
        "documentation_url": f"{base_url}/docs/",
        "endpoints": {
            "diagrams": {
                "list": f"{base_url}/api/diagrams/",
                "create": f"{base_url}/api/diagrams/",
                "detail": f"{base_url}/api/diagrams/{{id}}/",
                "statistics": f"{base_url}/api/diagrams/stats/",
                "export_plantuml": f"{base_url}/api/diagrams/{{id}}/export_plantuml/",
                "clone": f"{base_url}/api/diagrams/{{id}}/clone/"
            },
            "websockets": {
                "diagram": f"{ws_url}/ws/diagram/{{id}}/",
                "chat": f"{ws_url}/ws/diagram/{{id}}/chat/"
            }
        }
    })
