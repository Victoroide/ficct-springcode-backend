from rest_framework import serializers
from ..models import UMLRelationship


class UMLRelationshipListSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source_class.name', read_only=True)
    target_name = serializers.CharField(source='target_class.name', read_only=True)
    
    class Meta:
        model = UMLRelationship
        fields = ['id', 'relationship_type', 'source_class', 'target_class',
                 'source_name', 'target_name', 'name', 'created_at']


class UMLRelationshipDetailSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source_class.name', read_only=True)
    target_name = serializers.CharField(source='target_class.name', read_only=True)
    diagram_name = serializers.CharField(source='diagram.name', read_only=True)
    
    class Meta:
        model = UMLRelationship
        fields = ['id', 'diagram', 'diagram_name', 'source_class', 'target_class',
                 'source_name', 'target_name', 'relationship_type', 'name',
                 'source_multiplicity', 'target_multiplicity', 'style_config', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at']


class UMLRelationshipCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UMLRelationship
        fields = ['diagram', 'source_class', 'target_class', 'relationship_type',
                 'name', 'source_multiplicity', 'target_multiplicity', 'style_config']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
