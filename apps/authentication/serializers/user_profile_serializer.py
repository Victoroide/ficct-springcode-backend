"""
User Profile Serializer for enterprise user data representation.
"""

from rest_framework import serializers
from apps.accounts.models import EnterpriseUser
from typing import Dict, Any


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile data with enterprise-specific fields.
    Provides read-only access to sensitive user information.
    """
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    last_login_formatted = serializers.SerializerMethodField()
    account_age_days = serializers.SerializerMethodField()
    password_expires_in_days = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    security_status = serializers.SerializerMethodField()
    
    class Meta:
        model = EnterpriseUser
        fields = [
            'id',
            'corporate_email',
            'full_name',
            'role',
            'role_display',
            'department',
            'company_domain',
            'employee_id',
            'is_2fa_enabled',
            'email_verified',
            'last_login',
            'last_login_formatted',
            'last_login_ip',
            'created_at',
            'account_age_days',
            'password_changed_at',
            'password_expires_in_days',
            'last_activity',
            'permissions',
            'security_status',
            'is_active',
            'is_staff',
        ]
        read_only_fields = [
            'id',
            'corporate_email',
            'company_domain',
            'email_verified',
            'last_login',
            'last_login_ip',
            'created_at',
            'password_changed_at',
            'last_activity',
            'is_active',
            'is_staff',
        ]
    
    def get_last_login_formatted(self, obj: EnterpriseUser) -> str:
        """
        Get formatted last login datetime.
        """
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M:%S UTC')
        return "Never"
    
    def get_account_age_days(self, obj: EnterpriseUser) -> int:
        """
        Calculate account age in days.
        """
        from django.utils import timezone
        
        if obj.created_at:
            delta = timezone.now() - obj.created_at
            return delta.days
        return 0
    
    def get_password_expires_in_days(self, obj: EnterpriseUser) -> int:
        """
        Calculate days until password expires.
        """
        from django.utils import timezone
        
        if obj.password_expires_at:
            delta = obj.password_expires_at - timezone.now()
            return max(0, delta.days)
        return 0
    
    def get_permissions(self, obj: EnterpriseUser) -> Dict[str, Any]:
        """
        Get user permissions and capabilities.
        """
        return {
            'can_manage_users': obj.role in [
                EnterpriseUser.UserRole.SUPER_ADMIN,
                EnterpriseUser.UserRole.ADMIN
            ],
            'can_view_audit_logs': obj.role in [
                EnterpriseUser.UserRole.SUPER_ADMIN,
                EnterpriseUser.UserRole.ADMIN,
                EnterpriseUser.UserRole.MANAGER
            ],
            'can_modify_security_settings': obj.role == EnterpriseUser.UserRole.SUPER_ADMIN,
            'can_access_admin_panel': obj.is_staff,
            'requires_2fa': obj.is_2fa_enabled,
            'can_generate_reports': obj.role in [
                EnterpriseUser.UserRole.SUPER_ADMIN,
                EnterpriseUser.UserRole.ADMIN,
                EnterpriseUser.UserRole.MANAGER,
                EnterpriseUser.UserRole.ANALYST
            ]
        }
    
    def get_security_status(self, obj: EnterpriseUser) -> Dict[str, Any]:
        """
        Get user security status and indicators.
        """
        return {
            '2fa_enabled': obj.is_2fa_enabled,
            'email_verified': obj.email_verified,
            'account_locked': obj.is_account_locked(),
            'password_expired': obj.is_password_expired(),
            'failed_login_attempts': obj.failed_login_attempts,
            'backup_codes_available': len(obj.backup_codes) if obj.backup_codes else 0,
            'last_password_change': obj.password_changed_at.strftime('%Y-%m-%d') if obj.password_changed_at else None,
            'security_score': self._calculate_security_score(obj)
        }
    
    def _calculate_security_score(self, obj: EnterpriseUser) -> int:
        """
        Calculate security score based on user's security features.
        """
        score = 0
        
        # Base score for active account
        if obj.is_active:
            score += 20
        
        # Email verification
        if obj.email_verified:
            score += 20
        
        # 2FA enabled
        if obj.is_2fa_enabled:
            score += 30
        
        # Recent password change (within 90 days)
        if obj.password_changed_at:
            from django.utils import timezone
            from datetime import timedelta
            
            if timezone.now() - obj.password_changed_at <= timedelta(days=90):
                score += 15
        
        # No failed login attempts
        if obj.failed_login_attempts == 0:
            score += 10
        
        # Has backup codes
        if obj.backup_codes:
            score += 5
        
        return min(score, 100)  # Cap at 100
    
    def to_representation(self, instance: EnterpriseUser) -> Dict[str, Any]:
        """
        Custom representation with enterprise-specific data formatting.
        """
        data = super().to_representation(instance)
        
        # Add computed fields
        data['full_profile_complete'] = all([
            instance.full_name,
            instance.department,
            instance.employee_id,
        ])
        
        # Security recommendations
        recommendations = []
        
        if not instance.is_2fa_enabled:
            recommendations.append("Enable Two-Factor Authentication for enhanced security")
        
        if instance.is_password_expired():
            recommendations.append("Your password has expired. Please update it.")
        
        if instance.failed_login_attempts > 0:
            recommendations.append("Recent failed login attempts detected. Monitor your account security.")
        
        if not instance.backup_codes:
            recommendations.append("Generate backup codes for 2FA recovery")
        
        data['security_recommendations'] = recommendations
        
        return data
    
    def update(self, instance: EnterpriseUser, validated_data: Dict[str, Any]) -> EnterpriseUser:
        """
        Update user profile with validation for changeable fields.
        """
        # Only allow updates to specific fields
        allowed_fields = ['full_name', 'department', 'employee_id']
        
        for field in allowed_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        instance.save()
        return instance


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information.
    """
    
    class Meta:
        model = EnterpriseUser
        fields = [
            'full_name',
            'department',
            'employee_id',
        ]
    
    def validate_full_name(self, value: str) -> str:
        """
        Validate full name format.
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Full name cannot be empty")
        
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters")
        
        return value.strip()
    
    def validate_employee_id(self, value: str) -> str:
        """
        Validate employee ID uniqueness.
        """
        if value:
            # Check if employee ID already exists for another user
            existing_user = EnterpriseUser.objects.filter(
                employee_id=value
            ).exclude(id=self.instance.id if self.instance else None).first()
            
            if existing_user:
                raise serializers.ValidationError(
                    "Employee ID already exists for another user"
                )
        
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing user password with enterprise validation.
    """
    
    current_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="New password"
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )
    
    def validate_current_password(self, value: str) -> str:
        """
        Validate current password is correct.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        
        return value
    
    def validate_new_password(self, value: str) -> str:
        """
        Validate new password meets enterprise requirements.
        """
        user = self.context['request'].user
        
        # Check password strength
        is_valid, errors = user.check_password_policy(value)
        if not is_valid:
            raise serializers.ValidationError(errors)
        
        # Check password history (if implemented)
        from apps.accounts.models import PasswordHistory
        if PasswordHistory.check_password_reuse(user, value):
            raise serializers.ValidationError(
                "Password has been used recently. Please choose a different password."
            )
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate password change data.
        """
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        current_password = attrs.get('current_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': "New passwords do not match"
            })
        
        if new_password == current_password:
            raise serializers.ValidationError({
                'new_password': "New password must be different from current password"
            })
        
        return attrs
    
    def save(self) -> None:
        """
        Save new password and update related fields.
        """
        user = self.context['request'].user
        new_password = self.validated_data['new_password']
        
        # Add current password to history
        from apps.accounts.models import PasswordHistory
        PasswordHistory.add_password_to_history(user, user.password)
        
        # Set new password
        user.set_password(new_password)
        user.set_password_expiry()
        user.save()


class DisableTwoFactorSerializer(serializers.Serializer):
    """
    Serializer for disabling 2FA with password confirmation.
    """
    
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password for confirmation"
    )
    
    def validate_password(self, value: str) -> str:
        """
        Validate password is correct.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect")
        
        if not user.is_2fa_enabled:
            raise serializers.ValidationError("2FA is not currently enabled")
        
        return value
    
    def save(self) -> Dict[str, str]:
        """
        Disable 2FA for the user.
        """
        user = self.context['request'].user
        user.disable_2fa()
        
        return {
            'success': True,
            'message': '2FA has been disabled successfully'
        }
