"""
Enterprise Security Validators

Custom validators for enterprise security policies and domain validation.
"""

import re
import dns.resolver
from django.core.exceptions import ValidationError
from django.core.validators import BaseValidator
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.utils.translation import gettext as _
from apps.accounts.models import AuthorizedDomain, PasswordHistory


class EnterprisePasswordValidator:
    """
    Enterprise password policy validator with comprehensive security requirements.
    """
    
    def __init__(self):
        self.min_length = 8
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digits = True
        self.require_special = True
        self.special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        self.max_consecutive = 10
        self.min_unique_chars = 6
    
    def validate(self, password, user=None):
        """
        Validate password against enterprise security policy.
        
        Args:
            password: The password to validate
            user: The user instance (optional)
        
        Raises:
            ValidationError: If password doesn't meet enterprise requirements
        """
        errors = []
        
        # Length check
        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _('Password must be at least %(min_length)d characters long.'),
                    code='password_too_short',
                    params={'min_length': self.min_length},
                )
            )
        
        # Character complexity checks
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append(
                ValidationError(
                    _('Password must contain at least one uppercase letter.'),
                    code='password_no_upper',
                )
            )
        
        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append(
                ValidationError(
                    _('Password must contain at least one lowercase letter.'),
                    code='password_no_lower',
                )
            )
        
        if self.require_digits and not any(c.isdigit() for c in password):
            errors.append(
                ValidationError(
                    _('Password must contain at least one digit.'),
                    code='password_no_digit',
                )
            )
        
        if self.require_special and not any(c in self.special_chars for c in password):
            errors.append(
                ValidationError(
                    _('Password must contain at least one special character (%(chars)s).'),
                    code='password_no_special',
                    params={'chars': self.special_chars},
                )
            )
        
        # Advanced security checks
        if self._has_consecutive_chars(password):
            errors.append(
                ValidationError(
                    _('Password cannot contain more than %(max)d consecutive identical characters.'),
                    code='password_consecutive',
                    params={'max': self.max_consecutive},
                )
            )
        
        if self._count_unique_chars(password) < self.min_unique_chars:
            errors.append(
                ValidationError(
                    _('Password must contain at least %(min)d unique characters.'),
                    code='password_not_unique',
                    params={'min': self.min_unique_chars},
                )
            )
        
        # Common patterns check
        if self._contains_common_patterns(password):
            errors.append(
                ValidationError(
                    _('Password contains common patterns that are not secure.'),
                    code='password_common_pattern',
                )
            )
        
        # User-specific checks
        if user:
            if self._is_similar_to_user_info(password, user):
                errors.append(
                    ValidationError(
                        _('Password cannot be similar to your personal information.'),
                        code='password_similar_to_user',
                    )
                )
            
            if self._is_in_password_history(password, user):
                errors.append(
                    ValidationError(
                        _('Password has been used recently. Please choose a different password.'),
                        code='password_in_history',
                    )
                )
        
        if errors:
            raise ValidationError(errors)
    
    def _has_consecutive_chars(self, password):
        """Check for consecutive identical characters."""
        count = 1
        for i in range(1, len(password)):
            if password[i] == password[i-1]:
                count += 1
                if count > self.max_consecutive:
                    return True
            else:
                count = 1
        return False
    
    def _count_unique_chars(self, password):
        """Count unique characters in password."""
        return len(set(password))
    
    def _contains_common_patterns(self, password):
        """Check for common insecure patterns."""
        password_lower = password.lower()
        
        # Sequential patterns
        sequential_patterns = [
            'abcd', '1234', '4321', 'dcba',
            'qwer', 'asdf', 'zxcv', 'yuio'
        ]
        
        for pattern in sequential_patterns:
            if pattern in password_lower:
                return True
        
        # Keyboard patterns
        keyboard_patterns = [
            'qwerty', 'azerty', 'dvorak', '123456', 'password'
        ]
        
        for pattern in keyboard_patterns:
            if pattern in password_lower:
                return True
        
        return False
    
    def _is_similar_to_user_info(self, password, user):
        """Check if password is similar to user information."""
        password_lower = password.lower()
        
        # Check against user fields
        user_fields = [
            user.full_name,
            user.corporate_email.split('@')[0],  # Email username part
            user.corporate_email.split('@')[1],  # Domain part
            user.company_domain,
            user.department,
            user.employee_id or '',
        ]
        
        for field in user_fields:
            if field and len(field) > 3:  # Only check meaningful fields
                field_lower = field.lower()
                if field_lower in password_lower or password_lower in field_lower:
                    return True
        
        return False
    
    def _is_in_password_history(self, password, user):
        """Check if password was used recently."""
        if not hasattr(user, 'password_history'):
            return False
        
        from django.contrib.auth.hashers import check_password
        
        # Check last 5 passwords
        recent_passwords = user.password_history.all()[:5]
        
        for history_entry in recent_passwords:
            if check_password(password, history_entry.password_hash):
                return True
        
        return False
    
    def get_help_text(self):
        """Return help text for password requirements."""
        return _(
            'Your password must contain at least %(min_length)d characters, '
            'including uppercase and lowercase letters, digits, and special characters. '
            'It cannot contain common patterns or be similar to your personal information.'
        ) % {'min_length': self.min_length}


