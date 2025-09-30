from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from ..models import UMLDiagram


class UMLDiagramListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    element_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UMLDiagram
        fields = ['id', 'name', 'diagram_type', 'status', 'owner_name', 
                 'element_count', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.IntegerField())
    def get_element_count(self, obj) -> int:
        try:
            classes_count = len(obj.get_classes() or [])
            relationships_count = len(obj.get_relationships() or [])
            return classes_count + relationships_count
        except Exception:

            return 0


class UMLDiagramDetailSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    elements = serializers.SerializerMethodField()
    relationships = serializers.SerializerMethodField()
    
    class Meta:
        model = UMLDiagram
        fields = ['id', 'name', 'description', 'diagram_type', 'status', 
                 'owner', 'owner_name', 'diagram_data', 'metadata',
                 'created_by', 'created_at', 'updated_at', 'elements', 'relationships']
        read_only_fields = ['created_by', 'created_at']
    
    @extend_schema_field(serializers.ListField())
    def get_elements(self, obj) -> list:
        try:
            return obj.get_classes() or []
        except Exception:
            return []
    
    @extend_schema_field(serializers.ListField())
    def get_relationships(self, obj) -> list:
        try:
            return obj.get_relationships() or []
        except Exception:
            return []


class UMLDiagramCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UMLDiagram
        fields = ['name', 'description', 'diagram_type', 'owner', 
                 'diagram_data', 'metadata']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        validated_data['last_modified_by'] = self.context['request'].user
        return super().create(validated_data)
