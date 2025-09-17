"""
Audit Models - Refactored to use modular enterprise architecture.

This file imports individual model files for better organization and maintainability:
- AuditLog: Core audit logging functionality
- SecurityAlert: Security incident management
"""

# Import individual models from modular structure
from .models.audit_log import AuditLog
from .models.security_alert import SecurityAlert

# Export all models for backward compatibility
__all__ = [
    'AuditLog',
    'SecurityAlert',
]
