"""
IP Whitelist Model - Enterprise IP access control and whitelisting management.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import validate_ipv4_address, validate_ipv6_address
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import Dict, Any, List, Optional
import ipaddress
import logging

logger = logging.getLogger('security')
User = get_user_model()


class IPWhitelist(models.Model):
    """
    Model for managing IP addresses that have special access privileges.
    
    Provides comprehensive IP-based access control including:
    - Multiple access levels (Admin, API, Full, Limited)
    - Path-specific access restrictions
    - Usage tracking and analytics
    - Network range support
    - Geolocation validation
    """
    
    class AccessLevel(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin Access'
        API = 'API', 'API Access'
        FULL = 'FULL', 'Full Access'
        LIMITED = 'LIMITED', 'Limited Access'
        READONLY = 'READONLY', 'Read-Only Access'
    
    ip_address = models.GenericIPAddressField(
        unique=True,
        help_text="IPv4 or IPv6 address to whitelist"
    )
    
    description = models.CharField(
        max_length=255,
        help_text="Description of this IP address or its purpose"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this IP whitelist entry is active"
    )
    
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.LIMITED,
        help_text="Level of access granted to this IP"
    )
    
    allowed_paths = models.JSONField(
        default=list,
        blank=True,
        help_text="Specific paths this IP can access (empty = all paths)"
    )
    
    blocked_paths = models.JSONField(
        default=list,
        blank=True,
        help_text="Specific paths this IP cannot access"
    )
    
    # Network range support
    is_network_range = models.BooleanField(
        default=False,
        help_text="Whether this entry represents a network range (CIDR)"
    )
    
    network_mask = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Network mask for CIDR notation (e.g., 24 for /24)"
    )
    
    # Geographic restrictions
    allowed_countries = models.JSONField(
        default=list,
        blank=True,
        help_text="Country codes allowed for this IP (empty = all countries)"
    )
    
    # Time-based restrictions
    access_start_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time for daily access window"
    )
    
    access_end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="End time for daily access window"
    )
    
    timezone_name = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Timezone for time-based restrictions"
    )
    
    # Rate limiting
    max_requests_per_hour = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum requests per hour from this IP"
    )
    
    max_concurrent_sessions = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum concurrent sessions from this IP"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ip_whitelists',
        help_text="User who created this whitelist entry"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this entry was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this entry was last updated"
    )
    
    # Usage tracking
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this IP was used for access"
    )
    
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times this IP has been used"
    )
    
    last_user_agent = models.TextField(
        blank=True,
        help_text="Last user agent seen from this IP"
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this whitelist entry expires (null = never)"
    )
    
    # Security flags
    is_trusted = models.BooleanField(
        default=False,
        help_text="Whether this IP is considered fully trusted"
    )
    
    requires_2fa = models.BooleanField(
        default=True,
        help_text="Whether users from this IP must use 2FA"
    )
    
    bypass_rate_limits = models.BooleanField(
        default=False,
        help_text="Whether this IP can bypass standard rate limits"
    )
    
    class Meta:
        app_label = 'security'
        db_table = 'security_ip_whitelist'
        verbose_name = 'IP Whitelist Entry'
        verbose_name_plural = 'IP Whitelist Entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_active', 'access_level']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['last_used']),
        ]
    
    def __str__(self) -> str:
        return f"{self.ip_address} - {self.get_access_level_display()}"
    
    def clean(self) -> None:
        """Validate IP address format and network configuration."""
        super().clean()
        
        if self.ip_address:
            try:
                ip = ipaddress.ip_address(self.ip_address)
                
                # Validate network mask for network ranges
                if self.is_network_range:
                    if not self.network_mask:
                        raise ValidationError({
                            'network_mask': 'Network mask is required for network ranges'
                        })
                    
                    # Check valid mask range
                    max_mask = 32 if ip.version == 4 else 128
                    if self.network_mask > max_mask or self.network_mask < 1:
                        raise ValidationError({
                            'network_mask': f'Network mask must be between 1 and {max_mask}'
                        })
                
            except ValueError:
                raise ValidationError({
                    'ip_address': 'Invalid IP address format'
                })
        
        # Validate time restrictions
        if self.access_start_time and self.access_end_time:
            if self.access_start_time >= self.access_end_time:
                raise ValidationError({
                    'access_end_time': 'End time must be after start time'
                })
    
    def is_ip_allowed(self, ip_address: str, path: str = None, country_code: str = None) -> bool:
        """
        Check if the given IP address matches this whitelist entry with comprehensive validation.
        
        Args:
            ip_address: IP address to check
            path: Optional path to check against allowed/blocked paths
            country_code: Optional country code for geographic validation
            
        Returns:
            bool: True if IP is allowed, False otherwise
        """
        try:
            # Basic active check
            if not self.is_active:
                return False
            
            # Check expiration
            if self.expires_at and timezone.now() > self.expires_at:
                return False
            
            # IP address matching
            if not self._matches_ip_address(ip_address):
                return False
            
            # Path-based access control
            if path and not self._is_path_allowed(path):
                return False
            
            # Geographic restrictions
            if country_code and not self._is_country_allowed(country_code):
                return False
            
            # Time-based restrictions
            if not self._is_time_allowed():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"IP whitelist check error for {ip_address}: {str(e)}")
            return False
    
    def _matches_ip_address(self, ip_address: str) -> bool:
        """Check if IP address matches this whitelist entry."""
        try:
            check_ip = ipaddress.ip_address(ip_address)
            
            if self.is_network_range and self.network_mask:
                # Check against network range
                whitelist_network = ipaddress.ip_network(
                    f"{self.ip_address}/{self.network_mask}",
                    strict=False
                )
                return check_ip in whitelist_network
            else:
                # Direct IP match
                whitelist_ip = ipaddress.ip_address(self.ip_address)
                return whitelist_ip == check_ip
                
        except ValueError:
            return False
    
    def _is_path_allowed(self, path: str) -> bool:
        """Check if path is allowed based on allowed/blocked paths."""
        # Check blocked paths first
        if self.blocked_paths:
            for blocked_path in self.blocked_paths:
                if path.startswith(blocked_path):
                    return False
        
        # If no allowed paths specified, all paths are allowed
        if not self.allowed_paths:
            return True
        
        # Check allowed paths
        for allowed_path in self.allowed_paths:
            if path.startswith(allowed_path):
                return True
        
        return False
    
    def _is_country_allowed(self, country_code: str) -> bool:
        """Check if country is allowed."""
        if not self.allowed_countries:
            return True
        
        return country_code.upper() in [c.upper() for c in self.allowed_countries]
    
    def _is_time_allowed(self) -> bool:
        """Check if current time is within allowed access window."""
        if not (self.access_start_time and self.access_end_time):
            return True
        
        try:
            import pytz
            tz = pytz.timezone(self.timezone_name)
            current_time = timezone.now().astimezone(tz).time()
            
            return self.access_start_time <= current_time <= self.access_end_time
        except Exception:
            # If timezone handling fails, allow access
            return True
    
    def update_usage(self, user_agent: str = '', increment: int = 1) -> None:
        """Update usage tracking information."""
        self.last_used = timezone.now()
        self.usage_count += increment
        if user_agent:
            self.last_user_agent = user_agent[:500]  # Limit length
        
        self.save(update_fields=['last_used', 'usage_count', 'last_user_agent'])
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information for this IP whitelist entry."""
        try:
            if self.is_network_range and self.network_mask:
                network = ipaddress.ip_network(
                    f"{self.ip_address}/{self.network_mask}",
                    strict=False
                )
                return {
                    'network': str(network),
                    'network_address': str(network.network_address),
                    'broadcast_address': str(network.broadcast_address),
                    'num_addresses': network.num_addresses,
                    'is_private': network.is_private,
                    'is_multicast': network.is_multicast,
                    'version': network.version
                }
            else:
                ip = ipaddress.ip_address(self.ip_address)
                return {
                    'ip_address': str(ip),
                    'is_private': ip.is_private,
                    'is_multicast': ip.is_multicast,
                    'is_loopback': ip.is_loopback,
                    'version': ip.version
                }
        except ValueError:
            return {'error': 'Invalid IP address or network configuration'}
    
    def get_access_summary(self) -> Dict[str, Any]:
        """Get comprehensive access summary for this whitelist entry."""
        return {
            'ip_address': self.ip_address,
            'description': self.description,
            'access_level': self.get_access_level_display(),
            'is_active': self.is_active,
            'is_trusted': self.is_trusted,
            'requires_2fa': self.requires_2fa,
            'is_network_range': self.is_network_range,
            'network_info': self.get_network_info(),
            'allowed_paths': self.allowed_paths,
            'blocked_paths': self.blocked_paths,
            'allowed_countries': self.allowed_countries,
            'time_restrictions': {
                'start_time': self.access_start_time.isoformat() if self.access_start_time else None,
                'end_time': self.access_end_time.isoformat() if self.access_end_time else None,
                'timezone': self.timezone_name
            },
            'rate_limits': {
                'max_requests_per_hour': self.max_requests_per_hour,
                'max_concurrent_sessions': self.max_concurrent_sessions,
                'bypass_rate_limits': self.bypass_rate_limits
            },
            'usage': {
                'last_used': self.last_used.isoformat() if self.last_used else None,
                'usage_count': self.usage_count,
                'last_user_agent': self.last_user_agent
            },
            'expiration': {
                'expires_at': self.expires_at.isoformat() if self.expires_at else None,
                'is_expired': self.is_expired()
            },
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by.corporate_email if self.created_by else None
        }
    
    def is_expired(self) -> bool:
        """Check if this whitelist entry has expired."""
        return self.expires_at and timezone.now() > self.expires_at
    
    def extend_expiration(self, days: int) -> None:
        """Extend the expiration date by specified number of days."""
        from datetime import timedelta
        
        if self.expires_at:
            self.expires_at += timedelta(days=days)
        else:
            self.expires_at = timezone.now() + timedelta(days=days)
        
        self.save(update_fields=['expires_at'])
    
    @classmethod
    def check_ip_access(
        cls,
        ip_address: str,
        path: str = None,
        country_code: str = None,
        access_level: str = None
    ) -> Optional['IPWhitelist']:
        """
        Check if an IP address has access based on whitelist entries.
        
        Args:
            ip_address: IP address to check
            path: Optional path to check
            country_code: Optional country code
            access_level: Minimum required access level
            
        Returns:
            IPWhitelist instance if allowed, None if not allowed
        """
        # Get all active whitelist entries
        entries = cls.objects.filter(is_active=True)
        
        if access_level:
            # Filter by minimum access level
            level_hierarchy = {
                cls.AccessLevel.READONLY: 1,
                cls.AccessLevel.LIMITED: 2,
                cls.AccessLevel.API: 3,
                cls.AccessLevel.FULL: 4,
                cls.AccessLevel.ADMIN: 5
            }
            
            min_level = level_hierarchy.get(access_level, 1)
            entries = entries.filter(
                access_level__in=[
                    level for level, value in level_hierarchy.items()
                    if value >= min_level
                ]
            )
        
        # Check each entry
        for entry in entries:
            if entry.is_ip_allowed(ip_address, path, country_code):
                entry.update_usage()
                return entry
        
        return None
    
    @classmethod
    def get_usage_statistics(cls, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for IP whitelist entries."""
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        entries = cls.objects.filter(is_active=True)
        used_entries = entries.filter(last_used__gte=start_date)
        
        return {
            'total_entries': entries.count(),
            'used_entries': used_entries.count(),
            'unused_entries': entries.filter(last_used__isnull=True).count(),
            'expired_entries': entries.filter(
                expires_at__lte=timezone.now()
            ).count(),
            'by_access_level': {
                level[0]: entries.filter(access_level=level[0]).count()
                for level in cls.AccessLevel.choices
            },
            'top_used_entries': list(
                entries.order_by('-usage_count')[:10].values(
                    'ip_address', 'description', 'usage_count', 'last_used'
                )
            ),
            'network_ranges': entries.filter(is_network_range=True).count(),
            'trusted_ips': entries.filter(is_trusted=True).count(),
            'period_days': days
        }
