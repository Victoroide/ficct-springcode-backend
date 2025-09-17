"""
Registration Serializers for enterprise user registration and email verification.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import EnterpriseUser, AuthorizedDomain
from typing import Dict, Any
import re
import secrets


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for enterprise user registration with domain validation.
    """
    
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Password must meet enterprise security requirements"
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="Password confirmation"
    )
    
    class Meta:
        model = EnterpriseUser
        fields = [
            'corporate_email',
            'full_name',
            'role',
            'department',
            'password',
            'password_confirm'
        ]
        extra_kwargs = {
            'corporate_email': {
                'help_text': 'Corporate email address (must be from authorized domain)'
            },
            'full_name': {
                'help_text': 'Full name of the employee'
            },
            'role': {
                'help_text': 'Professional role in the organization'
            },
            'department': {
                'help_text': 'Department or division within the company'
            },
        }
    
    def validate_corporate_email(self, value: str) -> str:
        """
        Validate corporate email format and domain authorization.
        """
        if not value:
            raise serializers.ValidationError(_("Corporate email is required"))
        
        # Basic email format validation
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(value):
            raise serializers.ValidationError(_("Invalid email format"))
        
        # Check if email already exists
        if EnterpriseUser.objects.filter(corporate_email=value.lower()).exists():
            raise serializers.ValidationError(
                _("User with this email already exists")
            )
        
        return value.lower()
    
    def validate_corporate_domain(self, email: str) -> bool:
        """
        Validate if the email domain is authorized for registration.
        """
        if not email or '@' not in email:
            raise serializers.ValidationError(_('Invalid email format'))
        
        domain = email.split('@')[1].lower()
        
        # Check if domain is authorized in the database
        is_authorized = AuthorizedDomain.objects.filter(
            domain=domain, 
            is_active=True
        ).exists()
        
        if not is_authorized:
            # DRF ValidationError doesn't support params argument, format the string directly
            error_message = _('Email domain "{}" is not authorized for registration.').format(domain)
            raise serializers.ValidationError(error_message)
        
        return True
    
    def validate_password_strength(self, password: str) -> None:
        """
        Validate password meets enterprise strength requirements.
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            errors.append("Password must contain at least one special character")
        
        if errors:
            raise serializers.ValidationError(errors)
    
    def validate_role(self, value: str) -> str:
        """
        Validate user role is allowed for registration.
        """
        if not value:
            raise serializers.ValidationError(_("Role is required"))
        
        # Don't allow direct registration as SUPER_ADMIN
        if value == EnterpriseUser.UserRole.SUPER_ADMIN:
            raise serializers.ValidationError(
                _("Super Administrator role cannot be assigned through registration")
            )
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate registration data including password confirmation and domain.
        """
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        corporate_email = attrs.get('corporate_email')
        
        # Password confirmation check
        if password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': _("Passwords do not match")
            })
        
        # Password strength validation
        if password:
            self.validate_password_strength(password)
            
            # Django's built-in password validation
            try:
                validate_password(password)
            except ValidationError as e:
                raise serializers.ValidationError({
                    'password': list(e.messages)
                })
        
        # Corporate domain validation
        if corporate_email and not self.validate_corporate_domain(corporate_email):
            raise serializers.ValidationError({
                'corporate_email': _(
                    "Email domain is not authorized for registration. "
                    "Please contact your system administrator."
                )
            })
        
        # Remove password_confirm from validated data
        attrs.pop('password_confirm', None)
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> EnterpriseUser:
        """
        Create enterprise user with proper password handling and domain assignment.
        """
        password = validated_data.pop('password')
        corporate_email = validated_data['corporate_email']
        
        # Extract and set company domain
        domain = corporate_email.split('@')[1].lower()
        validated_data['company_domain'] = domain
        
        # Create user
        user = EnterpriseUser(**validated_data)
        user.set_password(password)
        user.is_active = False  # Require email verification
        user.email_verified = False
        
        # Generate email verification token
        user.generate_email_verification_token()
        
        # Set password expiry
        user.set_password_expiry()
        
        user.save()
        
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification with token validation.
    """
    
    verification_token = serializers.CharField(
        required=True,
        help_text="Email verification token sent to user's email"
    )
    email = serializers.EmailField(
        required=True,
        help_text="Corporate email address to verify"
    )
    
    def validate_verification_token(self, value: str) -> str:
        """
        Validate verification token format and existence.
        """
        if not value:
            raise serializers.ValidationError(_("Verification token is required"))
        
        if len(value) < 32:
            raise serializers.ValidationError(_("Invalid verification token format"))
        
        return value
    
    def validate_email(self, value: str) -> str:
        """
        Validate email exists and is not already verified.
        """
        try:
            user = EnterpriseUser.objects.get(corporate_email=value.lower())
            if user.email_verified:
                raise serializers.ValidationError(
                    _("Email is already verified")
                )
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(
                _("User with this email does not exist")
            )
        
        return value.lower()
    
    def activate_user(self, email: str, token: str) -> EnterpriseUser:
        """
        Activate user account after successful email verification.
        """
        try:
            user = EnterpriseUser.objects.get(corporate_email=email)
            
            if user.verify_email_with_token(token):
                user.is_active = True
                user.save(update_fields=['is_active'])
                return user
            else:
                raise serializers.ValidationError(
                    _("Invalid or expired verification token")
                )
                
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(_("User not found"))
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate email verification token against user account.
        """
        email = attrs.get('email')
        token = attrs.get('verification_token')
        
        try:
            user = EnterpriseUser.objects.get(corporate_email=email)
            
            if user.email_verification_token != token:
                raise serializers.ValidationError(
                    _("Invalid verification token")
                )
            
            if user.email_verified:
                raise serializers.ValidationError(
                    _("Email is already verified")
                )
            
            attrs['user'] = user
            
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(_("User not found"))
        
        return attrs


