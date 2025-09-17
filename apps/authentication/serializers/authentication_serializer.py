"""
Authentication Serializers for enterprise login, 2FA, and token management.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import EnterpriseUser
from typing import Dict, Any
import re


class LoginSerializer(serializers.Serializer):
    
    corporate_email = serializers.EmailField(
        required=True,
        help_text="Corporate email address"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="User password"
    )
    
    def validate_corporate_email(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError(_("Corporate email is required"))
        
        # Basic email format validation
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(value):
            raise serializers.ValidationError(_("Invalid email format"))
        
        # Extract domain and validate against authorized domains
        domain = value.split('@')[1].lower()
        from apps.accounts.models import AuthorizedDomain
        
        if not AuthorizedDomain.is_domain_authorized(domain):
            raise serializers.ValidationError(
                _("Domain '{}' is not authorized for access").format(domain)
            )
        
        return value.lower()
    
    def validate_password(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError(_("Password is required"))
        
        if len(value) < 8:
            raise serializers.ValidationError(
                _("Password must be at least 8 characters long")
            )
        
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        corporate_email = attrs.get('corporate_email')
        password = attrs.get('password')
        request = self.context.get('request')
        
        if not corporate_email or not password:
            raise serializers.ValidationError(
                _("Both corporate email and password are required")
            )
        
        # Get user and check existence
        try:
            user = EnterpriseUser.objects.get(corporate_email=corporate_email)
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(
                _("Invalid credentials")
            )
        
        # Check account status
        if not user.is_active:
            raise serializers.ValidationError(
                _("Account is disabled")
            )
        
        if user.is_account_locked():
            raise serializers.ValidationError(
                _("Account is temporarily locked due to failed login attempts")
            )
        
        if not user.email_verified:
            raise serializers.ValidationError(
                _("Email address not verified")
            )
        
        # Authenticate user with request parameter for django-axes
        user = authenticate(request=request, username=corporate_email, password=password)
        if not user:
            # Increment failed attempts for existing user
            try:
                existing_user = EnterpriseUser.objects.get(corporate_email=corporate_email)
                existing_user.increment_failed_attempts()
            except EnterpriseUser.DoesNotExist:
                pass
            
            raise serializers.ValidationError(
                _("Invalid credentials")
            )
        
        attrs['user'] = user
        return attrs


class TwoFactorVerifySerializer(serializers.Serializer):
    
    code = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text="6-digit TOTP code from authenticator app"
    )
    user_id = serializers.IntegerField(
        required=True,
        help_text="User ID for 2FA verification"
    )
    
    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(
                _("2FA code must contain only digits")
            )
        
        if len(value) != 6:
            raise serializers.ValidationError(
                _("2FA code must be exactly 6 digits")
            )
        
        return value
    
    def validate_user_id(self, value: int) -> int:
        try:
            user = EnterpriseUser.objects.get(id=value, is_active=True)
            if not user.is_2fa_enabled:
                raise serializers.ValidationError(
                    _("2FA is not enabled for this user")
                )
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(
                _("Invalid user")
            )
        
        return value
    
    def check_time_window(self, user: EnterpriseUser, code: str) -> bool:
        return user.verify_2fa_token(code)
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        user_id = attrs.get('user_id')
        code = attrs.get('code')
        
        try:
            user = EnterpriseUser.objects.get(id=user_id, is_active=True)
        except EnterpriseUser.DoesNotExist:
            raise serializers.ValidationError(_("Invalid user"))
        
        # Verify 2FA code
        if not self.check_time_window(user, code):
            # Check if it's a backup code
            if not user.use_backup_code(code):
                raise serializers.ValidationError(
                    _("Invalid or expired 2FA code")
                )
        
        attrs['user'] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    
    refresh_token = serializers.CharField(
        required=False,
        help_text="Refresh token to blacklist (optional)"
    )
    
    def validate_refresh_token(self, value: str) -> str:
        if value:
            try:
                refresh_token = RefreshToken(value)
                # Check if token is already blacklisted
                if refresh_token.check_blacklist():
                    raise serializers.ValidationError(
                        _("Token is already blacklisted")
                    )
            except Exception:
                raise serializers.ValidationError(
                    _("Invalid refresh token")
                )
        
        return value
    
    def blacklist_token(self, refresh_token_str: str) -> bool:
        try:
            refresh_token = RefreshToken(refresh_token_str)
            refresh_token.blacklist()
            return True
        except Exception:
            return False


class TokenRefreshSerializer(serializers.Serializer):
    
    refresh_token = serializers.CharField(
        required=True,
        help_text="Valid refresh token"
    )
    
    def validate_refresh_token(self, value: str) -> str:
        try:
            refresh_token = RefreshToken(value)
            
            # Check if token is blacklisted
            if refresh_token.check_blacklist():
                raise serializers.ValidationError(
                    _("Token is blacklisted")
                )
            
            # Get user from token and validate status
            user_id = refresh_token.payload.get('user_id')
            if user_id:
                try:
                    user = EnterpriseUser.objects.get(id=user_id)
                    if not user.is_active:
                        raise serializers.ValidationError(
                            _("User account is disabled")
                        )
                    if user.is_account_locked():
                        raise serializers.ValidationError(
                            _("User account is locked")
                        )
                except EnterpriseUser.DoesNotExist:
                    raise serializers.ValidationError(
                        _("User not found")
                    )
            
        except Exception as e:
            raise serializers.ValidationError(
                _("Invalid or expired refresh token")
            )
        
        return value
    
    def generate_new_access_token(self, refresh_token_str: str) -> Dict[str, str]:
        try:
            refresh_token = RefreshToken(refresh_token_str)
            access_token = refresh_token.access_token
            
            return {
                'access_token': str(access_token),
                'refresh_token': str(refresh_token),
                'token_type': 'Bearer',
                'expires_in': access_token.payload['exp'] - access_token.current_time
            }
        except Exception:
            raise serializers.ValidationError(
                _("Failed to generate new access token")
            )


class EnterpriseTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    username_field = 'corporate_email'
    
    @classmethod
    def get_token(cls, user: EnterpriseUser) -> RefreshToken:
        token = super().get_token(user)
        
        # Add enterprise-specific claims
        token['role'] = user.role
        token['department'] = user.department
        token['company_domain'] = user.company_domain
        token['is_2fa_enabled'] = user.is_2fa_enabled
        token['email_verified'] = user.email_verified
        token['full_name'] = user.full_name
        
        return token
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, str]:
        data = super().validate(attrs)
        
        # Add user info to response
        user = self.user
        data.update({
            'user_id': user.id,
            'corporate_email': user.corporate_email,
            'full_name': user.full_name,
            'role': user.role,
            'requires_2fa': user.is_2fa_enabled,
            'email_verified': user.email_verified,
        })
        
        return data
