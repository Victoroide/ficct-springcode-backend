"""
Enterprise GenerationTemplate ViewSet for SpringBoot code generation template management.
Professional CRUD operations with atomic transactions, audit logging, and comprehensive validation.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.db import models, transaction
from django.utils import timezone
import json

from ..models import GenerationTemplate
from ..serializers import (
    GenerationTemplateSerializer,
    GenerationTemplateCreateSerializer,
    GenerationTemplateListSerializer,
    GenerationTemplateUpdateSerializer
)
from base.mixins.enterprise_transaction_mixins import EnterpriseViewSetMixin
from base.exceptions.enterprise_exceptions import EnterpriseExceptionHandler
from apps.audit.services.audit_service import AuditService
from base.swagger.enterprise_documentation import get_error_responses


@extend_schema_view(
    list=extend_schema(
        tags=["Code Generation - Templates"],
        summary="List Generation Templates",
        description="Retrieve a comprehensive list of SpringBoot code generation templates with advanced filtering, search capabilities, and enterprise security.",
        parameters=[
            OpenApiParameter(
                name='template_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by template type (ENTITY, CONTROLLER, SERVICE, etc.)"
            ),
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by template status (ACTIVE, INACTIVE, DEPRECATED)"
            ),
            OpenApiParameter(
                name='is_system_template',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by system/user templates"
            ),
            OpenApiParameter(
                name='created_by',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by creator user ID"
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in template name, description, and content"
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by: created_at, updated_at, name, usage_count, last_used_at"
            ),
        ],
        responses={
            200: GenerationTemplateListSerializer(many=True),
            **get_error_responses(['400', '401', '403'])
        }
    ),
    create=extend_schema(
        tags=["Code Generation - Templates"],
        summary="Create Generation Template",
        description="Create a new SpringBoot code generation template with enterprise validation and audit logging.",
        request=GenerationTemplateCreateSerializer,
        responses={
            201: GenerationTemplateSerializer,
            **get_error_responses(['400', '401', '403'])
        }
    ),
    retrieve=extend_schema(
        tags=["Code Generation - Templates"],
        summary="Get Template Details",
        description="Retrieve comprehensive information about a specific generation template with metadata and usage statistics.",
        responses={
            200: GenerationTemplateSerializer,
            **get_error_responses(['401', '403', '404'])
        }
    ),
    update=extend_schema(
        tags=["Code Generation - Templates"],
        summary="Update Generation Template",
        description="Update generation template content and configuration with enterprise validation and audit logging.",
        request=GenerationTemplateUpdateSerializer,
        responses={
            200: GenerationTemplateSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    partial_update=extend_schema(
        tags=["Code Generation - Templates"],
        summary="Partially Update Template",
        description="Perform partial updates on generation template with field-level validation.",
        request=GenerationTemplateUpdateSerializer,
        responses={
            200: GenerationTemplateSerializer,
            **get_error_responses(['400', '401', '403', '404'])
        }
    ),
    destroy=extend_schema(
        tags=["Code Generation - Templates"],
        summary="Delete Generation Template",
        description="Safely delete a generation template with validation, audit logging, and soft delete capabilities.",
        responses={
            204: {'description': 'Template deleted successfully'},
            **get_error_responses(['401', '403', '404'])
        }
    )
)
class GenerationTemplateViewSet(EnterpriseViewSetMixin, viewsets.ModelViewSet):
    """
    Enterprise ViewSet for managing SpringBoot code generation templates.
    
    Provides comprehensive CRUD operations, template validation, testing functionality,
    and lifecycle management with enterprise-grade security, audit logging, and transaction management.
    """
    
    serializer_class = GenerationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['template_type', 'is_system_template', 'created_by', 'is_active']
    search_fields = ['name', 'description', 'content', 'template_type']
    ordering_fields = ['created_at', 'updated_at', 'name', 'usage_count', 'last_used_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action with comprehensive mapping."""
        serializer_map = {
            'list': GenerationTemplateListSerializer,
            'create': GenerationTemplateCreateSerializer,
            'retrieve': GenerationTemplateSerializer,
            'update': GenerationTemplateUpdateSerializer,
            'partial_update': GenerationTemplateUpdateSerializer,
        }
        return serializer_map.get(self.action, GenerationTemplateSerializer)
    
    def get_queryset(self):
        """
        Filter queryset with enterprise security and performance optimizations.
        """
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return GenerationTemplate.objects.none()
        
        base_queryset = GenerationTemplate.objects.select_related(
            'created_by'
        ).prefetch_related(
            'generation_requests'  # For usage tracking
        )
        
        # Staff users have access to all templates
        if self.request.user.is_staff:
            return base_queryset
        
        # Regular users can only access system templates and their own templates
        return base_queryset.filter(
            models.Q(is_system_template=True) |
            models.Q(created_by=self.request.user)
        ).exclude(
            # Exclude soft deleted items
            status='DELETED'
        )
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create template with enterprise validation and audit logging."""
        try:
            instance = serializer.save(created_by=self.request.user)
            
            # Audit logging for creation
            AuditService.log_user_action(
                user=self.request.user,
                action='CREATE_TEMPLATE',
                resource_type='GENERATION_TEMPLATE',
                resource_id=instance.id,
                details={
                    'template_name': instance.name,
                    'template_type': instance.template_type,
                    'is_system_template': instance.is_system_template,
                    'content_length': len(instance.content or '')
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'CREATE_TEMPLATE', 'GENERATION_TEMPLATE')
            raise
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update template with validation and audit logging."""
        try:
            old_data = {
                'name': serializer.instance.name,
                'template_type': serializer.instance.template_type,
                'content': serializer.instance.content,
                'is_active': serializer.instance.is_active
            }
            
            instance = serializer.save()
            
            # Audit logging for update
            AuditService.log_user_action(
                user=self.request.user,
                action='UPDATE_TEMPLATE',
                resource_type='GENERATION_TEMPLATE',
                resource_id=instance.id,
                details={
                    'old_data': old_data,
                    'new_data': {
                        'name': instance.name,
                        'template_type': instance.template_type,
                        'content': instance.content,
                        'is_active': instance.is_active
                    }
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'UPDATE_TEMPLATE', 'GENERATION_TEMPLATE')
            raise
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Enterprise soft delete with comprehensive validation and audit logging.
        """
        try:
            # Validate user permissions for deletion
            if instance.is_system_template and not self.request.user.is_staff:
                raise ValidationError({
                    'error': 'SYSTEM_TEMPLATE_DELETE_DENIED',
                    'message': 'Cannot delete system templates',
                    'details': {'template_type': 'system', 'required_role': 'staff'}
                })
            
            if not self.request.user.is_staff and instance.created_by != self.request.user:
                raise ValidationError({
                    'error': 'TEMPLATE_DELETE_PERMISSION_DENIED',
                    'message': 'You do not have permission to delete this template'
                })
            
            # Store data for audit logging before deletion
            template_data = {
                'template_name': instance.name,
                'template_type': instance.template_type,
                'is_system_template': instance.is_system_template,
                'usage_count': instance.usage_count,
                'created_by': instance.created_by.username if instance.created_by else 'System'
            }
            
            # Perform soft delete by updating status
            instance.status = 'DELETED'
            instance.deleted_at = timezone.now()
            instance.is_active = False
            instance.save(update_fields=['status', 'deleted_at', 'is_active'])
            
            # Audit logging for deletion
            AuditService.log_user_action(
                user=self.request.user,
                action='DELETE_TEMPLATE',
                resource_type='GENERATION_TEMPLATE',
                resource_id=instance.id,
                details={
                    **template_data,
                    'deletion_timestamp': timezone.now().isoformat()
                }
            )
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, self.request.user, 'DELETE_TEMPLATE', 'GENERATION_TEMPLATE')
            raise
    
    @extend_schema(
        tags=["Code Generation - Templates"],
        summary="Validate Template Syntax",
        description="Validate template syntax and structure with comprehensive error checking and variable analysis.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'Template content to validate (Jinja2 syntax)'
                    },
                    'variables': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'type': {'type': 'string'},
                                'required': {'type': 'boolean'}
                            }
                        },
                        'description': 'Expected template variables with metadata'
                    }
                },
                'required': ['content'],
                'example': {
                    'content': 'Hello {{ name }}! Your age is {{ age }}.',
                    'variables': [
                        {'name': 'name', 'type': 'string', 'required': True},
                        {'name': 'age', 'type': 'integer', 'required': False}
                    ]
                }
            }
        },
        responses={
            200: {
                'description': 'Template validation results',
                'content': {
                    'application/json': {
                        'example': {
                            'is_valid': True,
                            'errors': [],
                            'warnings': ['Undeclared variables found: age'],
                            'variables_found': ['name', 'age'],
                            'validation_details': {
                                'syntax_valid': True,
                                'variable_analysis': {
                                    'declared_count': 1,
                                    'found_count': 2,
                                    'missing_count': 1
                                }
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '401'])
        }
    )
    @transaction.atomic
    @action(detail=False, methods=['post'])
    def validate_template(self, request):
        """Validate template content and syntax with enterprise validation and audit logging."""
        try:
            content = request.data.get('content', '')
            variables = request.data.get('variables', [])
            
            if not content:
                raise ValidationError({
                    'error': 'CONTENT_REQUIRED',
                    'message': 'Template content is required for validation'
                })
            
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "variables_found": [],
                "validation_details": {
                    "syntax_valid": False,
                    "content_length": len(content),
                    "variable_analysis": {}
                }
            }
            
            try:
                # Validate Jinja2 syntax
                from jinja2 import Template, meta, Environment, TemplateSyntaxError
                
                # Parse template to check syntax
                env = Environment()
                ast = env.parse(content)
                validation_result["validation_details"]["syntax_valid"] = True
                
                # Create template instance
                template = Template(content)
                
                # Extract variables from template
                variables_found = list(meta.find_undeclared_variables(ast))
                validation_result["variables_found"] = variables_found
                
                # Analyze variables
                declared_vars = [var.get('name', '') for var in variables if isinstance(var, dict)]
                missing_vars = [var for var in variables_found if var not in declared_vars]
                unused_vars = [var for var in declared_vars if var not in variables_found]
                
                validation_result["validation_details"]["variable_analysis"] = {
                    "declared_count": len(declared_vars),
                    "found_count": len(variables_found),
                    "missing_count": len(missing_vars),
                    "unused_count": len(unused_vars)
                }
                
                # Generate warnings for variable issues
                if missing_vars:
                    validation_result["warnings"].append(
                        f"Undeclared variables found: {', '.join(missing_vars)}"
                    )
                
                if unused_vars:
                    validation_result["warnings"].append(
                        f"Declared but unused variables: {', '.join(unused_vars)}"
                    )
                
                # Validate required variables
                required_vars = [var.get('name') for var in variables if var.get('required', False)]
                missing_required = [var for var in required_vars if var not in variables_found]
                
                if missing_required:
                    validation_result["errors"].append(
                        f"Required variables missing from template: {', '.join(missing_required)}"
                    )
                    validation_result["is_valid"] = False
                
            except TemplateSyntaxError as e:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Template syntax error: {str(e)}")
                validation_result["validation_details"]["syntax_valid"] = False
                
            except Exception as e:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Template validation error: {str(e)}")
            
            # Audit logging for validation
            AuditService.log_user_action(
                user=request.user,
                action='VALIDATE_TEMPLATE',
                resource_type='GENERATION_TEMPLATE',
                resource_id=None,
                details={
                    'content_length': len(content),
                    'is_valid': validation_result["is_valid"],
                    'errors_count': len(validation_result["errors"]),
                    'warnings_count': len(validation_result["warnings"]),
                    'variables_found': validation_result["variables_found"]
                }
            )
            
            return Response({
                'success': True,
                'data': validation_result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'VALIDATE_TEMPLATE', 'GENERATION_TEMPLATE')
            raise
    
    @extend_schema(
        tags=["Code Generation - Templates"],
        summary="Test Template Rendering",
        description="Test template rendering with sample data and comprehensive error handling and audit logging.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'test_data': {
                        'type': 'object',
                        'description': 'Sample data for template rendering test',
                        'example': {
                            'entity_name': 'User',
                            'package_name': 'com.example.demo',
                            'fields': [
                                {'name': 'id', 'type': 'Long'},
                                {'name': 'username', 'type': 'String'}
                            ]
                        }
                    }
                },
                'required': ['test_data']
            }
        },
        responses={
            200: {
                'description': 'Template rendering test results',
                'content': {
                    'application/json': {
                        'example': {
                            'rendered_content': 'public class User {\n    private Long id;\n    private String username;\n}',
                            'success': True,
                            'error': None,
                            'render_metadata': {
                                'template_name': 'Entity Template',
                                'render_time_ms': 15,
                                'content_length': 85
                            }
                        }
                    }
                }
            },
            **get_error_responses(['400', '401', '403', '404'])
        }
    )
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def test_render(self, request, pk=None):
        """Test template rendering with comprehensive validation and audit logging."""
        try:
            template = self.get_object()
            
            # Validate user permissions
            if not request.user.is_staff and template.created_by != request.user and not template.is_system_template:
                raise ValidationError({
                    'error': 'RENDER_PERMISSION_DENIED',
                    'message': 'You do not have permission to test render this template'
                })
            
            test_data = request.data.get('test_data', {})
            
            if not isinstance(test_data, dict):
                raise ValidationError({
                    'error': 'INVALID_TEST_DATA',
                    'message': 'Test data must be a valid JSON object'
                })
            
            start_time = timezone.now()
            
            try:
                # Attempt to render the template
                if hasattr(template, 'render'):
                    rendered_content = template.render(test_data)
                else:
                    # Fallback rendering using Jinja2
                    from jinja2 import Template
                    jinja_template = Template(template.content or '')
                    rendered_content = jinja_template.render(**test_data)
                
                end_time = timezone.now()
                render_duration = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
                
                # Update template usage statistics
                template.usage_count = (template.usage_count or 0) + 1
                template.last_used_at = timezone.now()
                template.save(update_fields=['usage_count', 'last_used_at'])
                
                # Audit logging for successful render test
                AuditService.log_user_action(
                    user=request.user,
                    action='TEST_RENDER_TEMPLATE',
                    resource_type='GENERATION_TEMPLATE',
                    resource_id=template.id,
                    details={
                        'template_name': template.name,
                        'success': True,
                        'render_time_ms': render_duration,
                        'content_length': len(rendered_content),
                        'test_data_keys': list(test_data.keys())
                    }
                )
                
                return Response({
                    'success': True,
                    'data': {
                        'rendered_content': rendered_content,
                        'success': True,
                        'error': None,
                        'render_metadata': {
                            'template_name': template.name,
                            'render_time_ms': int(render_duration),
                            'content_length': len(rendered_content),
                            'variables_used': list(test_data.keys())
                        }
                    }
                }, status=status.HTTP_200_OK)
                
            except Exception as render_error:
                # Audit logging for failed render test
                AuditService.log_user_action(
                    user=request.user,
                    action='TEST_RENDER_TEMPLATE_FAILED',
                    resource_type='GENERATION_TEMPLATE',
                    resource_id=template.id,
                    details={
                        'template_name': template.name,
                        'success': False,
                        'error': str(render_error),
                        'test_data_keys': list(test_data.keys())
                    }
                )
                
                return Response({
                    'success': True,
                    'data': {
                        'rendered_content': None,
                        'success': False,
                        'error': str(render_error),
                        'render_metadata': {
                            'template_name': template.name,
                            'error_type': type(render_error).__name__
                        }
                    }
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            EnterpriseExceptionHandler.handle_exception(e, request.user, 'TEST_RENDER_TEMPLATE', 'GENERATION_TEMPLATE')
            raise
    
    @extend_schema(
        summary="Clone template",
        description="Create a copy of an existing template.",
        tags=["Code Generation Templates"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the cloned template"}
                }
            }
        },
        responses={
            201: GenerationTemplateSerializer,
            400: {"description": "Invalid clone data"}
        }
    )
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone an existing template."""
        source_template = self.get_object()
        clone_name = request.data.get('name', f"{source_template.name} (Copy)")
        
        cloned_template = GenerationTemplate.objects.create(
            name=clone_name,
            description=f"Cloned from: {source_template.name}",
            template_type=source_template.template_type,
            file_path=source_template.file_path,
            content=source_template.content,
            variables=source_template.variables.copy(),
            default_values=source_template.default_values.copy(),
            validation_schema=source_template.validation_schema.copy() if source_template.validation_schema else None,
            created_by=request.user,
            is_system_template=False
        )
        
        serializer = self.get_serializer(cloned_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Get template usage statistics",
        description="Get comprehensive usage statistics for templates.",
        tags=["Code Generation Templates"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_templates": {"type": "integer"},
                    "system_templates": {"type": "integer"},
                    "user_templates": {"type": "integer"},
                    "active_templates": {"type": "integer"},
                    "most_used_templates": {"type": "array"},
                    "template_type_distribution": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get template usage statistics."""
        queryset = self.get_queryset()
        
        stats = {
            "total_templates": queryset.count(),
            "system_templates": queryset.filter(is_system_template=True).count(),
            "user_templates": queryset.filter(is_system_template=False).count(),
            "active_templates": queryset.filter(is_active=True).count(),
        }
        
        # Most used templates
        most_used = queryset.filter(usage_count__gt=0).order_by('-usage_count')[:5]
        stats["most_used_templates"] = [
            {
                "id": str(template.id),
                "name": template.name,
                "usage_count": template.usage_count,
                "template_type": template.template_type
            }
            for template in most_used
        ]
        
        # Template type distribution
        from django.db.models import Count
        type_distribution = queryset.values('template_type').annotate(count=Count('id'))
        stats["template_type_distribution"] = {
            item['template_type']: item['count'] 
            for item in type_distribution
        }
        
        return Response(stats)
    
    @extend_schema(
        summary="Export templates",
        description="Export templates as JSON for backup or sharing.",
        tags=["Code Generation Templates"],
        parameters=[
            OpenApiParameter("template_ids", OpenApiTypes.STR, description="Comma-separated template IDs to export"),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "templates": {"type": "array"},
                    "export_metadata": {"type": "object"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export templates as JSON."""
        template_ids = request.query_params.get('template_ids', '').split(',')
        template_ids = [tid.strip() for tid in template_ids if tid.strip()]
        
        queryset = self.get_queryset()
        
        if template_ids:
            queryset = queryset.filter(id__in=template_ids)
        
        # Only allow exporting user templates (not system templates)
        if not request.user.is_staff:
            queryset = queryset.filter(is_system_template=False)
        
        templates_data = []
        for template in queryset:
            templates_data.append({
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "file_path": template.file_path,
                "content": template.content,
                "variables": template.variables,
                "default_values": template.default_values,
                "validation_schema": template.validation_schema
            })
        
        export_data = {
            "templates": templates_data,
            "export_metadata": {
                "exported_by": request.user.username,
                "exported_at": timezone.now().isoformat(),
                "template_count": len(templates_data),
                "version": "1.0"
            }
        }
        
        return Response(export_data)
    
    @extend_schema(
        summary="Import templates",
        description="Import templates from JSON data.",
        tags=["Code Generation Templates"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "templates": {"type": "array", "description": "Array of template data"},
                    "overwrite_existing": {"type": "boolean", "description": "Whether to overwrite existing templates"}
                }
            }
        },
        responses={
            201: {
                "type": "object",
                "properties": {
                    "imported_count": {"type": "integer"},
                    "skipped_count": {"type": "integer"},
                    "errors": {"type": "array"}
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def import_templates(self, request):
        """Import templates from JSON data."""
        templates_data = request.data.get('templates', [])
        overwrite_existing = request.data.get('overwrite_existing', False)
        
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for template_data in templates_data:
            try:
                name = template_data.get('name')
                existing = GenerationTemplate.objects.filter(
                    name=name, created_by=request.user
                ).first()
                
                if existing and not overwrite_existing:
                    skipped_count += 1
                    continue
                
                if existing and overwrite_existing:
                    # Update existing template
                    for field in ['description', 'template_type', 'file_path', 
                                 'content', 'variables', 'default_values', 'validation_schema']:
                        if field in template_data:
                            setattr(existing, field, template_data[field])
                    existing.save()
                    imported_count += 1
                else:
                    # Create new template
                    GenerationTemplate.objects.create(
                        name=name,
                        description=template_data.get('description', ''),
                        template_type=template_data.get('template_type', 'CUSTOM'),
                        file_path=template_data.get('file_path', ''),
                        content=template_data.get('content', ''),
                        variables=template_data.get('variables', []),
                        default_values=template_data.get('default_values', {}),
                        validation_schema=template_data.get('validation_schema'),
                        created_by=request.user,
                        is_system_template=False
                    )
                    imported_count += 1
                    
            except Exception as e:
                errors.append(f"Error importing template '{template_data.get('name', 'Unknown')}': {str(e)}")
        
        return Response({
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "errors": errors
        }, status=status.HTTP_201_CREATED)
