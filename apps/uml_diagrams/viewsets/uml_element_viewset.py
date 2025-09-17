from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.swagger.enterprise_documentation import EnterpriseDocumentation
from ..models import UMLElement
from ..serializers import (
    UMLElementListSerializer,
    UMLElementDetailSerializer,
    UMLElementCreateSerializer
)


@extend_schema_view(
    **EnterpriseDocumentation.get_standard_crud_schema(
        resource_name="UML Element",
        tag_name="UML Diagrams",
        include_soft_delete=True
    )
)
class UMLElementViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['class_type', 'diagram', 'stereotype', 'visibility']
    search_fields = ['name', 'description', 'diagram__name']
    ordering_fields = ['name', 'created_at', 'updated_at', 'position_x', 'position_y']
    ordering = ['name']
    soft_delete_field = 'status'
    soft_delete_value = 'DELETED'
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return UMLElement.objects.none()
        
        # Get base queryset with enterprise filtering
        queryset = super().get_queryset()
        
        return queryset.filter(
            diagram__project__workspace__owner=self.request.user
        ).select_related('diagram', 'created_by', 'updated_by').prefetch_related(
            'diagram__project__workspace'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UMLElementListSerializer
        elif self.action == 'create':
            return UMLElementCreateSerializer
        return UMLElementDetailSerializer
    
    @extend_schema(
        summary="Move UML Element",
        description="Update the position of a UML element on the diagram canvas with validation and collision detection.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate position"},
                "y": {"type": "number", "description": "Y coordinate position"},
                "snap_to_grid": {"type": "boolean", "description": "Whether to snap to grid"}
            },
            "required": ["x", "y"]
        },
        responses={
            200: {"description": "Element moved successfully"},
            400: {"description": "Invalid position coordinates"}
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def move_to(self, request, pk=None):
        """Move UML element to new position."""
        element = self.get_object()
        
        try:
            x = request.data.get('x')
            y = request.data.get('y')
            snap_to_grid = request.data.get('snap_to_grid', False)
            
            # Validate coordinates
            if x is None or y is None:
                return Response({
                    'error': True,
                    'error_code': 'missing_coordinates',
                    'message': 'Both x and y coordinates are required',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Move element
            if hasattr(element, 'move_to'):
                element.move_to(x, y, snap_to_grid=snap_to_grid)
            else:
                element.position_x = x
                element.position_y = y
                element.save()
            
            # Log move action
            self.log_transaction_event(
                "UML_ELEMENT_MOVED",
                instance=element,
                details={'x': x, 'y': y, 'snap_to_grid': snap_to_grid}
            )
            
            return Response({
                'success': True,
                'message': 'Element moved successfully',
                'position': {'x': x, 'y': y}
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'move_failed',
                'message': f'Failed to move element: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Resize UML Element",
        description="Resize a UML element with dimension validation and automatic content adjustment.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "width": {"type": "number", "minimum": 10, "description": "Element width"},
                "height": {"type": "number", "minimum": 10, "description": "Element height"},
                "maintain_aspect_ratio": {"type": "boolean", "description": "Whether to maintain aspect ratio"}
            },
            "required": ["width", "height"]
        },
        responses={
            200: {"description": "Element resized successfully"},
            400: {"description": "Invalid dimensions"}
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def resize(self, request, pk=None):
        """Resize UML element dimensions."""
        element = self.get_object()
        
        try:
            width = request.data.get('width')
            height = request.data.get('height')
            maintain_aspect_ratio = request.data.get('maintain_aspect_ratio', False)
            
            # Validate dimensions
            if width is None or height is None:
                return Response({
                    'error': True,
                    'error_code': 'missing_dimensions',
                    'message': 'Both width and height are required',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if width < 10 or height < 10:
                return Response({
                    'error': True,
                    'error_code': 'invalid_dimensions',
                    'message': 'Minimum dimensions are 10x10 pixels',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Resize element
            if hasattr(element, 'resize'):
                element.resize(width, height, maintain_aspect_ratio=maintain_aspect_ratio)
            else:
                element.width = width
                element.height = height
                element.save()
            
            # Log resize action
            self.log_transaction_event(
                "UML_ELEMENT_RESIZED",
                instance=element,
                details={'width': width, 'height': height, 'maintain_aspect_ratio': maintain_aspect_ratio}
            )
            
            return Response({
                'success': True,
                'message': 'Element resized successfully',
                'dimensions': {'width': width, 'height': height}
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'resize_failed',
                'message': f'Failed to resize element: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Add UML Element Attribute",
        description="Add a new attribute to a UML class element with type validation and visibility settings.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Attribute name"},
                "type": {"type": "string", "description": "Attribute data type"},
                "visibility": {"type": "string", "enum": ["public", "private", "protected"], "description": "Visibility modifier"},
                "default_value": {"type": "string", "description": "Default value"}
            },
            "required": ["name", "type"]
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def add_attribute(self, request, pk=None):
        """Add attribute to UML class element."""
        element = self.get_object()
        
        try:
            name = request.data.get('name')
            attr_type = request.data.get('type')
            visibility = request.data.get('visibility', 'public')
            default_value = request.data.get('default_value')
            
            if not name or not attr_type:
                return Response({
                    'error': True,
                    'error_code': 'missing_attribute_data',
                    'message': 'Attribute name and type are required',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Add attribute to element
            if hasattr(element, 'add_attribute'):
                element.add_attribute(name, attr_type, visibility, default_value)
            
            # Log attribute addition
            self.log_transaction_event(
                "UML_ELEMENT_ATTRIBUTE_ADDED",
                instance=element,
                details={'name': name, 'type': attr_type, 'visibility': visibility}
            )
            
            return Response({
                'success': True,
                'message': 'Attribute added successfully',
                'attribute': {
                    'name': name,
                    'type': attr_type,
                    'visibility': visibility,
                    'default_value': default_value
                }
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'attribute_addition_failed',
                'message': f'Failed to add attribute: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Add UML Element Method",
        description="Add a new method to a UML class element with parameter specification and return type validation.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Method name"},
                "return_type": {"type": "string", "description": "Return data type"},
                "visibility": {"type": "string", "enum": ["public", "private", "protected"]},
                "parameters": {"type": "array", "items": {"type": "object"}, "description": "Method parameters"}
            },
            "required": ["name"]
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def add_method(self, request, pk=None):
        """Add method to UML class element."""
        element = self.get_object()
        
        try:
            name = request.data.get('name')
            return_type = request.data.get('return_type', 'void')
            visibility = request.data.get('visibility', 'public')
            parameters = request.data.get('parameters', [])
            
            if not name:
                return Response({
                    'error': True,
                    'error_code': 'missing_method_name',
                    'message': 'Method name is required',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Add method to element
            if hasattr(element, 'add_method'):
                element.add_method(name, return_type, visibility, parameters)
            
            # Log method addition
            self.log_transaction_event(
                "UML_ELEMENT_METHOD_ADDED",
                instance=element,
                details={'name': name, 'return_type': return_type, 'visibility': visibility, 'parameter_count': len(parameters)}
            )
            
            return Response({
                'success': True,
                'message': 'Method added successfully',
                'method': {
                    'name': name,
                    'return_type': return_type,
                    'visibility': visibility,
                    'parameters': parameters
                }
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'method_addition_failed',
                'message': f'Failed to add method: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
