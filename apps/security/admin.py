"""
Enterprise Security Management Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from .models import IPWhitelist, SecurityConfiguration


@admin.register(IPWhitelist)
class IPWhitelistAdmin(admin.ModelAdmin):
    
    list_display = (
        'ip_address', 'description', 'is_active', 
        'access_level', 'created_at', 'created_by'
    )
    
    list_filter = ('is_active', 'access_level', 'created_at')
    
    search_fields = ('ip_address', 'description')
    
    readonly_fields = ('created_at', 'last_used')
    
    fieldsets = (
        ('IP Information', {
            'fields': ('ip_address', 'description', 'is_active')
        }),
        ('Access Control', {
            'fields': ('access_level', 'allowed_paths')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SecurityConfiguration)
class SecurityConfigurationAdmin(admin.ModelAdmin):
    
    list_display = (
        'setting_name', 'setting_value', 'is_active', 
        'updated_at', 'updated_by'
    )
    
    list_filter = ('is_active', 'updated_at')
    
    search_fields = ('setting_name', 'description')
    
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Configuration', {
            'fields': ('setting_name', 'setting_value', 'description', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.updated_by = request.user
        else:  # Updating existing
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
