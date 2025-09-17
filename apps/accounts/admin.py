"""Enterprise User Management Admin Interface"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from .models import EnterpriseUser, AuthorizedDomain, PasswordHistory


@admin.register(EnterpriseUser)
class EnterpriseUserAdmin(UserAdmin):
    
    list_display = (
        'corporate_email', 'full_name', 'role', 'department', 
        'company_domain', 'is_active', 'email_verified', 
        'is_2fa_enabled', 'last_login', 'security_status'
    )
    
    list_filter = (
        'is_active', 'email_verified', 'is_2fa_enabled', 'role',
        'company_domain', 'department', 'is_staff', 'is_superuser',
        'created_at', 'last_login'
    )
    
    search_fields = (
        'corporate_email', 'full_name', 'employee_id', 
        'company_domain', 'department'
    )
    
    ordering = ('-created_at',)
    
    readonly_fields = (
        'last_login', 'created_at', 'updated_at', 'password_changed_at',
        'last_login_ip', 'last_login_user_agent', 'security_info',
        'audit_summary', 'password_expiry_status'
    )
    
    fieldsets = (
        ('Corporate Identity', {
            'fields': ('corporate_email', 'full_name', 'role', 'department', 
                      'company_domain', 'employee_id')
        }),
        ('Account Status', {
            'fields': ('is_active', 'email_verified', 'is_staff', 'is_superuser')
        }),
        ('Security Settings', {
            'fields': ('is_2fa_enabled', 'failed_login_attempts', 
                      'account_locked_until', 'password_expiry_status'),
            'classes': ('collapse',)
        }),
        ('Session Information', {
            'fields': ('last_login', 'last_login_ip', 'last_login_user_agent', 
                      'last_activity', 'session_key'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'password_changed_at',
                      'security_info', 'audit_summary'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_users', 'deactivate_users', 'force_password_reset',
        'unlock_accounts', 'disable_2fa', 'send_verification_email'
    ]
    
    def security_status(self, obj):
        status_items = []
        
        if obj.is_account_locked():
            status_items.append('<span style="color: red;">🔒 Locked</span>')
        
        if not obj.email_verified:
            status_items.append('<span style="color: orange;">📧 Unverified</span>')
        
        if obj.is_2fa_enabled:
            status_items.append('<span style="color: green;">🔐 2FA</span>')
        else:
            status_items.append('<span style="color: orange;">❌ No 2FA</span>')
        
        if obj.is_password_expired():
            status_items.append('<span style="color: red;">🔑 Password Expired</span>')
        
        return format_html(' | '.join(status_items))
    
    security_status.short_description = 'Security Status'
    
    def security_info(self, obj):
        info = []
        
        info.append(f"Failed Attempts: {obj.failed_login_attempts}")
        
        if obj.account_locked_until:
            info.append(f"Locked Until: {obj.account_locked_until}")
        
        if obj.password_expires_at:
            info.append(f"Password Expires: {obj.password_expires_at}")
        
        if obj.backup_codes:
            info.append(f"Backup Codes: {len(obj.backup_codes)} remaining")
        
        return format_html('<br>'.join(info))
    
    security_info.short_description = 'Security Details'
    
    def password_expiry_status(self, obj):
        if not obj.password_expires_at:
            return format_html('<span style="color: gray;">No Expiry Set</span>')
        
        days_until_expiry = (obj.password_expires_at - timezone.now()).days
        
        if days_until_expiry < 0:
            return format_html('<span style="color: red;">Expired {} days ago</span>', 
                             abs(days_until_expiry))
        elif days_until_expiry <= 7:
            return format_html('<span style="color: orange;">Expires in {} days</span>', 
                             days_until_expiry)
        else:
            return format_html('<span style="color: green;">Expires in {} days</span>', 
                             days_until_expiry)
    
    password_expiry_status.short_description = 'Password Status'
    
    def audit_summary(self, obj):
        from apps.audit.models import AuditLog
        
        recent_logs = AuditLog.objects.filter(
            user=obj,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        failed_logins = AuditLog.objects.filter(
            user=obj,
            action_type=AuditLog.ActionType.LOGIN_FAILED,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        return format_html(
            'Recent Activity (30 days): {} events<br>'
            'Failed Logins (30 days): {}',
            recent_logs, failed_logins
        )
    
    audit_summary.short_description = 'Audit Summary'
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    
    deactivate_users.short_description = 'Deactivate selected users'
    
    def force_password_reset(self, request, queryset):
        for user in queryset:
            user.password_expires_at = timezone.now()
            user.save(update_fields=['password_expires_at'])
        
        count = queryset.count()
        self.message_user(request, f'{count} users marked for password reset.')
    
    force_password_reset.short_description = 'Force password reset'
    
    def unlock_accounts(self, request, queryset):
        for user in queryset:
            user.unlock_account()
        
        count = queryset.count()
        self.message_user(request, f'{count} accounts unlocked.')
    
    unlock_accounts.short_description = 'Unlock accounts'
    
    def disable_2fa(self, request, queryset):
        updated = queryset.update(
            is_2fa_enabled=False,
            two_factor_secret='',
            backup_codes=[]
        )
        self.message_user(request, f'2FA disabled for {updated} users.')
    
    disable_2fa.short_description = 'Disable 2FA'


@admin.register(AuthorizedDomain)
class AuthorizedDomainAdmin(admin.ModelAdmin):
    
    list_display = (
        'domain', 'company_name', 'is_active', 
        'user_count', 'created_at', 'created_by'
    )
    
    list_filter = ('is_active', 'created_at')
    
    search_fields = ('domain', 'company_name')
    
    readonly_fields = ('created_at', 'user_count_detail')
    
    fieldsets = (
        ('Domain Information', {
            'fields': ('domain', 'company_name', 'is_active')
        }),
        ('Creation Info', {
            'fields': ('created_by', 'created_at', 'user_count_detail'),
            'classes': ('collapse',)
        }),
    )
    
    def user_count(self, obj):
        count = EnterpriseUser.objects.filter(company_domain=obj.domain).count()
        return f"{count} users"
    
    user_count.short_description = 'Users'
    
    def user_count_detail(self, obj):
        total_users = EnterpriseUser.objects.filter(company_domain=obj.domain).count()
        active_users = EnterpriseUser.objects.filter(
            company_domain=obj.domain, is_active=True
        ).count()
        verified_users = EnterpriseUser.objects.filter(
            company_domain=obj.domain, email_verified=True
        ).count()
        
        return format_html(
            'Total Users: {}<br>'
            'Active Users: {}<br>'
            'Verified Users: {}',
            total_users, active_users, verified_users
        )
    
    user_count_detail.short_description = 'User Statistics'


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    
    list_display = ('user', 'created_at', 'password_age')
    
    list_filter = ('created_at',)
    
    search_fields = ('user__corporate_email', 'user__full_name')
    
    readonly_fields = ('user', 'password_hash', 'created_at', 'password_age')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def password_age(self, obj):
        age = timezone.now() - obj.created_at
        return f"{age.days} days ago"
    
    password_age.short_description = 'Age'


admin.site.site_header = 'FICCT Enterprise Administration'
admin.site.site_title = 'Enterprise Admin'
admin.site.index_title = 'Enterprise Management Portal'
