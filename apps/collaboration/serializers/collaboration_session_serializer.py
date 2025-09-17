from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from ..models import CollaborationSession


class CollaborationSessionListSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CollaborationSession
        fields = ['id', 'status', 'created_at', 'participant_count']
    
    @extend_schema_field(serializers.IntegerField())
    def get_participant_count(self, obj) -> int:
        return obj.participants.count()


class CollaborationSessionDetailSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    diagram_name = serializers.CharField(source='diagram.name', read_only=True)
    
    class Meta:
        model = CollaborationSession
        fields = [
            'id', 'project', 'diagram', 'diagram_name', 'host_user',
            'status', 'session_data', 'created_at', 'updated_at', 'ended_at',
            'participants'
        ]
        read_only_fields = ['host_user', 'created_at', 'updated_at', 'ended_at']
    
    @extend_schema_field(serializers.ListField())
    def get_participants(self, obj) -> list:
        from .session_participant_serializer import SessionParticipantListSerializer
        return SessionParticipantListSerializer(
            obj.participants.all(), many=True
        ).data


class CollaborationSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollaborationSession
        fields = ['project', 'diagram', 'session_data']
    
    def create(self, validated_data):
        validated_data['host_user'] = self.context['request'].user
        return super().create(validated_data)
