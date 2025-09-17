from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from base.swagger.enterprise_documentation import (
    CRUD_DOCUMENTATION, 
    get_custom_action_documentation,
    get_error_responses
)
from apps.audit.services import AuditService
from ..models import UMLRelationship
from ..serializers import (
    UMLRelationshipListSerializer,
    UMLRelationshipDetailSerializer,
    UMLRelationshipCreateSerializer
)


@extend_schema_view(
    list=extend_schema(
        tags=['UML Diagrams'],
        summary="List UML Relationships",
        description="Retrieve a paginated list of UML relationships with advanced filtering, ordering, and search capabilities.",
        parameters=[
            OpenApiParameter(
                name='relationship_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by relationship type (association, inheritance, composition, aggregation, dependency, realization)"
            ),
            OpenApiParameter(
                name='diagram',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by diagram ID"
            ),
            OpenApiParameter(
                name='source_element',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by source element ID"
            ),
            OpenApiParameter(
                name='target_element',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by target element ID"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in relationship names and descriptions"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: created_at, updated_at, relationship_type (prefix with '-' for descending)"
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by status (ACTIVE, DELETED)"
            ),
        ],
        responses=CRUD_DOCUMENTATION['list']['responses']
    ),
    create=extend_schema(
        tags=['UML Diagrams'],
        summary="Create UML Relationship",
        description="Create a new UML relationship between two elements with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['create']['responses']
    ),
    retrieve=extend_schema(
        tags=['UML Diagrams'],
        summary="Retrieve UML Relationship",
        description="Retrieve detailed information about a specific UML relationship including connection path data.",
        responses=CRUD_DOCUMENTATION['retrieve']['responses']
    ),
    update=extend_schema(
        tags=['UML Diagrams'],
        summary="Update UML Relationship",
        description="Update UML relationship properties with validation and audit logging. Use PATCH for partial updates.",
        responses=CRUD_DOCUMENTATION['update']['responses']
    ),
    partial_update=extend_schema(
        tags=['UML Diagrams'],
        summary="Partially Update UML Relationship",
        description="Partially update UML relationship properties with validation and audit logging.",
        responses=CRUD_DOCUMENTATION['partial_update']['responses']
    ),
    destroy=extend_schema(
        tags=['UML Diagrams'],
        summary="Delete UML Relationship",
        description="Soft delete a UML relationship with audit logging. The relationship will be marked as deleted but preserved for audit purposes.",
        responses=CRUD_DOCUMENTATION['destroy']['responses']
    )
)
class UMLRelationshipViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for UML Relationship management with atomic transactions,
    soft delete support, comprehensive filtering, and audit logging.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['relationship_type', 'diagram', 'source_class', 'target_class']
    ordering_fields = ['created_at', 'updated_at', 'relationship_type']
    ordering = ['-created_at']
    search_fields = ['name', 'description', 'relationship_type']
    
    def get_queryset(self):
        """
        Enhanced queryset with optimized database queries and soft delete support.
        """
        if getattr(self, 'swagger_fake_view', False):
            return UMLRelationship.objects.none()
        
        queryset = UMLRelationship.objects.filter(
            diagram__project__workspace__owner=self.request.user
        ).select_related(
            'diagram', 
            'source_element', 
            'target_element', 
            'created_by',
            'updated_by'
        ).prefetch_related(
            'diagram__project',
            'source_element__diagram',
            'target_element__diagram'
        )
        
        # Apply soft delete filter - only show active relationships by default
        if self.action != 'list' or self.request.query_params.get('status') != 'DELETED':
            queryset = queryset.exclude(status='DELETED')
        
        return queryset
    
    def get_serializer_class(self):
        """
        Dynamic serializer class selection based on action.
        """
        if self.action == 'list':
            return UMLRelationshipListSerializer
        elif self.action == 'create':
            return UMLRelationshipCreateSerializer
        return UMLRelationshipDetailSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Enhanced creation with audit logging and validation.
        """
        try:
            # Validate relationship doesn't create cycles or invalid connections
            source_element = serializer.validated_data.get('source_element')
            target_element = serializer.validated_data.get('target_element')
            
            if source_element == target_element:
                raise ValidationError({
                    'error': 'INVALID_RELATIONSHIP',
                    'message': 'A relationship cannot connect an element to itself',
                    'details': {'source_element': source_element.id}
                })
            
            if source_element.diagram != target_element.diagram:
                raise ValidationError({
                    'error': 'CROSS_DIAGRAM_RELATIONSHIP',
                    'message': 'Relationships can only be created between elements in the same diagram',
                    'details': {
                        'source_diagram': source_element.diagram.id,
                        'target_diagram': target_element.diagram.id
                    }
                })
            
            relationship = serializer.save(
                created_by=self.request.user,
                updated_by=self.request.user
            )
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE',
                resource_type='UML_RELATIONSHIP',
                resource_id=relationship.id,
                details={
                    'relationship_type': relationship.relationship_type,
                    'source_element_id': relationship.source_element.id,
                    'target_element_id': relationship.target_element.id,
                    'diagram_id': relationship.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE', 'UML_RELATIONSHIP')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """
        Enhanced update with audit logging and validation.
        """
        try:
            original_data = {
                'relationship_type': serializer.instance.relationship_type,
                'name': serializer.instance.name,
                'description': serializer.instance.description
            }
            
            relationship = serializer.save(updated_by=self.request.user)
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE',
                resource_type='UML_RELATIONSHIP',
                resource_id=relationship.id,
                details={
                    'original_data': original_data,
                    'updated_data': serializer.validated_data,
                    'diagram_id': relationship.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE', 'UML_RELATIONSHIP')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Soft delete implementation with audit logging.
        """
        try:
            # Soft delete
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.updated_by = self.request.user
            instance.save(update_fields=['status', 'deleted_at', 'updated_by'])
            
            # Audit logging
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE',
                resource_type='UML_RELATIONSHIP',
                resource_id=instance.id,
                details={
                    'relationship_type': instance.relationship_type,
                    'source_element_id': instance.source_element.id,
                    'target_element_id': instance.target_element.id,
                    'diagram_id': instance.diagram.id
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE', 'UML_RELATIONSHIP')
            raise
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary="Get Connection Path",
        description="Calculate and retrieve the visual connection path between source and target elements for rendering.",
        responses={
            200: {
                'description': 'Connection path data',
                'content': {
                    'application/json': {
                        'example': {
                            'path': [
                                {'x': 100, 'y': 150},
                                {'x': 200, 'y': 150},
                                {'x': 200, 'y': 250},
                                {'x': 300, 'y': 250}
                            ],
                            'arrow_position': {'x': 300, 'y': 250, 'angle': 0},
                            'label_position': {'x': 200, 'y': 200}
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @action(detail=True, methods=['get'])
    def connection_path(self, request, pk=None):
        """
        Calculate the optimal connection path between elements for visual rendering.
        """
        try:
            relationship = self.get_object()
            path = relationship.calculate_connection_path()
            
            # Audit logging for data access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW',
                resource_type='UML_RELATIONSHIP_PATH',
                resource_id=relationship.id,
                details={
                    'diagram_id': relationship.diagram.id,
                    'path_points': len(path.get('path', []))
                }
            )
            
            return Response({
                'success': True,
                'data': path,
                'message': 'Connection path calculated successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW', 'UML_RELATIONSHIP_PATH')
            raise
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary="Get Label Position",
        description="Calculate the optimal position for the relationship label based on the connection path.",
        responses={
            200: {
                'description': 'Label position data',
                'content': {
                    'application/json': {
                        'example': {
                            'position': {'x': 200, 'y': 175},
                            'rotation': 15,
                            'alignment': 'center'
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @action(detail=True, methods=['get'])
    def label_position(self, request, pk=None):
        """
        Calculate the optimal label position for the relationship.
        """
        try:
            relationship = self.get_object()
            position = relationship.get_label_position()
            
            # Audit logging for data access
            AuditService.log_user_action(
                user=request.user,
                action='VIEW',
                resource_type='UML_RELATIONSHIP_LABEL',
                resource_id=relationship.id,
                details={
                    'diagram_id': relationship.diagram.id,
                    'position': position
                }
            )
            
            return Response({
                'success': True,
                'data': position,
                'message': 'Label position calculated successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VIEW', 'UML_RELATIONSHIP_LABEL')
            raise
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary="Validate Relationship",
        description="Validate relationship configuration and check for potential issues or conflicts.",
        responses={
            200: {
                'description': 'Validation results',
                'content': {
                    'application/json': {
                        'example': {
                            'is_valid': True,
                            'warnings': [],
                            'errors': [],
                            'suggestions': [
                                'Consider adding a more descriptive name',
                                'Verify the relationship type matches your design intent'
                            ]
                        }
                    }
                }
            },
            **get_error_responses(['400', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def validate_relationship(self, request, pk=None):
        """
        Validate the relationship configuration and provide feedback.
        """
        try:
            relationship = self.get_object()
            
            validation_results = {
                'is_valid': True,
                'warnings': [],
                'errors': [],
                'suggestions': []
            }
            
            # Check for circular dependencies
            if relationship.relationship_type == 'inheritance':
                # TODO: Implement inheritance chain validation
                pass
            
            # Check for naming consistency
            if not relationship.name or len(relationship.name.strip()) < 3:
                validation_results['suggestions'].append(
                    'Consider providing a more descriptive name for better documentation'
                )
            
            # Check element compatibility
            source_type = relationship.source_element.element_type
            target_type = relationship.target_element.element_type
            rel_type = relationship.relationship_type
            
            # Basic compatibility checks
            incompatible_combinations = [
                ('use_case', 'class', ['inheritance', 'composition']),
                ('actor', 'class', ['composition', 'aggregation'])
            ]
            
            for src, tgt, invalid_rels in incompatible_combinations:
                if source_type == src and target_type == tgt and rel_type in invalid_rels:
                    validation_results['warnings'].append(
                        f'{rel_type.title()} relationship between {src} and {tgt} may not be semantically correct'
                    )
            
            # Audit logging
            AuditService.log_user_action(
                user=request.user,
                action='VALIDATE',
                resource_type='UML_RELATIONSHIP',
                resource_id=relationship.id,
                details={
                    'validation_results': validation_results,
                    'diagram_id': relationship.diagram.id
                }
            )
            
            return Response({
                'success': True,
                'data': validation_results,
                'message': 'Relationship validation completed'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VALIDATE', 'UML_RELATIONSHIP')
            raise
