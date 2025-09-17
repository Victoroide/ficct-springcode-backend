from rest_framework import serializers
from ..models import UMLChangeEvent


class UMLChangeEventListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UMLChangeEvent
        fields = ['id', 'event_type', 'timestamp', 'username']


class UMLChangeEventDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    session_name = serializers.CharField(source='session.session_name', read_only=True)
    
    class Meta:
        model = UMLChangeEvent
        fields = ['id', 'session', 'session_name', 'user', 'username', 
                 'event_type', 'change_data', 'timestamp']
        read_only_fields = ['timestamp']


class UMLChangeEventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UMLChangeEvent
        fields = ['session', 'event_type', 'change_data']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
