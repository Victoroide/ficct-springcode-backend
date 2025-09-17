"""
Security Models - Refactored to use modular enterprise architecture.

This file imports individual model files for better organization and maintainability:
- IPWhitelist: IP access control and whitelisting
- SecurityConfiguration: Security settings management
"""

# Import individual models from modular structure
from .models.ip_whitelist import IPWhitelist
from .models.security_configuration import SecurityConfiguration

# Export all models for backward compatibility
__all__ = [
    'IPWhitelist',
    'SecurityConfiguration',
]
