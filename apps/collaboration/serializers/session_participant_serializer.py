from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import SessionParticipant

User = get_user_model()


class SessionParticipantListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = SessionParticipant
        fields = ['id', 'user', 'username', 'role', 'is_active', 'joined_at', 'last_activity']


class SessionParticipantDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SessionParticipant
        fields = ['id', 'session', 'user', 'username', 'email', 'role', 'is_active',
                 'cursor_position', 'joined_at', 'last_activity', 'left_at']
        read_only_fields = ['joined_at', 'last_activity', 'left_at']


class SessionParticipantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionParticipant
        fields = ['session', 'user', 'role']
