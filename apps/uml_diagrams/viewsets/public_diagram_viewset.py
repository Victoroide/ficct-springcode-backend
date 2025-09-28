"""
Public ViewSet for UML Diagrams.

Provides public access to diagrams without authentication using UUID.
Supports read and edit operations for public diagrams.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from ..models import UMLDiagram
from ..serializers import UMLDiagramSerializer, UMLDiagramPublicSerializer
from apps.audit.services.audit_service import AuditService


class PublicDiagramRateThrottle(AnonRateThrottle):
    """Custom rate throttling for public diagram access."""
    scope = 'public_diagram'
    rate = '30/min'


@extend_schema_view(
    retrieve=extend_schema(
        tags=['Public Access'],
        summary='Get public diagram by UUID',
        description='Retrieve a public UML diagram using its public edit URL without authentication.',
    ),
    update=extend_schema(
        tags=['Public Access'],
        summary='Update public diagram',
        description='Update a public UML diagram without authentication using its public edit URL.',
    ),
    partial_update=extend_schema(
        tags=['Public Access'],
        summary='Partially update public diagram',
        description='Partially update a public UML diagram without authentication.',
    ),
)
class PublicDiagramViewSet(viewsets.ModelViewSet):
    """
    Public ViewSet for UML Diagrams.
    
    Provides public access to diagrams without authentication.
    Uses public_edit_url UUID for access control.
    
    Features:
    - GET /api/public/diagrams/<uuid>/ - Read diagram
    - PUT /api/public/diagrams/<uuid>/ - Update diagram
    - PATCH /api/public/diagrams/<uuid>/ - Partial update
    - Rate limiting for anonymous users
    - Audit logging for public access
    """
    
    serializer_class = UMLDiagramPublicSerializer
    permission_classes = [AllowAny]
    throttle_classes = [PublicDiagramRateThrottle]
    lookup_field = 'public_edit_url'
    lookup_url_kwarg = 'uuid'
    
    def get_queryset(self):
        """Get only public diagrams."""
        return UMLDiagram.objects.filter(is_public=True)
    
    def get_object(self):
        """Get diagram by public_edit_url UUID."""
        uuid = self.kwargs.get(self.lookup_url_kwarg)
        
        try:
            diagram = UMLDiagram.objects.get(
                public_edit_url=uuid,
                is_public=True
            )
            
            # Log public access
            AuditService.log_anonymous_action(
                action_type='PUBLIC_DIAGRAM_ACCESS',
                resource_type='UMLDiagram',
                resource_id=diagram.id,
                ip_address=self.get_client_ip(),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'public_uuid': str(uuid),
                    'diagram_name': diagram.name,
                    'action': self.action
                }
            )
            
            return diagram
            
        except UMLDiagram.DoesNotExist:
            raise Http404("Public diagram not found or not accessible")
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve public diagram."""
        diagram = self.get_object()
        serializer = self.get_serializer(diagram)
        
        # Add public access metadata
        data = serializer.data
        data['public_access'] = {
            'is_public': True,
            'public_url': str(diagram.public_edit_url),
            'access_time': timezone.now().isoformat(),
            'can_edit': True
        }
        
        return Response(data)
    
    def update(self, request, *args, **kwargs):
        """Update public diagram."""
        partial = kwargs.pop('partial', False)
        diagram = self.get_object()
        
        # Validate anti-spam measures
        if not self._validate_update_request(request):
            return Response(
                {'error': 'Update request rejected - potential spam'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        serializer = self.get_serializer(diagram, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Update diagram
        serializer.save(
            last_modified_by=None,  # Anonymous update
            updated_at=timezone.now()
        )
        
        # Log public update
        AuditService.log_anonymous_action(
            action_type='PUBLIC_DIAGRAM_UPDATE',
            resource_type='UMLDiagram',
            resource_id=diagram.id,
            ip_address=self.get_client_ip(),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={
                'public_uuid': str(diagram.public_edit_url),
                'diagram_name': diagram.name,
                'version': diagram.version_number,
                'changes': list(request.data.keys()) if hasattr(request.data, 'keys') else []
            }
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update public diagram."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Public Access'],
        summary='Get diagram version history',
        description='Get version history for public diagram.',
    )
    @action(detail=True, methods=['get'])
    def versions(self, request, uuid=None):
        """Get diagram version history."""
        diagram = self.get_object()
        versions = diagram.versions.all()[:10]  # Last 10 versions
        
        version_data = []
        for version in versions:
            version_data.append({
                'version_number': version.version_number,
                'created_at': version.created_at.isoformat(),
                'change_summary': version.change_summary,
                'is_major_version': version.is_major_version,
                'tag': version.tag
            })
        
        return Response({
            'diagram_id': str(diagram.id),
            'current_version': diagram.version_number,
            'versions': version_data
        })
    
    @extend_schema(
        tags=['Public Access'],
        summary='Export diagram to PlantUML',
        description='Export public diagram to PlantUML format.',
    )
    @action(detail=True, methods=['get'])
    def export_plantuml(self, request, uuid=None):
        """Export diagram to PlantUML format."""
        diagram = self.get_object()
        
        try:
            plantuml_content = diagram.export_to_plantuml()
            
            # Log export
            AuditService.log_anonymous_action(
                action_type='PUBLIC_DIAGRAM_EXPORT',
                resource_type='UMLDiagram',
                resource_id=diagram.id,
                ip_address=self.get_client_ip(),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'export_format': 'plantuml',
                    'diagram_name': diagram.name
                }
            )
            
            return Response({
                'diagram_name': diagram.name,
                'format': 'plantuml',
                'content': plantuml_content,
                'exported_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        tags=['Public Access'],
        summary='Get diagram statistics',
        description='Get public statistics about the diagram.',
    )
    @action(detail=True, methods=['get'])
    def stats(self, request, uuid=None):
        """Get diagram statistics."""
        diagram = self.get_object()
        
        # Calculate diagram statistics
        classes_count = len(diagram.get_classes())
        relationships_count = len(diagram.get_relationships())
        
        return Response({
            'diagram_id': str(diagram.id),
            'name': diagram.name,
            'diagram_type': diagram.get_diagram_type_display(),
            'version': diagram.version_number,
            'created_at': diagram.created_at.isoformat(),
            'updated_at': diagram.updated_at.isoformat(),
            'statistics': {
                'classes_count': classes_count,
                'relationships_count': relationships_count,
                'total_elements': classes_count + relationships_count
            },
            'public_access': {
                'is_public': diagram.is_public,
                'visibility': diagram.get_visibility_display()
            }
        })
    
    # Helper methods
    def get_client_ip(self):
        """Get client IP address."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def _validate_update_request(self, request):
        """Validate update request for anti-spam measures."""
        # Basic validation - can be extended with more sophisticated checks
        
        # Check content length
        if hasattr(request.data, '__len__') and len(str(request.data)) > 50000:  # 50KB limit
            return False
        
        # Check for suspicious patterns
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        suspicious_agents = ['bot', 'crawler', 'spider', 'scraper']
        
        if any(agent in user_agent for agent in suspicious_agents):
            return False
        
        return True
