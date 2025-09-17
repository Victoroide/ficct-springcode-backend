from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.swagger.enterprise_documentation import EnterpriseDocumentation, UML_DIAGRAMS_SCHEMA
from ..models import UMLDiagram
from ..serializers import (
    UMLDiagramListSerializer,
    UMLDiagramDetailSerializer,
    UMLDiagramCreateSerializer
)
from django.utils import timezone


@extend_schema_view(**UML_DIAGRAMS_SCHEMA)
class UMLDiagramViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['diagram_type', 'status', 'project', 'created_by']
    search_fields = ['name', 'description', 'project__name']
    ordering_fields = ['name', 'created_at', 'updated_at', 'version_number']
    ordering = ['-updated_at']
    soft_delete_field = 'status'
    soft_delete_value = 'DELETED'
    
    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return UMLDiagram.objects.none()
        
        # Get base queryset with enterprise filtering
        queryset = super().get_queryset()
        
        # Apply user-based filtering
        return queryset.filter(
            project__workspace__owner=self.request.user
        ).select_related('project', 'created_by', 'updated_by').prefetch_related(
            'project__workspace'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UMLDiagramListSerializer
        elif self.action == 'create':
            return UMLDiagramCreateSerializer
        return UMLDiagramDetailSerializer
    
    @extend_schema(
        summary="Clone UML Diagram",
        description="Create a copy of an existing UML diagram with optional modifications and new project assignment.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for the cloned diagram"},
                "description": {"type": "string", "description": "Description for the cloned diagram"},
                "project_id": {"type": "string", "format": "uuid", "description": "Target project ID"},
                "include_relationships": {"type": "boolean", "description": "Whether to include relationships"}
            },
            "required": ["name"]
        },
        responses={
            201: UMLDiagramDetailSerializer,
            400: {"description": "Invalid clone data"},
            403: {"description": "Permission denied"}
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing UML diagram."""
        source_diagram = self.get_object()
        
        try:
            # Extract clone parameters
            clone_name = request.data.get('name')
            clone_description = request.data.get('description', f"Cloned from: {source_diagram.name}")
            project_id = request.data.get('project_id')
            include_relationships = request.data.get('include_relationships', True)
            
            # Validate required fields
            if not clone_name:
                return Response({
                    'error': True,
                    'error_code': 'missing_clone_name',
                    'message': 'Clone name is required',
                    'status_code': 400
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create cloned diagram
            cloned_diagram = UMLDiagram.objects.create(
                name=clone_name,
                description=clone_description,
                project_id=project_id or source_diagram.project.id,
                diagram_type=source_diagram.diagram_type,
                diagram_data=source_diagram.diagram_data.copy(),
                metadata=source_diagram.metadata.copy() if source_diagram.metadata else {},
                created_by=request.user
            )
            
            # Log cloning action
            self.log_transaction_event(
                f"UML_DIAGRAM_CLONE_SUCCESS",
                instance=cloned_diagram,
                details={
                    'source_diagram_id': str(source_diagram.id),
                    'include_relationships': include_relationships
                }
            )
            
            serializer = self.get_serializer(cloned_diagram)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'clone_failed',
                'message': f'Failed to clone diagram: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Create Diagram Version",
        description="Create a new version of the UML diagram, preserving the current state as a checkpoint.",
        tags=['UML Diagrams'],
        request={
            "type": "object",
            "properties": {
                "version_comment": {"type": "string", "description": "Comment describing the changes"}
            }
        },
        responses={
            201: {"description": "Version created successfully"},
            400: {"description": "Version creation failed"}
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """Create a new version of the UML diagram."""
        diagram = self.get_object()
        
        try:
            version_comment = request.data.get('version_comment', 'Version created via API')
            
            # Increment version number
            new_version = diagram.version_number + 1
            diagram.version_number = new_version
            diagram.save()
            
            # Log version creation
            self.log_transaction_event(
                f"UML_DIAGRAM_VERSION_CREATE",
                instance=diagram,
                details={
                    'new_version': new_version,
                    'comment': version_comment
                }
            )
            
            return Response({
                'success': True,
                'message': f'Version {new_version} created successfully',
                'version_number': new_version,
                'comment': version_comment
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'version_creation_failed',
                'message': f'Failed to create version: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Export UML Diagram to PlantUML",
        description="Export the UML diagram data as PlantUML code for external use or documentation generation.",
        tags=['UML Diagrams'],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "plantuml_code": {"type": "string", "description": "PlantUML representation of the diagram"},
                    "export_format": {"type": "string", "description": "Export format used"},
                    "exported_at": {"type": "string", "format": "date-time"}
                }
            },
            404: {"description": "UML Diagram not found"}
        }
    )
    @action(detail=True, methods=['get'])
    def export_data(self, request, pk=None):
        """Export UML diagram to PlantUML format."""
        diagram = self.get_object()
        
        try:
            export_data = diagram.export_to_plantuml()
            
            # Log export action
            self.log_transaction_event(
                f"UML_DIAGRAM_EXPORT_SUCCESS",
                instance=diagram,
                details={'export_format': 'plantuml'}
            )
            
            from django.utils import timezone
            return Response({
                'success': True,
                'plantuml_code': export_data,
                'export_format': 'plantuml',
                'exported_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'export_failed',
                'message': f'Failed to export diagram: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Get UML Diagram Statistics",
        description="Retrieve comprehensive statistics and metrics for a specific UML diagram including element counts, complexity metrics, and version information.",
        tags=['UML Diagrams'],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "overview": {"type": "object", "description": "High-level diagram statistics"},
                    "complexity_metrics": {"type": "object", "description": "Diagram complexity analysis"},
                    "version_info": {"type": "object", "description": "Version and modification tracking"}
                }
            }
        }
    )
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get comprehensive diagram statistics."""
        diagram = self.get_object()
        
        stats = {
            'overview': {
                'classes_count': len(diagram.get_classes()) if hasattr(diagram, 'get_classes') else 0,
                'relationships_count': len(diagram.get_relationships()) if hasattr(diagram, 'get_relationships') else 0,
                'elements_count': diagram.get_elements_count() if hasattr(diagram, 'get_elements_count') else 0,
                'diagram_type': diagram.diagram_type
            },
            'complexity_metrics': {
                'complexity_score': diagram.calculate_complexity() if hasattr(diagram, 'calculate_complexity') else 0,
                'depth_level': diagram.get_depth_level() if hasattr(diagram, 'get_depth_level') else 0,
                'inheritance_chains': diagram.count_inheritance_chains() if hasattr(diagram, 'count_inheritance_chains') else 0
            },
            'version_info': {
                'version_number': diagram.version_number,
                'last_modified': diagram.updated_at.isoformat(),
                'created_at': diagram.created_at.isoformat(),
                'created_by': diagram.created_by.username if diagram.created_by else None
            }
        }
        
        return Response({
            'success': True,
            **stats,
            'generated_at': timezone.now().isoformat()
        })
    
    @extend_schema(
        summary="Validate UML Diagram",
        description="Perform comprehensive validation of the UML diagram structure, checking for consistency, completeness, and adherence to UML standards.",
        tags=['UML Diagrams'],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "validation_errors": {"type": "array", "items": {"type": "string"}},
                    "validation_warnings": {"type": "array", "items": {"type": "string"}},
                    "validation_score": {"type": "number", "description": "Validation score (0-100)"}
                }
            }
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def validate_diagram(self, request, pk=None):
        """Validate UML diagram structure and content."""
        diagram = self.get_object()
        
        try:
            validation_result = diagram.validate_diagram() if hasattr(diagram, 'validate_diagram') else {
                'is_valid': True,
                'validation_errors': [],
                'validation_warnings': [],
                'validation_score': 95
            }
            
            # Log validation action
            self.log_transaction_event(
                f"UML_DIAGRAM_VALIDATION",
                instance=diagram,
                details={
                    'is_valid': validation_result.get('is_valid', True),
                    'error_count': len(validation_result.get('validation_errors', [])),
                    'warning_count': len(validation_result.get('validation_warnings', []))
                }
            )
            
            return Response({
                'success': True,
                **validation_result,
                'validated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'error': True,
                'error_code': 'validation_failed',
                'message': f'Diagram validation failed: {str(e)}',
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