class CorporateDomainValidator:
    """
    Validator for corporate email domains.
    
    Ensures email domains are authorized for enterprise registration.
    """
    
    def __init__(self, require_mx_record=True):
        self.require_mx_record = require_mx_record
    
    def __call__(self, email):
        """Validate corporate email domain."""
        if '@' not in email:
            raise ValidationError(
                _('Invalid email format.'),
                code='invalid_email_format'
            )
        
        domain = email.split('@')[1].lower()
        
        # Check if domain is authorized
        if not self._is_domain_authorized(domain):
            raise ValidationError(
                _('Email domain "%(domain)s" is not authorized for registration.'),
                code='domain_not_authorized',
                params={'domain': domain}
            )
        
        # Check MX record if required
        if self.require_mx_record and not self._has_mx_record(domain):
            raise ValidationError(
                _('Email domain "%(domain)s" does not have a valid mail server.'),
                code='domain_no_mx_record',
                params={'domain': domain}
            )
    
    def _is_domain_authorized(self, domain):
        """Check if domain is in authorized domains list."""
        return AuthorizedDomain.objects.filter(
            domain=domain,
            is_active=True
        ).exists()
    
    def _has_mx_record(self, domain):
        """Check if domain has MX record (mail server)."""
        try:
            dns.resolver.resolve(domain, 'MX')
            return True
        except Exception:
            return False


class EnterpriseUsernameValidator:
    """
    Validator for enterprise usernames with security requirements.
    """
    
    def __init__(self):
        self.min_length = 3
        self.max_length = 150
        self.allowed_chars = re.compile(r'^[a-zA-Z0-9._-]+$')
        self.reserved_names = [
            'admin', 'administrator', 'root', 'system', 'user',
            'test', 'guest', 'anonymous', 'null', 'undefined'
        ]
    
    def __call__(self, username):
        """Validate username against enterprise policies."""
        # Length checks
        if len(username) < self.min_length:
            raise ValidationError(
                _('Username must be at least %(min_length)d characters long.'),
                code='username_too_short',
                params={'min_length': self.min_length}
            )
        
        if len(username) > self.max_length:
            raise ValidationError(
                _('Username cannot be longer than %(max_length)d characters.'),
                code='username_too_long',
                params={'max_length': self.max_length}
            )
        
        # Character validation
        if not self.allowed_chars.match(username):
            raise ValidationError(
                _('Username can only contain letters, numbers, periods, underscores, and hyphens.'),
                code='username_invalid_chars'
            )
        
        # Reserved names check
        if username.lower() in self.reserved_names:
            raise ValidationError(
                _('This username is reserved and cannot be used.'),
                code='username_reserved'
            )
        
        # Cannot start or end with special characters
        if username.startswith(('.', '_', '-')) or username.endswith(('.', '_', '-')):
            raise ValidationError(
                _('Username cannot start or end with periods, underscores, or hyphens.'),
                code='username_invalid_format'
            )


class IPAddressValidator:
    """
    Validator for IP address security policies.
    """
    
    def __init__(self, allow_private=True, allow_loopback=True):
        self.allow_private = allow_private
        self.allow_loopback = allow_loopback
        self.blocked_ranges = [
            # Add any blocked IP ranges here
        ]
    
    def __call__(self, ip_address):
        """Validate IP address against security policies."""
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(ip_address)
        except ValueError:
            raise ValidationError(
                _('Invalid IP address format.'),
                code='invalid_ip_format'
            )
        
        # Check private addresses
        if not self.allow_private and ip.is_private:
            raise ValidationError(
                _('Private IP addresses are not allowed.'),
                code='private_ip_not_allowed'
            )
        
        # Check loopback addresses
        if not self.allow_loopback and ip.is_loopback:
            raise ValidationError(
                _('Loopback IP addresses are not allowed.'),
                code='loopback_ip_not_allowed'
            )
        
        # Check blocked ranges
        for blocked_range in self.blocked_ranges:
            network = ipaddress.ip_network(blocked_range)
            if ip in network:
                raise ValidationError(
                    _('This IP address is in a blocked range.'),
                    code='ip_address_blocked'
                )


class FileUploadValidator:
    """
    Validator for secure file uploads with enterprise security policies.
    """
    
    def __init__(self, allowed_extensions=None, max_size=None, scan_for_malware=False):
        self.allowed_extensions = allowed_extensions or [
            'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt'
        ]
        self.max_size = max_size or 10 * 1024 * 1024  # 10MB default
        self.scan_for_malware = scan_for_malware
        
        # Dangerous file signatures to block
        self.dangerous_signatures = [
            b'\x4d\x5a',  # PE executable
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'\xca\xfe\xba\xbe',  # Java class file
            b'\x50\x4b\x03\x04',  # ZIP file (could contain executables)
        ]
    
    def __call__(self, uploaded_file):
        """Validate uploaded file against security policies."""
        # Size check
        if uploaded_file.size > self.max_size:
            raise ValidationError(
                _('File size cannot exceed %(max_size)s bytes.'),
                code='file_too_large',
                params={'max_size': self.max_size}
            )
        
        # Extension check
        if uploaded_file.name:
            extension = uploaded_file.name.split('.')[-1].lower()
            if extension not in self.allowed_extensions:
                raise ValidationError(
                    _('File type "%(extension)s" is not allowed.'),
                    code='file_type_not_allowed',
                    params={'extension': extension}
                )
        
        # Content signature check
        uploaded_file.seek(0)  # Reset file pointer
        file_header = uploaded_file.read(1024)  # Read first 1KB
        uploaded_file.seek(0)  # Reset again
        
        for signature in self.dangerous_signatures:
            if file_header.startswith(signature):
                raise ValidationError(
                    _('File appears to contain executable code and cannot be uploaded.'),
                    code='dangerous_file_content'
                )
        
        # Malware scanning (if enabled)
        if self.scan_for_malware:
            self._scan_for_malware(uploaded_file)
    
    def _scan_for_malware(self, uploaded_file):
        """Scan file for malware (placeholder for actual implementation)."""
        # In a real implementation, this would integrate with a malware
        # scanning service like ClamAV or a cloud-based scanner
        pass