class Setup2FASerializer(serializers.Serializer):
    """
    Serializer for setting up 2FA with QR code verification.
    """
    
    qr_secret = serializers.CharField(
        required=True,
        help_text="Base32 secret key for TOTP setup"
    )
    verification_code = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text="6-digit TOTP verification code"
    )
    
    def validate_qr_secret(self, value: str) -> str:
        """
        Validate QR secret format.
        """
        if not value:
            raise serializers.ValidationError(_("QR secret is required"))
        
        # Base32 validation (only A-Z and 2-7)
        import re
        if not re.match(r'^[A-Z2-7]+$', value):
            raise serializers.ValidationError(
                _("Invalid QR secret format")
            )
        
        return value
    
    def validate_verification_code(self, value: str) -> str:
        """
        Validate TOTP verification code format.
        """
        if not value.isdigit():
            raise serializers.ValidationError(
                _("Verification code must contain only digits")
            )
        
        if len(value) != 6:
            raise serializers.ValidationError(
                _("Verification code must be exactly 6 digits")
            )
        
        return value
    
    def validate_totp_code(self, secret: str, code: str) -> bool:
        """
        Validate TOTP code against the provided secret.
        """
        import pyotp
        
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False
    
    def enable_2fa(self, user: EnterpriseUser, secret: str) -> Dict[str, Any]:
        """
        Enable 2FA for user and generate backup codes.
        """
        user.two_factor_secret = secret
        user.enable_2fa()
        
        # Generate backup codes
        backup_codes = user.generate_backup_codes()
        
        return {
            'success': True,
            'backup_codes': backup_codes,
            'message': '2FA enabled successfully'
        }
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate 2FA setup with secret and verification code.
        """
        secret = attrs.get('qr_secret')
        code = attrs.get('verification_code')
        
        if not self.validate_totp_code(secret, code):
            raise serializers.ValidationError(
                _("Invalid verification code. Please check your authenticator app.")
            )
        
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    """
    Serializer for resending email verification.
    """
    
    corporate_email = serializers.EmailField(
        required=True,
        help_text="Corporate email address to resend verification to"
    )
    
    def validate_corporate_email(self, value: str) -> str:
        """
        Validate email exists and needs verification.
        """
        try:
            user = EnterpriseUser.objects.get(corporate_email=value.lower())
            
            if user.email_verified:
                raise serializers.ValidationError(
                    _("Email is already verified")
                )
            
            if not user.is_active:
                # This is expected for unverified users
                pass
            
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(
                _("User with this email does not exist")
            )
        
        return value.lower()
    
    def get_user(self, email: str) -> EnterpriseUser:
        """
        Get user by email for verification resend.
        """
        try:
            return EnterpriseUser.objects.get(corporate_email=email)
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(_("User not found"))
