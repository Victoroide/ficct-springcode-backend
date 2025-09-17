"""Enterprise Audit Management Admin Interface"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import AuditLog, SecurityAlert


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    
    list_display = (
        'timestamp', 'user', 'action_type', 'severity',
        'ip_address', 'status_indicator', 'risk_assessment'
    )
    
    list_filter = (
        'action_type', 'severity', 'timestamp', 
        'ip_address', 'user_agent'
    )
    
    search_fields = (
        'user__corporate_email', 'user__full_name', 'ip_address',
        'resource', 'details'
    )
    
    readonly_fields = (
        'timestamp', 'user', 'action_type', 'resource', 'ip_address',
        'user_agent', 'details', 'severity', 'session_key',
        'method', 'status_code', 'formatted_details', 'error_message'
    )
    
    ordering = ('-timestamp',)
    
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('timestamp', 'user', 'action_type', 'resource')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'session_key'),
            'classes': ('collapse',)
        }),
        ('Response Information', {
            'fields': ('status_code', 'method', 'severity', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Additional Details', {
            'fields': ('formatted_details',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['export_to_csv', 'mark_as_reviewed']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        
        if obj and obj.timestamp > timezone.now() - timedelta(days=30):
            return False
        
        return True
    
    def status_indicator(self, obj):
        color_map = {
            'LOW': 'green',
            'MEDIUM': 'orange', 
            'HIGH': 'red',
            'CRITICAL': 'darkred'
        }
        
        color = color_map.get(obj.severity, 'gray')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span>',
            color
        )
    
    status_indicator.short_description = 'Status'
    
    def risk_assessment(self, obj):
        if obj.action_type in ['LOGIN_FAILED', 'ACCOUNT_LOCKED', 'SUSPICIOUS_ACTIVITY']:
            return format_html('<span style="color: red;">High Risk</span>')
        elif obj.action_type in ['LOGIN_SUCCESS', 'LOGOUT']:
            return format_html('<span style="color: green;">Normal</span>')
        elif obj.action_type in ['PASSWORD_CHANGED', 'EMAIL_CHANGED']:
            return format_html('<span style="color: orange;">Medium Risk</span>')
        else:
            return format_html('<span style="color: gray;">Low Risk</span>')
    
    risk_assessment.short_description = 'Risk Level'
    
    def formatted_details(self, obj):
        if not obj.details:
            return 'No details available'
        
        import json
        try:
            formatted = json.dumps(obj.details, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except (TypeError, ValueError):
            return str(obj.details)
    
    formatted_details.short_description = 'Details'
    
    def export_to_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User', 'Action Type', 'Resource', 
            'IP Address', 'Severity', 'Details'
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.corporate_email if log.user else 'Anonymous',
                log.get_action_type_display(),
                log.resource,
                log.ip_address,
                log.get_severity_level_display(),
                str(log.details) if log.details else ''
            ])
        
        return response
    
    export_to_csv.short_description = 'Export to CSV'


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    
    list_display = (
        'created_at', 'alert_type', 'severity', 'user', 
        'status', 'alert_status'
    )
    
    list_filter = (
        'alert_type', 'severity', 'status', 'created_at'
    )
    
    search_fields = (
        'user__corporate_email', 'user__full_name', 
        'ip_address', 'description', 'title'
    )
    
    readonly_fields = (
        'created_at', 'updated_at', 'alert_type', 'user', 'ip_address', 
        'user_agent', 'risk_score', 'formatted_metadata'
    )
    
    ordering = ('-created_at',)
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('created_at', 'alert_type', 'severity', 'title', 'description')
        }),
        ('User & Location', {
            'fields': ('user', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('status', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Additional Data', {
            'fields': ('risk_score', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_resolved', 'mark_unresolved']
    
    def alert_status(self, obj):
        if obj.status == 'RESOLVED':
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Resolved</span>'
            )
        else:
            severity_colors = {
                'LOW': 'orange',
                'MEDIUM': 'darkorange',
                'HIGH': 'red',
                'CRITICAL': 'darkred'
            }
            color = severity_colors.get(obj.severity, 'gray')
            return format_html(
                '<span style="color: {}; font-weight: bold;">⚠ {}</span>',
                color, obj.get_severity_display()
            )
    
    alert_status.short_description = 'Status'
    
    def formatted_metadata(self, obj):
        
        info = []
        if hasattr(obj, 'risk_score'):
            info.append(f"Risk Score: {obj.risk_score}")
        if hasattr(obj, 'audit_logs'):
            count = obj.audit_logs.count()
            info.append(f"Related Audit Logs: {count}")
        
        return format_html('<br>'.join(info)) if info else 'No additional metadata'
    
    formatted_metadata.short_description = 'Metadata'
    
    def mark_resolved(self, request, queryset):
        updated = queryset.update(
            status='RESOLVED',
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        self.message_user(request, f'{updated} alerts marked as resolved.')
    
    mark_resolved.short_description = 'Mark as resolved'
    
    def mark_unresolved(self, request, queryset):
        updated = queryset.update(
            status='OPEN',
            resolved_at=None,
            resolved_by=None,
            resolution_notes=''
        )
        self.message_user(request, f'{updated} alerts marked as unresolved.')
    
    mark_unresolved.short_description = 'Mark as unresolved'


class AuditSummaryFilter(admin.SimpleListFilter):
    title = 'Activity Summary'
    parameter_name = 'activity'
    
    def lookups(self, request, model_admin):
        return (
            ('failed_logins', 'Failed Logins'),
            ('successful_logins', 'Successful Logins'),
            ('security_events', 'Security Events'),
            ('admin_actions', 'Admin Actions'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'failed_logins':
            return queryset.filter(action_type='LOGIN_FAILED')
        elif self.value() == 'successful_logins':
            return queryset.filter(action_type='LOGIN_SUCCESS')
        elif self.value() == 'security_events':
            return queryset.filter(
                action_type__in=['ACCOUNT_LOCKED', 'SUSPICIOUS_ACTIVITY', 'SECURITY_VIOLATION']
            )
        elif self.value() == 'admin_actions':
            return queryset.filter(
                action_type__in=['USER_CREATED', 'USER_UPDATED', 'USER_DELETED']
            )
