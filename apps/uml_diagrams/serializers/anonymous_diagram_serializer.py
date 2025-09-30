from rest_framework import serializers
from django.utils import timezone
from ..models import UMLDiagram
import uuid
import random

class AnonymousDiagramListSerializer(serializers.ModelSerializer):
    active_sessions_count = serializers.SerializerMethodField()
    time_since_modified = serializers.SerializerMethodField()

    
    class Meta:
        model = UMLDiagram
        fields = [
            'id',
            'title', 
            'description',
            'diagram_type',
            'created_at',
            'last_modified',
            'active_sessions_count',
            'time_since_modified'
        ]
        read_only_fields = ['id', 'created_at', 'last_modified']
    
    def get_active_sessions_count(self, obj) -> int:
        return obj.get_active_sessions_count()
    
    def get_time_since_modified(self, obj) -> str:
        delta = timezone.now() - obj.last_modified
        if delta.days > 0:
            return f"{delta.days} days ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hours ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"

class AnonymousDiagramDetailSerializer(serializers.ModelSerializer):    
    active_sessions = serializers.JSONField(read_only=True)
    active_sessions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UMLDiagram
        fields = [
            'id',
            'title',
            'description', 
            'diagram_type',
            'content',
            'layout_config',
            'created_at',
            'last_modified',
            'session_id',
            'active_sessions',
            'active_sessions_count'
        ]
        read_only_fields = ['id', 'created_at', 'last_modified', 'session_id']
    
    def get_active_sessions_count(self, obj) -> int:
        return obj.get_active_sessions_count()

class AnonymousDiagramCreateSerializer(serializers.ModelSerializer):    
    diagram_type = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = UMLDiagram
        fields = [
            'id',
            'title',
            'description',
            'diagram_type',
            'content',
            'layout_config',
            'created_at',
            'last_modified'
        ]
        read_only_fields = ['id', 'created_at', 'last_modified']
    
    def validate_diagram_type(self, value):
        if not value:
            return UMLDiagram.DiagramType.CLASS
        
        normalized = UMLDiagram.normalize_diagram_type(value)
        return normalized
    
    def validate(self, attrs):
        if 'content' not in attrs or not attrs['content']:
            attrs['content'] = {}
        
        if 'layout_config' not in attrs or not attrs['layout_config']:
            attrs['layout_config'] = {}
        
        if not attrs.get('title', '').strip():
            attrs['title'] = f"Anonymous Diagram {attrs.get('diagram_type', 'CLASS')}"
        
        return attrs
    
    def create(self, validated_data):
        import logging
        logger = logging.getLogger('django')
        request = self.context.get('request')
        
        session_id = self.get_or_create_session_id(request)
        
        diagram = UMLDiagram.objects.create(
            session_id=session_id,
            **validated_data
        )
        
        return diagram
    
    def get_or_create_session_id(self, request) -> str:
        if request and hasattr(request, 'session'):
            session_id = request.session.get('diagram_session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                request.session['diagram_session_id'] = session_id
                request.session.save()
            return session_id
        else:
            return str(uuid.uuid4())

class AnonymousDiagramUpdateSerializer(serializers.ModelSerializer):    
    class Meta:
        model = UMLDiagram
        fields = [
            'title',
            'description',
            'content',
            'layout_config'
        ]
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        
        if request and hasattr(request, 'session'):
            session_id = self.get_or_create_session_id(request)
            instance.session_id = session_id
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
    
    def get_or_create_session_id(self, request) -> str:
        session_id = request.session.get('diagram_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['diagram_session_id'] = session_id
            request.session.save()
        return session_id

class DiagramStatsSerializer(serializers.Serializer):
    total_diagrams = serializers.IntegerField()
    diagrams_today = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    most_popular_type = serializers.CharField()
    
    def to_representation(self, instance):
        from django.db.models import Count
        from datetime import datetime, timedelta
        
        today = timezone.now().date()
        
        total_diagrams = UMLDiagram.objects.count()
        diagrams_today = UMLDiagram.objects.filter(
            created_at__date=today
        ).count()
        
        active_sessions = 0
        for diagram in UMLDiagram.objects.all():
            active_sessions += diagram.get_active_sessions_count()
        
        popular_type = UMLDiagram.objects.values('diagram_type') \
            .annotate(count=Count('diagram_type')) \
            .order_by('-count') \
            .first()
        
        most_popular_type = popular_type['diagram_type'] if popular_type else 'CLASS'
        
        return {
            'total_diagrams': total_diagrams,
            'diagrams_today': diagrams_today,
            'active_sessions': active_sessions,
            'most_popular_type': most_popular_type
        }


class PlantUMLExportSerializer(serializers.Serializer):    
    plantuml_code = serializers.CharField(read_only=True)
    diagram_title = serializers.CharField(read_only=True)
    exported_at = serializers.DateTimeField(read_only=True)
    
    def to_representation(self, diagram):
        return {
            'plantuml_code': diagram.export_to_plantuml(),
            'diagram_title': diagram.title,
            'exported_at': timezone.now()
        }
