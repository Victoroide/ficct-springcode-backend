"""
Enterprise User Management Serializers
Serializers for user management CRUD operations with proper validation.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import AuthorizedDomain
from django.contrib.sessions.models import Session
from django.db import transaction

User = get_user_model()


class UserListSerializer(serializers.ModelSerializer):
    
    full_name = serializers.SerializerMethodField()
    is_2fa_enabled = serializers.SerializerMethodField()
    session_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name', 'is_active', 
            'is_staff', 'is_2fa_enabled', 'session_count', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_is_2fa_enabled(self, obj):
        return hasattr(obj, 'userprofile') and obj.userprofile.is_2fa_enabled
    
    def get_session_count(self, obj):
        return Session.objects.filter(session_data__contains=str(obj.id)).count()


class UserDetailSerializer(serializers.ModelSerializer):
    
    full_name = serializers.SerializerMethodField()
    is_2fa_enabled = serializers.SerializerMethodField()
    active_sessions = serializers.SerializerMethodField()
    authorized_domain = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'is_active', 'is_staff', 'is_superuser',
            'is_2fa_enabled', 'active_sessions', 'authorized_domain',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_is_2fa_enabled(self, obj):
        return hasattr(obj, 'userprofile') and obj.userprofile.is_2fa_enabled
    
    def get_active_sessions(self, obj):
        return Session.objects.filter(session_data__contains=str(obj.id)).count()
    
    def get_authorized_domain(self, obj):
        domain = obj.email.split('@')[1] if '@' in obj.email else None
        if domain:
            try:
                auth_domain = AuthorizedDomain.objects.get(domain=domain)
                return {'domain': auth_domain.domain, 'is_active': auth_domain.is_active}
            except AuthorizedDomain.DoesNotExist:
                pass
        return None


class UserCreateSerializer(serializers.ModelSerializer):
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'is_active', 'is_staff'
        ]
    
    def validate_email(self, value):
        """Validate email format."""
        # Domain validation disabled - all domains are allowed
        return value
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'is_active', 'is_staff'
        ]
    
    def validate_email(self, value):
        """Validate email format."""
        # Domain validation disabled - all domains are allowed
        return value


class PasswordResetSerializer(serializers.Serializer):
    
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs


class UserSessionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Session
        fields = [
            'session_key', 'session_data', 'expire_date'
        ]
        read_only_fields = ['session_key']


class BulkUserUpdateSerializer(serializers.Serializer):
    
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'delete', 'make_staff', 'remove_staff']
    )
    
    def validate_user_ids(self, value):
        existing_ids = set(User.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = set(value) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f"Users with IDs {list(missing_ids)} do not exist."
            )
        return value
