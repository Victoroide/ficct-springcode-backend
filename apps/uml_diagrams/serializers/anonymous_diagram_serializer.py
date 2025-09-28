"""
Anonymous UML Diagram serializers for session-based collaboration.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models import UMLDiagram
import uuid
import random


class AnonymousDiagramListSerializer(serializers.ModelSerializer):
    """Serializer for listing diagrams anonymously."""
    
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
        """Get count of active sessions."""
        return obj.get_active_sessions_count()
    
    def get_time_since_modified(self, obj) -> str:
        """Get human-readable time since last modification."""
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
    """Serializer for detailed diagram view with full content."""
    
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
        """Get count of active sessions."""
        return obj.get_active_sessions_count()


class AnonymousDiagramCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new diagrams anonymously with flexible validation."""
    
    # Override diagram_type field to allow case-insensitive input
    diagram_type = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = UMLDiagram
        fields = [
            'title',
            'description',
            'diagram_type',
            'content',
            'layout_config'
        ]
    
    def validate_diagram_type(self, value):
        """Validate and normalize diagram_type case-insensitively."""
        if not value:
            return UMLDiagram.DiagramType.CLASS
        
        # Use the model's normalization method
        normalized = UMLDiagram.normalize_diagram_type(value)
        return normalized
    
    def validate(self, attrs):
        """Validate and normalize all attributes."""
        # Ensure content has proper structure
        if 'content' not in attrs or not attrs['content']:
            attrs['content'] = {}
        
        # Ensure layout_config has proper structure
        if 'layout_config' not in attrs or not attrs['layout_config']:
            attrs['layout_config'] = {}
        
        # Provide default title if empty
        if not attrs.get('title', '').strip():
            attrs['title'] = f"Anonymous Diagram {attrs.get('diagram_type', 'CLASS')}"
        
        return attrs
    
    def create(self, validated_data):
        """Create diagram with auto-generated session ID."""
        request = self.context.get('request')
        
        # Generate or get session ID
        session_id = self.get_or_create_session_id(request)
        
        # Create diagram with session ID
        diagram = UMLDiagram.objects.create(
            session_id=session_id,
            **validated_data
        )
        
        return diagram
    
    def get_or_create_session_id(self, request) -> str:
        """Get existing session ID or create new one."""
        if request and hasattr(request, 'session'):
            session_id = request.session.get('diagram_session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                request.session['diagram_session_id'] = session_id
                request.session.save()
            return session_id
        else:
            # Fallback for cases without session
            return str(uuid.uuid4())


class AnonymousDiagramUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating diagrams anonymously."""
    
    class Meta:
        model = UMLDiagram
        fields = [
            'title',
            'description',
            'content',
            'layout_config'
        ]
    
    def update(self, instance, validated_data):
        """Update diagram and track session."""
        request = self.context.get('request')
        
        # Update session_id to current session (last editor)
        if request and hasattr(request, 'session'):
            session_id = self.get_or_create_session_id(request)
            instance.session_id = session_id
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
    
    def get_or_create_session_id(self, request) -> str:
        """Get existing session ID or create new one."""
        session_id = request.session.get('diagram_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['diagram_session_id'] = session_id
            request.session.save()
        return session_id


class DiagramStatsSerializer(serializers.Serializer):
    """Serializer for diagram statistics."""
    
    total_diagrams = serializers.IntegerField()
    diagrams_today = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    most_popular_type = serializers.CharField()
    
    def to_representation(self, instance):
        """Generate statistics data."""
        from django.db.models import Count
        from datetime import datetime, timedelta
        
        today = timezone.now().date()
        
        total_diagrams = UMLDiagram.objects.count()
        diagrams_today = UMLDiagram.objects.filter(
            created_at__date=today
        ).count()
        
        # Count active sessions across all diagrams
        active_sessions = 0
        for diagram in UMLDiagram.objects.all():
            active_sessions += diagram.get_active_sessions_count()
        
        # Most popular diagram type
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
    """Serializer for PlantUML export."""
    
    plantuml_code = serializers.CharField(read_only=True)
    diagram_title = serializers.CharField(read_only=True)
    exported_at = serializers.DateTimeField(read_only=True)
    
    def to_representation(self, diagram):
        """Export diagram to PlantUML format."""
        return {
            'plantuml_code': diagram.export_to_plantuml(),
            'diagram_title': diagram.title,
            'exported_at': timezone.now()
        }
