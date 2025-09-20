"""
Enterprise User Model with corporate authentication and security features.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import EmailValidator
from django.utils import timezone
from datetime import timedelta
import secrets
import pyotp
from typing import Optional, Tuple, List, Dict


class EnterpriseUser(AbstractUser):
    """
    Enterprise User Model with corporate authentication and security features.
    Extends Django's AbstractUser with enterprise-specific fields and methods.
    """
    
    class UserRole(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Administrator'
        ADMIN = 'ADMIN', 'Administrator'
        MANAGER = 'MANAGER', 'Manager'
        DEVELOPER = 'DEVELOPER', 'Developer'
        ANALYST = 'ANALYST', 'Business Analyst'
    
    # Override username to use email as primary identifier
    username = None
    
    # Corporate Identity Fields
    corporate_email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text='Corporate email address used for authentication'
    )
    full_name = models.CharField(
        max_length=150,
        help_text='Full name of the employee'
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.DEVELOPER,
        help_text='Professional role in the organization'
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text='Department or division within the company'
    )
    company_domain = models.CharField(
        max_length=100,
        help_text='Domain of the company (e.g., company.com)'
    )
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text='Company employee ID number'
    )
    
    # Security Fields
    two_factor_secret = models.CharField(
        max_length=32,
        blank=True,
        help_text='Secret key for TOTP 2FA authentication'
    )
    is_2fa_enabled = models.BooleanField(
        default=False,
        help_text='Whether 2FA is enabled for this user'
    )
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of consecutive failed login attempts'
    )
    account_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Account is locked until this datetime'
    )
    password_changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When password was last changed'
    )
    password_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When current password expires'
    )
    backup_codes = models.JSONField(
        default=list,
        blank=True,
        help_text='Backup codes for 2FA recovery'
    )
    
    # Audit Fields
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of last successful login'
    )
    last_login_user_agent = models.TextField(
        blank=True,
        help_text='User agent string of last login'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Account creation timestamp'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Last profile update timestamp'
    )
    email_verified = models.BooleanField(
        default=False,
        help_text='Whether corporate email has been verified'
    )
    email_verification_token = models.CharField(
        max_length=64,
        blank=True,
        help_text='Token for email verification'
    )
    
    # Activity tracking
    last_activity = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last recorded user activity'
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text='Current session key'
    )
    
    USERNAME_FIELD = 'corporate_email'
    REQUIRED_FIELDS = ['full_name', 'role']
    
    class Meta:
        app_label = 'accounts'
        verbose_name = 'Enterprise User'
        verbose_name_plural = 'Enterprise Users'
        db_table = 'accounts_enterprise_user'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['corporate_email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_2fa_enabled']),
            models.Index(fields=['email_verified']),
            models.Index(fields=['last_login']),
            models.Index(fields=['password_expires_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.full_name} ({self.corporate_email})"
    
    def validate_corporate_domain(self) -> bool:
        """
        Validate if the user's email domain is authorized for registration.
        """
        if not self.corporate_email:
            return False
            
        domain = self.corporate_email.split('@')[1].lower()
        self.company_domain = domain
        
        return True
    
    def check_password_policy(self, raw_password: str) -> Tuple[bool, List[str]]:
        """
        Check if password meets enterprise policy requirements.
        Returns (is_valid, errors)
        """
        errors = []
        
        # Length check
        if len(raw_password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        # Complexity checks
        if not any(c.isupper() for c in raw_password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in raw_password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in raw_password):
            errors.append("Password must contain at least one digit")
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in raw_password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    def generate_2fa_secret(self) -> str:
        """
        Generate a new TOTP secret for 2FA setup.
        """
        secret = pyotp.random_base32()
        self.two_factor_secret = secret
        return secret
    
    def get_2fa_qr_uri(self) -> str:
        """
        Generate provisioning URI for 2FA QR code setup.
        """
        if not self.two_factor_secret:
            self.generate_2fa_secret()
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.provisioning_uri(
            name=self.corporate_email,
            issuer_name="FICCT Enterprise"
        )
    
    def verify_2fa_token(self, token: str) -> bool:
        """
        Verify a 2FA token against the user's secret.
        """
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token, valid_window=1)  # Allow 30s window
    
    def enable_2fa(self) -> None:
        """
        Enable 2FA for the user.
        """
        self.is_2fa_enabled = True
        self.save(update_fields=['is_2fa_enabled'])
    
    def disable_2fa(self) -> None:
        """
        Disable 2FA for the user.
        """
        self.is_2fa_enabled = False
        self.two_factor_secret = ''
        self.backup_codes = []
        self.save(update_fields=['is_2fa_enabled', 'two_factor_secret', 'backup_codes'])
    
    def generate_backup_codes(self, count: int = 8) -> List[str]:
        """
        Generate backup codes for 2FA recovery.
        """
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes = codes
        self.save(update_fields=['backup_codes'])
        return codes
    
    def use_backup_code(self, code: str) -> bool:
        """
        Use a backup code and remove it from available codes.
        """
        if code.upper() in self.backup_codes:
            self.backup_codes.remove(code.upper())
            self.save(update_fields=['backup_codes'])
            return True
        return False
    
    def is_account_locked(self) -> bool:
        """
        Check if account is currently locked due to failed attempts.
        """
        if not self.account_locked_until:
            return False
        return timezone.now() < self.account_locked_until
    
    def lock_account(self, duration_minutes: int = 15) -> None:
        """
        Lock the account for specified duration.
        """
        self.account_locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['account_locked_until'])
    
    def unlock_account(self) -> None:
        """
        Unlock the account and reset failed attempts.
        """
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['account_locked_until', 'failed_login_attempts'])
    
    def increment_failed_attempts(self) -> None:
        """
        Increment failed login attempts and lock if threshold reached.
        """
        from django.conf import settings
        
        self.failed_login_attempts += 1
        
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        lockout_duration = getattr(settings, 'ACCOUNT_LOCKOUT_DURATION_MINUTES', 15)
        
        if self.failed_login_attempts >= max_attempts:
            self.lock_account(lockout_duration)
        
        self.save(update_fields=['failed_login_attempts'])
    
    def reset_failed_attempts(self) -> None:
        """
        Reset failed login attempts counter.
        """
        self.failed_login_attempts = 0
        self.save(update_fields=['failed_login_attempts'])
    
    def is_password_expired(self) -> bool:
        """
        Check if current password has expired.
        """
        if not self.password_expires_at:
            return False
        return timezone.now() > self.password_expires_at
    
    def set_password_expiry(self) -> None:
        """
        Set password expiry date based on enterprise policy.
        """
        from django.conf import settings
        
        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        self.password_expires_at = timezone.now() + timedelta(days=expiry_days)
        self.password_changed_at = timezone.now()
        self.save(update_fields=['password_expires_at', 'password_changed_at'])
    
    def generate_email_verification_token(self) -> str:
        """
        Generate a token for email verification.
        """
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        
        if self.pk:
            self.save(update_fields=['email_verification_token'])
        else:
            self.save()
            
        return token
    
    def verify_email_with_token(self, token: str) -> bool:
        """
        Verify email with provided token.
        """
        if self.email_verification_token == token:
            self.email_verified = True
            self.email_verification_token = ''
            self.save(update_fields=['email_verified', 'email_verification_token'])
            return True
        return False
    
    def update_last_activity(self) -> None:
        """
        Update last activity timestamp.
        """
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def update_login_info(self, ip_address: str, user_agent: str) -> None:
        """
        Update login information.
        """
        self.last_login_ip = ip_address
        self.last_login_user_agent = user_agent
        self.last_login = timezone.now()
        self.save(update_fields=['last_login_ip', 'last_login_user_agent', 'last_login'])
    
    def get_permissions_dict(self) -> Dict:
        """
        Get user permissions as dictionary for JWT claims.
        """
        return {
            'role': self.role,
            'department': self.department,
            'company_domain': self.company_domain,
            'is_2fa_enabled': self.is_2fa_enabled,
            'email_verified': self.email_verified,
            'is_staff': self.is_staff,
            'is_superuser': self.is_superuser,
        }
