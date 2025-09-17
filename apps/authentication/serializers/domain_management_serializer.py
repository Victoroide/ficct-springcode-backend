"""
Enterprise Domain Management Serializers
Serializers for authorized domain management and validation.
"""

from rest_framework import serializers
from apps.accounts.models import AuthorizedDomain
from django.contrib.auth import get_user_model
import re

User = get_user_model()


class DomainListSerializer(serializers.ModelSerializer):
    """Serializer for domain list view."""
    
    user_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AuthorizedDomain
        fields = [
            'id', 'domain', 'description', 'is_active', 'status_display',
            'user_count', 'created_at', 'updated_at'
        ]
    
    def get_user_count(self, obj):
        """Count users with this domain."""
        return User.objects.filter(email__iendswith=f'@{obj.domain}').count()
    
    def get_status_display(self, obj):
        """Get human-readable status."""
        return 'Active' if obj.is_active else 'Inactive'


class DomainDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual domain information."""
    
    user_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    recent_users = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()
    
    class Meta:
        model = AuthorizedDomain
        fields = [
            'id', 'domain', 'description', 'is_active', 'status_display',
            'user_count', 'recent_users', 'statistics', 'created_at', 'updated_at'
        ]
    
    def get_user_count(self, obj):
        """Count users with this domain."""
        return User.objects.filter(email__iendswith=f'@{obj.domain}').count()
    
    def get_status_display(self, obj):
        """Get human-readable status."""
        return 'Active' if obj.is_active else 'Inactive'
    
    def get_recent_users(self, obj):
        """Get recent users from this domain."""
        users = User.objects.filter(
            email__iendswith=f'@{obj.domain}'
        ).order_by('-date_joined')[:5]
        
        return [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined,
                'is_active': user.is_active
            }
            for user in users
        ]
    
    def get_statistics(self, obj):
        """Get domain statistics."""
        users = User.objects.filter(email__iendswith=f'@{obj.domain}')
        active_users = users.filter(is_active=True)
        staff_users = users.filter(is_staff=True)
        
        return {
            'total_users': users.count(),
            'active_users': active_users.count(),
            'staff_users': staff_users.count(),
            'recent_registrations': users.filter(
                date_joined__gte=users.order_by('-date_joined').first().date_joined
            ).count() if users.exists() else 0
        }


class DomainCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new authorized domains."""
    
    class Meta:
        model = AuthorizedDomain
        fields = ['domain', 'description', 'is_active']
    
    def validate_domain(self, value):
        """Validate domain format and uniqueness."""
        # Remove protocol and www prefix
        domain = value.lower().strip()
        domain = re.sub(r'^https?://', '', domain)
        domain = re.sub(r'^www\.', '', domain)
        
        # Validate domain format
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, domain):
            raise serializers.ValidationError("Invalid domain format.")
        
        # Check for duplicates
        if AuthorizedDomain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError("This domain is already authorized.")
        
        return domain


class DomainUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating domain information."""
    
    class Meta:
        model = AuthorizedDomain
        fields = ['description', 'is_active']


class DomainValidationSerializer(serializers.Serializer):
    """Serializer for domain validation requests."""
    
    domain = serializers.CharField(max_length=255)
    
    def validate_domain(self, value):
        """Validate domain format."""
        domain = value.lower().strip()
        domain = re.sub(r'^https?://', '', domain)
        domain = re.sub(r'^www\.', '', domain)
        
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, domain):
            raise serializers.ValidationError("Invalid domain format.")
        
        return domain


class DomainStatisticsSerializer(serializers.Serializer):
    """Serializer for domain statistics."""
    
    total_domains = serializers.IntegerField()
    active_domains = serializers.IntegerField()
    inactive_domains = serializers.IntegerField()
    total_users = serializers.IntegerField()
    domain_breakdown = serializers.ListField(child=serializers.DictField())
    recent_additions = serializers.ListField(child=serializers.DictField())


class DomainUserListSerializer(serializers.Serializer):
    """Serializer for users from a specific domain."""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    is_active = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)


class BulkDomainOperationSerializer(serializers.Serializer):
    """Serializer for bulk domain operations."""
    
    domain_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50
    )
    operation = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'delete']
    )
    
    def validate_domain_ids(self, value):
        """Validate all domain IDs exist."""
        existing_ids = set(AuthorizedDomain.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = set(value) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f"Domains with IDs {list(missing_ids)} do not exist."
            )
        return value


class DomainActivationSerializer(serializers.Serializer):
    """Serializer for domain activation/deactivation."""
    
    is_active = serializers.BooleanField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
