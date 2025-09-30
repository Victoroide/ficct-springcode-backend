"""
Anonymous drf-spectacular Documentation Patterns.

Simplified documentation decorators and schemas for the anonymous UML diagram service.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from rest_framework import status


class AnonymousDocumentation:
    """
    Documentation patterns for anonymous UML diagram service.
    
    Provides simplified documentation decorators without authentication requirements
    and with a focus on public, zero-friction access.
    """
    
    @staticmethod
    def get_standard_crud_schema(
        resource_name: str,
        tag_name: str,
        list_serializer=None,
        detail_serializer=None,
        create_serializer=None,
        update_serializer=None,
    ):
        """
        Generate standard CRUD documentation schema for anonymous ViewSets.
        
        Args:
            resource_name: Human-readable resource name (e.g., "UML Diagram")
            tag_name: OpenAPI tag for categorization
            list_serializer: Serializer for list operations
            detail_serializer: Serializer for detail operations
            create_serializer: Serializer for create operations
            update_serializer: Serializer for update operations
        """
        
        resource_lower = resource_name.lower()
        
        schema_config = {
            'list': extend_schema(
                summary=f"List {resource_name}s",
                description=f"Retrieve paginated list of {resource_lower}s with filtering and search capabilities.",
                tags=[tag_name],
                responses={
                    200: list_serializer if list_serializer else detail_serializer,
                    429: {"description": "Rate limit exceeded"}
                },
                parameters=[
                    OpenApiParameter("page", OpenApiTypes.INT, description="Page number for pagination"),
                    OpenApiParameter("page_size", OpenApiTypes.INT, description="Number of items per page (max 100)"),
                    OpenApiParameter("ordering", OpenApiTypes.STR, description="Field to order by (prefix with '-' for descending)"),
                    OpenApiParameter("search", OpenApiTypes.STR, description="Search across relevant fields"),
                ]
            ),
            
            'create': extend_schema(
                summary=f"Create {resource_name}",
                description=f"Create a new {resource_lower} without authentication. Session-based tracking used for temporary identification.",
                tags=[tag_name],
                request=create_serializer if create_serializer else detail_serializer,
                responses={
                    201: detail_serializer,
                    400: {"description": "Validation errors"},
                    429: {"description": "Rate limit exceeded"}
                },
                examples=[
                    OpenApiExample(
                        f'Create {resource_name} Success',
                        value={
                            "message": f"{resource_name} created successfully",
                            "id": "uuid-here"
                        },
                        response_only=True,
                        status_codes=[201]
                    ),
                    OpenApiExample(
                        'Validation Error Response',
                        value={
                            "error": True,
                            "message": "Validation failed",
                            "details": {
                                "field_name": ["This field is required."]
                            }
                        },
                        response_only=True,
                        status_codes=[400]
                    )
                ]
            ),
            
            'retrieve': extend_schema(
                summary=f"Get {resource_name} Details",
                description=f"Retrieve information about a specific {resource_lower} by UUID. No authentication required.",
                tags=[tag_name],
                responses={
                    200: detail_serializer,
                    404: {"description": f"{resource_name} not found"},
                    429: {"description": "Rate limit exceeded"}
                }
            ),
            
            'partial_update': extend_schema(
                summary=f"Update {resource_name}",
                description=f"Partially update {resource_lower}. Only provided fields will be updated.",
                tags=[tag_name],
                request=update_serializer if update_serializer else detail_serializer,
                responses={
                    200: detail_serializer,
                    400: {"description": "Validation errors"},
                    404: {"description": f"{resource_name} not found"},
                    429: {"description": "Rate limit exceeded"}
                }
            ),
            
            'update': extend_schema(
                summary=f"Full Update {resource_name}",
                description=f"Completely update {resource_lower} information with all fields.",
                tags=[tag_name],
                request=update_serializer if update_serializer else detail_serializer,
                responses={
                    200: detail_serializer,
                    400: {"description": "Validation errors or missing required fields"},
                    404: {"description": f"{resource_name} not found"},
                    429: {"description": "Rate limit exceeded"}
                }
            ),
            
            'destroy': extend_schema(
                summary=f"Delete {resource_name}",
                description=f"Delete {resource_lower} permanently. This operation cannot be undone.",
                tags=[tag_name],
                responses={
                    204: {"description": f"{resource_name} successfully deleted"},
                    404: {"description": f"{resource_name} not found"},
                    429: {"description": "Rate limit exceeded"}
                }
            )
        }
        
        return schema_config
    
    @staticmethod
    def get_custom_action_schema(
        action_name: str,
        resource_name: str,
        tag_name: str,
        description: str,
        method: str = 'post',
        request_serializer=None,
        response_serializer=None,
        parameters=None
    ):
        """
        Generate documentation for custom ViewSet actions.
        
        Args:
            action_name: Name of the custom action
            resource_name: Human-readable resource name
            tag_name: OpenAPI tag for categorization
            description: Detailed description of the action
            method: HTTP method (default: 'post')
            request_serializer: Request body serializer
            response_serializer: Response serializer
            parameters: List of OpenApiParameter objects
        """
        
        responses = {
            200: response_serializer if response_serializer else {"description": f"{action_name.title()} completed successfully"},
            400: {"description": "Invalid request data"},
            404: {"description": f"{resource_name} not found"},
            429: {"description": "Rate limit exceeded"}
        }

        if method.upper() == 'POST' and 'create' in action_name.lower():
            responses[201] = response_serializer if response_serializer else {"description": "Resource created successfully"}
            responses.pop(200)  # Remove 200 for creation operations
        
        schema_kwargs = {
            'summary': f"{action_name.replace('_', ' ').title()} {resource_name}",
            'description': description,
            'tags': [tag_name],
            'responses': responses
        }
        
        if request_serializer:
            schema_kwargs['request'] = request_serializer
        
        if parameters:
            schema_kwargs['parameters'] = parameters
        
        return extend_schema(**schema_kwargs)
    
    @staticmethod
    def get_statistics_schema(resource_name: str, tag_name: str):
        """Generate documentation for statistics endpoints."""
        
        return extend_schema(
            summary=f"Get {resource_name} Statistics",
            description=f"Retrieve basic statistics about {resource_name.lower()}s without authentication.",
            tags=[tag_name],
            responses={
                200: {
                    "type": "object",
                    "properties": {
                        "total_diagrams": {
                            "type": "integer",
                            "description": "Total number of diagrams"
                        },
                        "diagrams_today": {
                            "type": "integer", 
                            "description": "Diagrams created today"
                        },
                        "active_sessions": {
                            "type": "integer",
                            "description": "Current active sessions"
                        },
                        "generated_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Statistics generation timestamp"
                        }
                    }
                },
                429: {"description": "Rate limit exceeded"}
            }
        )

UML_DIAGRAMS_SCHEMA = AnonymousDocumentation.get_standard_crud_schema(
    resource_name="UML Diagram",
    tag_name="UML Diagrams"
)

WEBSOCKET_SCHEMA = {
    'websocket_info': extend_schema(
        summary="WebSocket Connection Info",
        description="Get information about WebSocket endpoints for real-time collaboration.",
        tags=["WebSocket Collaboration"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "diagram_ws_url": {
                        "type": "string",
                        "description": "WebSocket URL for diagram collaboration"
                    },
                    "chat_ws_url": {
                        "type": "string", 
                        "description": "WebSocket URL for diagram chat"
                    },
                    "connection_info": {
                        "type": "string",
                        "description": "How to connect to WebSockets"
                    }
                }
            },
            429: {"description": "Rate limit exceeded"}
        }
    )
}

CRUD_DOCUMENTATION = {
    'create': {
        'responses': {
            201: {"description": "Resource created successfully"},
            400: {"description": "Validation errors"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="Create Resource",
            description="Create a new resource without authentication.",
            responses={
                201: {"description": "Resource created successfully"},
                400: {"description": "Validation errors"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    },
    'list': {
        'responses': {
            200: {"description": "List of resources"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="List Resources", 
            description="Retrieve paginated list of resources.",
            responses={
                200: {"description": "List of resources"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    },
    'retrieve': {
        'responses': {
            200: {"description": "Resource details"},
            404: {"description": "Resource not found"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="Get Resource Details",
            description="Retrieve information about a specific resource.",
            responses={
                200: {"description": "Resource details"},
                404: {"description": "Resource not found"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    },
    'partial_update': {
        'responses': {
            200: {"description": "Resource updated successfully"},
            400: {"description": "Validation errors"},
            404: {"description": "Resource not found"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="Update Resource",
            description="Partially update resource information.",
            responses={
                200: {"description": "Resource updated successfully"},
                400: {"description": "Validation errors"},
                404: {"description": "Resource not found"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    },
    'update': {
        'responses': {
            200: {"description": "Resource updated successfully"},
            400: {"description": "Validation errors"},
            404: {"description": "Resource not found"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="Full Update Resource",
            description="Completely update resource information.",
            responses={
                200: {"description": "Resource updated successfully"},
                400: {"description": "Validation errors"},
                404: {"description": "Resource not found"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    },
    'destroy': {
        'responses': {
            204: {"description": "Resource deleted successfully"},
            404: {"description": "Resource not found"},
            429: {"description": "Rate limit exceeded"}
        },
        'schema': extend_schema(
            summary="Delete Resource",
            description="Permanently delete resource.",
            responses={
                204: {"description": "Resource deleted successfully"},
                404: {"description": "Resource not found"},
                429: {"description": "Rate limit exceeded"}
            }
        )
    }
}


def get_custom_action_documentation(action_name, description, method='post', request_serializer=None, response_serializer=None):
    """
    Generate documentation for custom ViewSet actions.
    
    Args:
        action_name: Name of the custom action
        description: Description of the action
        method: HTTP method (default: 'post')
        request_serializer: Request serializer
        response_serializer: Response serializer
    """
    responses = {
        200: response_serializer if response_serializer else {"description": f"{action_name} completed successfully"},
        400: {"description": "Invalid request data"},
        404: {"description": "Resource not found"},
        429: {"description": "Rate limit exceeded"}
    }
    
    if method.upper() == 'POST':
        responses[201] = {"description": "Resource created successfully"}
    
    schema_kwargs = {
        'summary': action_name.replace('_', ' ').title(),
        'description': description,
        'responses': responses
    }
    
    if request_serializer:
        schema_kwargs['request'] = request_serializer
    
    return extend_schema(**schema_kwargs)


def get_error_responses(status_codes=None):
    """Get standard error response schemas."""
    all_responses = {
        400: {"description": "Bad request - validation errors"},
        404: {"description": "Resource not found"},
        409: {"description": "Conflict - resource already exists"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
    
    if status_codes:

        return {int(code): all_responses.get(int(code), {"description": f"HTTP {code} response"}) 
                for code in status_codes}
    
    return all_responses
