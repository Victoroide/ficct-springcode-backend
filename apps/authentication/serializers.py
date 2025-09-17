"""
Enterprise Authentication Serializers

Serializers for authentication API endpoints supporting CU1, CU2, CU3.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import EnterpriseUser, AuthorizedDomain


class LoginRequestSerializer(serializers.Serializer):
    """
    Serializer for CU1: Iniciar Sesión Empresarial - Step 1
    """
    corporate_email = serializers.EmailField(
        help_text="Corporate email address"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="User password"
    )
    
    def validate_corporate_email(self, value):
        """Validate email format and normalize."""
        return value.lower().strip()


class TwoFactorVerifySerializer(serializers.Serializer):
    """
    Serializer for CU1: Iniciar Sesión Empresarial - Step 2
    """
    session_token = serializers.CharField(
        help_text="2FA session token from login response"
    )
    code = serializers.CharField(
        min_length=6,
        max_length=8,
        help_text="2FA code from authenticator app or backup code"
    )
    
    def validate_code(self, value):
        """Clean and validate 2FA code."""
        # Remove spaces and convert to uppercase for backup codes
        return value.replace(' ', '').strip().upper()


class LoginResponseSerializer(serializers.Serializer):
    """
    Serializer for login response data
    """
    status = serializers.CharField()
    message = serializers.CharField()
    tokens = serializers.DictField(required=False)
    user = serializers.DictField(required=False)
    session_token = serializers.CharField(required=False, source='2fa_session_token')
    user_id = serializers.IntegerField(required=False)


class LogoutRequestSerializer(serializers.Serializer):
    """
    Serializer for CU2: Cerrar Sesión Segura
    """
    refresh_token = serializers.CharField(
        required=False,
        help_text="Refresh token to blacklist (optional)"
    )


class RegistrationRequestSerializer(serializers.Serializer):
    """
    Serializer for CU3: Registrar Usuario Empresarial
    """
    corporate_email = serializers.EmailField(
        help_text="Corporate email address"
    )
    full_name = serializers.CharField(
        max_length=150,
        help_text="Full name of the employee"
    )
    role = serializers.ChoiceField(
        choices=EnterpriseUser.Role.choices,
        help_text="Professional role in the organization"
    )
    department = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Department or division within the company"
    )
    employee_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        help_text="Company employee ID number"
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="User password (must meet enterprise policy)"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Password confirmation"
    )
    
    def validate_corporate_email(self, value):
        """Validate email format and check if already exists."""
        email = value.lower().strip()
        
        if EnterpriseUser.objects.filter(corporate_email=email).exists():
            raise serializers.ValidationError(
                "User with this corporate email already exists."
            )
        
        return email
    
    def validate_full_name(self, value):
        """Validate and clean full name."""
        name = value.strip()
        if len(name.split()) < 2:
            raise serializers.ValidationError(
                "Please provide both first and last name."
            )
        return name
    
    def validate_employee_id(self, value):
        """Validate employee ID uniqueness if provided."""
        if value and EnterpriseUser.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError(
                "Employee ID already exists."
            )
        return value
    
    def validate_password(self, value):
        """Validate password against enterprise policy."""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        
        # Additional enterprise validation
        errors = []
        
        if len(value) < 8:
            errors.append("Password must be at least 8 characters long.")
        
        if not any(c.isupper() for c in value):
            errors.append("Password must contain at least one uppercase letter.")
        
        if not any(c.islower() for c in value):
            errors.append("Password must contain at least one lowercase letter.")
        
        if not any(c.isdigit() for c in value):
            errors.append("Password must contain at least one digit.")
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in value):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Password confirmation does not match.'
            })
        
        return data


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification
    """
    user_id = serializers.IntegerField(
        help_text="User ID from verification email"
    )
    token = serializers.CharField(
        help_text="Verification token from email link"
    )


class TwoFactorSetupSerializer(serializers.Serializer):
    """
    Serializer for 2FA setup initialization
    """
    pass  # No input required, uses authenticated user


class TwoFactorVerifySetupSerializer(serializers.Serializer):
    """
    Serializer for verifying 2FA setup
    """
    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit code from authenticator app"
    )
    
    def validate_code(self, value):
        """Clean and validate setup code."""
        return value.replace(' ', '').strip()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information
    """
    class Meta:
        model = EnterpriseUser
        fields = [
            'id', 'corporate_email', 'full_name', 'role', 'department',
            'employee_id', 'company_domain', 'is_2fa_enabled', 'email_verified',
            'created_at', 'last_login', 'last_activity'
        ]
        read_only_fields = [
            'id', 'corporate_email', 'company_domain', 'created_at',
            'last_login', 'last_activity'
        ]


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="New password"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )
    
    def validate_new_password(self, value):
        """Validate new password against enterprise policy."""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        
        # Additional enterprise validation (same as registration)
        errors = []
        
        if len(value) < 8:
            errors.append("Password must be at least 8 characters long.")
        
        if not any(c.isupper() for c in value):
            errors.append("Password must contain at least one uppercase letter.")
        
        if not any(c.islower() for c in value):
            errors.append("Password must contain at least one lowercase letter.")
        
        if not any(c.isdigit() for c in value):
            errors.append("Password must contain at least one digit.")
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in value):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Password confirmation does not match.'
            })
        
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from current password.'
            })
        
        return data


class AuthorizedDomainSerializer(serializers.ModelSerializer):
    """
    Serializer for authorized domains
    """
    class Meta:
        model = AuthorizedDomain
        fields = ['id', 'domain', 'company_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class AuditLogSerializer(serializers.Serializer):
    """
    Serializer for audit log entries (read-only)
    """
    id = serializers.IntegerField(read_only=True)
    action_type = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    ip_address = serializers.IPAddressField(read_only=True)
    user_agent = serializers.CharField(read_only=True)
    resource = serializers.CharField(read_only=True)
    method = serializers.CharField(read_only=True)
    status_code = serializers.IntegerField(read_only=True)
    details = serializers.JSONField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    country = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)


class SecurityReportSerializer(serializers.Serializer):
    """
    Serializer for security reports
    """
    period_days = serializers.IntegerField(read_only=True)
    total_events = serializers.IntegerField(read_only=True)
    suspicious_events = serializers.IntegerField(read_only=True)
    action_breakdown = serializers.DictField(read_only=True)
    severity_breakdown = serializers.DictField(read_only=True)
    generated_at = serializers.DateTimeField(read_only=True)
