"""
Public serializer for UML Diagrams.

Provides safe serialization of diagram data for public access,
excluding sensitive information like owner details.
"""

from rest_framework import serializers
from ..models import UMLDiagram


class UMLDiagramPublicSerializer(serializers.ModelSerializer):
    """
    Public serializer for UML Diagrams.
    
    Excludes sensitive information and provides only necessary
    fields for public diagram access and editing.
    """
    
    diagram_type_display = serializers.CharField(
        source='get_diagram_type_display', 
        read_only=True
    )
    visibility_display = serializers.CharField(
        source='get_visibility_display', 
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )

    classes_count = serializers.SerializerMethodField()
    relationships_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UMLDiagram
        fields = [
            'id',
            'name',
            'description',
            'diagram_type',
            'diagram_type_display',
            'status',
            'status_display',
            'visibility',
            'visibility_display',
            'diagram_data',
            'layout_config',
            'validation_results',
            'tags',
            'metadata',
            'created_at',
            'updated_at',
            'last_validated_at',
            'version_number',
            'is_template',
            'is_public',
            'classes_count',
            'relationships_count',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'last_validated_at',
            'version_number',
            'classes_count',
            'relationships_count',
        ]
    
    def get_classes_count(self, obj):
        """Get number of classes in diagram."""
        try:
            return len(obj.get_classes())
        except:
            return 0
    
    def get_relationships_count(self, obj):
        """Get number of relationships in diagram."""
        try:
            return len(obj.get_relationships())
        except:
            return 0
    
    def validate_diagram_data(self, value):
        """Validate diagram data structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Diagram data must be a dictionary")

        required_keys = ['classes', 'relationships']
        for key in required_keys:
            if key not in value:
                value[key] = []

        if not isinstance(value['classes'], list):
            raise serializers.ValidationError("Classes must be a list")

        if not isinstance(value['relationships'], list):
            raise serializers.ValidationError("Relationships must be a list")
        
        return value
    
    def validate_layout_config(self, value):
        """Validate layout configuration."""
        if value is None:
            return {}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Layout config must be a dictionary")
        
        return value
    
    def validate_tags(self, value):
        """Validate tags."""
        if value is None:
            return []
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")

        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("Each tag must be a string")
            if len(tag) > 50:
                raise serializers.ValidationError("Tags must be 50 characters or less")

        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 tags allowed")
        
        return value
    
    def validate_metadata(self, value):
        """Validate metadata."""
        if value is None:
            return {}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        
        return value
    
    def validate_name(self, value):
        """Validate diagram name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required")
        
        if len(value) > 255:
            raise serializers.ValidationError("Name must be 255 characters or less")
        
        return value.strip()
    
    def validate_description(self, value):
        """Validate description."""
        if value and len(value) > 1000:
            raise serializers.ValidationError("Description must be 1000 characters or less")
        
        return value
    
    def update(self, instance, validated_data):
        """Update diagram with version increment."""

        if 'diagram_data' in validated_data:
            if instance.diagram_data != validated_data['diagram_data']:
                instance.version_number += 1

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class UMLDiagramPublicListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for public diagram lists.
    
    Used for listing public diagrams with minimal information.
    """
    
    diagram_type_display = serializers.CharField(
        source='get_diagram_type_display', 
        read_only=True
    )
    
    class Meta:
        model = UMLDiagram
        fields = [
            'id',
            'name',
            'description',
            'diagram_type',
            'diagram_type_display',
            'created_at',
            'updated_at',
            'version_number',
            'is_template',
            'tags',
        ]
        read_only_fields = fields
