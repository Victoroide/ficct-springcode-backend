from rest_framework import serializers
from ..models import UMLElement


class UMLElementListSerializer(serializers.ModelSerializer):
    class Meta:
        model = UMLElement
        fields = ['id', 'name', 'class_type', 'position_x', 'position_y', 
                 'width', 'height', 'created_at']


class UMLElementDetailSerializer(serializers.ModelSerializer):
    diagram_name = serializers.CharField(source='diagram.name', read_only=True)
    
    class Meta:
        model = UMLElement
        fields = ['id', 'diagram', 'diagram_name', 'class_type', 'name',
                 'position_x', 'position_y', 'width', 'height', 
                 'attributes', 'methods', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at']


class UMLElementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UMLElement
        fields = ['diagram', 'class_type', 'name', 'position_x', 'position_y',
                 'width', 'height', 'package', 'visibility']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
