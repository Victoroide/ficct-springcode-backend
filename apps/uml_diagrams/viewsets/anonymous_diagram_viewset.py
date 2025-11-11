"""
Anonymous UML Diagram ViewSet for session-based collaboration.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.utils import timezone
from base.swagger.anonymous_documentation import AnonymousDocumentation, UML_DIAGRAMS_SCHEMA
from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models import UMLDiagram
from ..serializers.anonymous_diagram_serializer import (
    AnonymousDiagramListSerializer,
    AnonymousDiagramDetailSerializer,
    AnonymousDiagramCreateSerializer,
    AnonymousDiagramUpdateSerializer,
    DiagramStatsSerializer,
    PlantUMLExportSerializer
)


@extend_schema_view(**UML_DIAGRAMS_SCHEMA)
class AnonymousDiagramViewSet(viewsets.ModelViewSet):
    
    queryset = UMLDiagram.objects.all()
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    throttle_scope = 'anon'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AnonymousDiagramListSerializer
        elif self.action == 'create':
            return AnonymousDiagramCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AnonymousDiagramUpdateSerializer
        else:
            return AnonymousDiagramDetailSerializer
    
    def get_queryset(self):
        queryset = UMLDiagram.objects.all()

        diagram_type = self.request.query_params.get('type')
        if diagram_type:
            queryset = queryset.filter(diagram_type=diagram_type)

        my_diagrams = self.request.query_params.get('my_diagrams')
        if my_diagrams and hasattr(self.request, 'session'):
            session_id = self.request.session.get('diagram_session_id')
            if session_id:
                queryset = queryset.filter(session_id=session_id)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        return queryset.order_by('-last_modified')
    
    def perform_create(self, serializer):
        import logging
        logger = logging.getLogger('django')

        instance = serializer.save()
        
        return instance
    
    def partial_update(self, request, *args, **kwargs):
        """PATCH /api/diagrams/{id}/ - Auto-save endpoint"""
        import logging
        import json
        logger = logging.getLogger('django')
        
        diagram = self.get_object()

        if 'content' in request.data:
            try:

                if isinstance(request.data['content'], dict):
                    diagram.content = json.dumps(request.data['content'])
                elif isinstance(request.data['content'], str):
                    try:

                        json.loads(request.data['content'])
                    except json.JSONDecodeError:
                        pass

                    diagram.content = request.data['content']
                else:
                    diagram.content = str(request.data['content'])
            except Exception as e:
                pass
        if 'title' in request.data:
            original_title = diagram.title
            diagram.title = request.data['title']

        serializer = self.get_serializer(diagram, data=request.data, partial=True)
        
        if serializer.is_valid():

            instance = serializer.save()

            from django.utils import timezone
            instance.last_modified = timezone.now()
            instance.save(update_fields=['last_modified'])
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """PUT /api/diagrams/{id}/ - Full update endpoint"""
        import logging
        logger = logging.getLogger('django')
        
        diagram = self.get_object()
        serializer = self.get_serializer(diagram, data=request.data)
        
        if serializer.is_valid():
            instance = serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def perform_update(self, serializer):
        serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        diagram = self.get_object()

        current_session = request.session.get('diagram_session_id')
        if current_session and diagram.session_id == current_session:
            diagram.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {'detail': 'You can only delete diagrams you created.'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    @AnonymousDocumentation.get_statistics_schema(resource_name='UML Diagram', tag_name='UML Diagrams')
    @action(detail=False, methods=['get'])
    def stats(self, request):
        serializer = DiagramStatsSerializer(data={})
        serializer.is_valid()
        return Response(serializer.data)
    
    @AnonymousDocumentation.get_custom_action_schema(
        action_name='export_to_plantuml',
        resource_name='UML Diagram',
        tag_name='UML Diagrams',
        description='Export diagram to PlantUML format for professional documentation',
        method='get',
        response_serializer=PlantUMLExportSerializer
    )
    @action(detail=True, methods=['get'])
    def export_plantuml(self, request, pk=None):
        diagram = self.get_object()
        serializer = PlantUMLExportSerializer(diagram)
        return Response(serializer.data)
    
    @AnonymousDocumentation.get_custom_action_schema(
        action_name='clone',
        resource_name='UML Diagram',
        tag_name='UML Diagrams',
        description='Create a copy of existing diagram for your current anonymous session',
        method='post',
        response_serializer=AnonymousDiagramDetailSerializer
    )
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        import uuid
        diagram = self.get_object()

        session_id = request.session.get('diagram_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['diagram_session_id'] = session_id
            request.session.save()

        new_title = request.data.get('title', f"Copy of {diagram.title}")
        clone = diagram.clone_diagram(session_id, new_title)

        serializer = AnonymousDiagramDetailSerializer(clone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary='Join collaboration session',
        description='Join diagram collaboration session for real-time editing'
    )
    @action(detail=True, methods=['post'])
    def join_session(self, request, pk=None):
        diagram = self.get_object()

        session_id = request.session.get('diagram_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['diagram_session_id'] = session_id
            request.session.save()

        nickname = request.data.get('nickname')
        if not nickname:
            import random
            nickname = f"Guest_{random.randint(1000, 9999)}"

        diagram.add_active_session(session_id, nickname)
        
        return Response({
            'session_id': session_id,
            'nickname': nickname,
            'active_sessions': diagram.active_sessions,
            'websocket_url': f'/ws/diagram/{diagram.id}/'
        })
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary='Leave collaboration session',
        description='Leave diagram collaboration session'
    )
    @action(detail=True, methods=['post'])
    def leave_session(self, request, pk=None):
        diagram = self.get_object()
        
        session_id = request.session.get('diagram_session_id')
        if session_id:
            diagram.remove_active_session(session_id)
        
        return Response({'status': 'left_session'})
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary='Get recent diagrams',
        description='Get recently modified diagrams'
    )
    @action(detail=False, methods=['get'])
    def recent(self, request):
        limit = int(request.query_params.get('limit', 10))
        diagrams = UMLDiagram.get_recent_diagrams(limit)
        serializer = AnonymousDiagramListSerializer(diagrams, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        tags=['UML Diagrams'],
        summary='Get my diagrams',
        description='Get diagrams created by current session'
    )
    @action(detail=False, methods=['get']) 
    def my_diagrams(self, request):
        session_id = request.session.get('diagram_session_id')
        if not session_id:
            return Response([])
        
        diagrams = UMLDiagram.get_session_diagrams(session_id)
        serializer = AnonymousDiagramListSerializer(diagrams, many=True)
        return Response(serializer.data)
