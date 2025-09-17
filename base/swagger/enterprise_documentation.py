"""
Enterprise drf-spectacular Documentation Patterns.

Standardized documentation decorators and schemas for consistent
API documentation across all ViewSets with professional formatting.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from rest_framework import status


class EnterpriseDocumentation:
    """
    Centralized documentation patterns for enterprise ViewSets.
    
    Provides standardized documentation decorators with consistent
    response formats, error handling, and professional descriptions.
    """
    
    @staticmethod
    def get_standard_crud_schema(
        resource_name: str,
        tag_name: str,
        list_serializer=None,
        detail_serializer=None,
        create_serializer=None,
        update_serializer=None,
        include_soft_delete: bool = True
    ):
        """
        Generate standard CRUD documentation schema for ViewSets.
        
        Args:
            resource_name: Human-readable resource name (e.g., "Project")
            tag_name: OpenAPI tag for categorization (e.g., "Projects")
            list_serializer: Serializer for list operations
            detail_serializer: Serializer for detail operations
            create_serializer: Serializer for create operations
            update_serializer: Serializer for update operations
            include_soft_delete: Whether to use soft delete documentation
        """
        
        resource_lower = resource_name.lower()
        
        schema_config = {
            'list': extend_schema(
                summary=f"List {resource_name}s",
                description=f"Retrieve paginated list of {resource_lower}s with comprehensive filtering and search capabilities. Supports enterprise-grade filtering, sorting, and pagination.",
                tags=[tag_name],
                responses={
                    200: list_serializer if list_serializer else detail_serializer,
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions"}
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
                description=f"Create a new {resource_lower} with comprehensive validation and automatic audit logging. All creation operations are atomic and include enterprise security measures.",
                tags=[tag_name],
                request=create_serializer if create_serializer else detail_serializer,
                responses={
                    201: detail_serializer,
                    400: {"description": "Validation errors or business logic violations"},
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions for creation"},
                    409: {"description": "Resource conflict - duplicate or constraint violation"}
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
                            "error_code": "validation_error",
                            "message": "Validation failed",
                            "status_code": 400,
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
                description=f"Retrieve comprehensive information about a specific {resource_lower}, including all related data and metadata with proper permission checks.",
                tags=[tag_name],
                responses={
                    200: detail_serializer,
                    404: {"description": f"{resource_name} not found or access denied"},
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions to view this resource"}
                }
            ),
            
            'partial_update': extend_schema(
                summary=f"Update {resource_name}",
                description=f"Partially update {resource_lower} information with atomic transaction support. Only provided fields will be updated, maintaining data integrity and audit trail.",
                tags=[tag_name],
                request=update_serializer if update_serializer else detail_serializer,
                responses={
                    200: detail_serializer,
                    400: {"description": "Validation errors or business logic violations"},
                    404: {"description": f"{resource_name} not found or access denied"},
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions for modification"},
                    409: {"description": "Update conflict - resource modified by another user"}
                },
                examples=[
                    OpenApiExample(
                        f'Update {resource_name} Success',
                        value={
                            "message": f"{resource_name} updated successfully"
                        },
                        response_only=True,
                        status_codes=[200]
                    )
                ]
            ),
        }
        
        # Add soft delete or hard delete documentation
        if include_soft_delete:
            schema_config['destroy'] = extend_schema(
                summary=f"Delete {resource_name}",
                description=f"Soft delete {resource_lower} (marks as inactive/deleted) while preserving data integrity and audit trail. Resource can be restored if needed.",
                tags=[tag_name],
                responses={
                    204: {"description": f"{resource_name} successfully marked as deleted"},
                    404: {"description": f"{resource_name} not found or access denied"},
                    400: {"description": f"{resource_name} already deleted or cannot be deleted"},
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions for deletion"}
                }
            )
        else:
            schema_config['destroy'] = extend_schema(
                summary=f"Delete {resource_name}",
                description=f"Permanently delete {resource_lower} and all associated data. This operation cannot be undone.",
                tags=[tag_name],
                responses={
                    204: {"description": f"{resource_name} successfully deleted"},
                    404: {"description": f"{resource_name} not found or access denied"},
                    400: {"description": f"{resource_name} cannot be deleted due to dependencies"},
                    401: {"description": "Authentication required"},
                    403: {"description": "Insufficient permissions for deletion"}
                }
            )
        
        # Add full update documentation if needed
        schema_config['update'] = extend_schema(
            summary=f"Full Update {resource_name}",
            description=f"Completely update {resource_lower} information with all fields. Requires all mandatory fields to be provided.",
            tags=[tag_name],
            request=update_serializer if update_serializer else detail_serializer,
            responses={
                200: detail_serializer,
                400: {"description": "Validation errors or missing required fields"},
                404: {"description": f"{resource_name} not found or access denied"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions for modification"}
            }
        )
        
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
            400: {"description": "Invalid request data or business logic violation"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"},
            404: {"description": f"{resource_name} not found"}
        }
        
        # Add 201 for POST operations that create resources
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
            description=f"Retrieve comprehensive statistics and analytics for {resource_name.lower()}s with performance metrics, usage patterns, and trend analysis.",
            tags=[tag_name],
            responses={
                200: {
                    "type": "object",
                    "properties": {
                        "overview": {
                            "type": "object",
                            "description": "High-level statistics overview"
                        },
                        "metrics": {
                            "type": "object", 
                            "description": "Detailed performance metrics"
                        },
                        "trends": {
                            "type": "object",
                            "description": "Time-based trend analysis"
                        },
                        "generated_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Statistics generation timestamp"
                        }
                    }
                },
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions to view statistics"}
            },
            parameters=[
                OpenApiParameter(
                    "period", 
                    OpenApiTypes.STR, 
                    description="Time period for statistics (7d, 30d, 90d, 1y)",
                    enum=["7d", "30d", "90d", "1y"]
                ),
                OpenApiParameter(
                    "metrics", 
                    OpenApiTypes.STR, 
                    description="Specific metrics to include (comma-separated)"
                )
            ]
        )


# Pre-configured documentation for common resources
AUTHENTICATION_SCHEMA = EnterpriseDocumentation.get_standard_crud_schema(
    resource_name="User",
    tag_name="Authentication",
    include_soft_delete=False
)

PROJECTS_SCHEMA = EnterpriseDocumentation.get_standard_crud_schema(
    resource_name="Project", 
    tag_name="Projects",
    include_soft_delete=True
)

UML_DIAGRAMS_SCHEMA = EnterpriseDocumentation.get_standard_crud_schema(
    resource_name="UML Diagram",
    tag_name="UML Diagrams", 
    include_soft_delete=True
)

COLLABORATION_SCHEMA = EnterpriseDocumentation.get_standard_crud_schema(
    resource_name="Collaboration Session",
    tag_name="Collaboration",
    include_soft_delete=True  
)

CODE_GENERATION_SCHEMA = EnterpriseDocumentation.get_standard_crud_schema(
    resource_name="Generation Request",
    tag_name="Code Generation",
    include_soft_delete=True
)

# Generic CRUD documentation for general use
CRUD_DOCUMENTATION = {
    'create': {
        'responses': {
            201: {"description": "Resource created successfully"},
            400: {"description": "Validation errors"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="Create Resource",
            description="Create a new resource with comprehensive validation and audit logging.",
            responses={
                201: {"description": "Resource created successfully"},
                400: {"description": "Validation errors"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
            }
        )
    },
    'list': {
        'responses': {
            200: {"description": "List of resources"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="List Resources", 
            description="Retrieve paginated list of resources with filtering capabilities.",
            responses={
                200: {"description": "List of resources"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
            }
        )
    },
    'retrieve': {
        'responses': {
            200: {"description": "Resource details"},
            404: {"description": "Resource not found"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="Get Resource Details",
            description="Retrieve detailed information about a specific resource.",
            responses={
                200: {"description": "Resource details"},
                404: {"description": "Resource not found"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
            }
        )
    },
    'partial_update': {
        'responses': {
            200: {"description": "Resource updated successfully"},
            400: {"description": "Validation errors"},
            404: {"description": "Resource not found"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="Update Resource",
            description="Partially update resource information with atomic transaction support.",
            responses={
                200: {"description": "Resource updated successfully"},
                400: {"description": "Validation errors"},
                404: {"description": "Resource not found"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
            }
        )
    },
    'update': {
        'responses': {
            200: {"description": "Resource updated successfully"},
            400: {"description": "Validation errors"},
            404: {"description": "Resource not found"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="Full Update Resource",
            description="Completely update resource information with all fields required.",
            responses={
                200: {"description": "Resource updated successfully"},
                400: {"description": "Validation errors"},
                404: {"description": "Resource not found"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
            }
        )
    },
    'destroy': {
        'responses': {
            204: {"description": "Resource deleted successfully"},
            404: {"description": "Resource not found"},
            401: {"description": "Authentication required"},
            403: {"description": "Insufficient permissions"}
        },
        'schema': extend_schema(
            summary="Delete Resource",
            description="Soft delete resource while preserving audit trail.",
            responses={
                204: {"description": "Resource deleted successfully"},
                404: {"description": "Resource not found"},
                401: {"description": "Authentication required"},
                403: {"description": "Insufficient permissions"}
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
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Resource not found"}
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
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Resource not found"},
        409: {"description": "Conflict - resource already exists or constraint violation"},
        500: {"description": "Internal server error"}
    }
    
    if status_codes:
        # Return only requested status codes
        return {int(code): all_responses.get(int(code), {"description": f"HTTP {code} response"}) 
                for code in status_codes}
    
    return all_responses
