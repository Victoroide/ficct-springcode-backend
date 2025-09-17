"""
Security Configuration Model - Enterprise security settings and configuration management.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Dict, Any, List, Optional, Union
import json
import logging

logger = logging.getLogger('security')
User = get_user_model()


class SecurityConfiguration(models.Model):
    """
    Model for managing security configuration settings.
    
    Provides comprehensive security configuration management including:
    - Dynamic security policy settings
    - Environment-specific configurations
    - Audit trail for configuration changes
    - Validation and type conversion utilities
    - Configuration templates and presets
    """
    
    class SettingType(models.TextChoices):
        STRING = 'STRING', 'String'
        INTEGER = 'INTEGER', 'Integer'
        BOOLEAN = 'BOOLEAN', 'Boolean'
        JSON = 'JSON', 'JSON Object'
        LIST = 'LIST', 'List'
        FLOAT = 'FLOAT', 'Float'
    
    class Category(models.TextChoices):
        AUTHENTICATION = 'AUTHENTICATION', 'Authentication'
        AUTHORIZATION = 'AUTHORIZATION', 'Authorization'
        SESSION = 'SESSION', 'Session Management'
        RATE_LIMITING = 'RATE_LIMITING', 'Rate Limiting'
        IP_SECURITY = 'IP_SECURITY', 'IP Security'
        PASSWORD_POLICY = 'PASSWORD_POLICY', 'Password Policy'
        TWO_FACTOR = 'TWO_FACTOR', 'Two-Factor Authentication'
        AUDIT = 'AUDIT', 'Audit & Logging'
        EMAIL = 'EMAIL', 'Email Security'
        API = 'API', 'API Security'
        GENERAL = 'GENERAL', 'General Security'
    
    setting_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name of the security setting"
    )
    
    setting_value = models.TextField(
        help_text="Value of the security setting"
    )
    
    setting_type = models.CharField(
        max_length=20,
        choices=SettingType.choices,
        default=SettingType.STRING,
        help_text="Data type of the setting value"
    )
    
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.GENERAL,
        help_text="Category of the security setting"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this setting controls"
    )
    
    default_value = models.TextField(
        blank=True,
        help_text="Default value for this setting"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this setting is active"
    )
    
    is_system_setting = models.BooleanField(
        default=False,
        help_text="Whether this is a system setting (cannot be deleted)"
    )
    
    requires_restart = models.BooleanField(
        default=False,
        help_text="Whether changing this setting requires application restart"
    )
    
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Whether this setting contains sensitive information"
    )
    
    # Validation rules
    min_value = models.TextField(
        blank=True,
        help_text="Minimum allowed value (for numeric types)"
    )
    
    max_value = models.TextField(
        blank=True,
        help_text="Maximum allowed value (for numeric types)"
    )
    
    allowed_values = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed values (for enumerated types)"
    )
    
    validation_regex = models.CharField(
        max_length=500,
        blank=True,
        help_text="Regular expression for value validation"
    )
    
    # Environment and deployment
    environment = models.CharField(
        max_length=50,
        default='all',
        help_text="Target environment (production, staging, development, all)"
    )
    
    deployment_group = models.CharField(
        max_length=100,
        blank=True,
        help_text="Deployment group for this setting"
    )
    
    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this setting was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this setting was last updated"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_security_settings',
        help_text="User who created this setting"
    )
    
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_security_settings',
        help_text="User who last updated this setting"
    )
    
    # Change tracking
    previous_value = models.TextField(
        blank=True,
        help_text="Previous value before last update"
    )
    
    change_reason = models.TextField(
        blank=True,
        help_text="Reason for the last change"
    )
    
    class Meta:
        app_label = 'security'
        db_table = 'security_configuration'
        verbose_name = 'Security Configuration'
        verbose_name_plural = 'Security Configurations'
        ordering = ['category', 'setting_name']
        indexes = [
            models.Index(fields=['setting_name']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['environment']),
            models.Index(fields=['is_system_setting']),
        ]
    
    def __str__(self) -> str:
        return f"{self.setting_name}: {self.get_display_value()}"
    
    def clean(self) -> None:
        """Validate setting value based on type and constraints."""
        super().clean()
        
        # Validate setting value based on type
        try:
            self._validate_setting_value()
        except ValueError as e:
            raise ValidationError({'setting_value': str(e)})
        
        # Validate constraints
        self._validate_constraints()
    
    def _validate_setting_value(self) -> None:
        """Validate setting value based on setting type."""
        if not self.setting_value:
            return
        
        if self.setting_type == self.SettingType.INTEGER:
            int(self.setting_value)
        elif self.setting_type == self.SettingType.FLOAT:
            float(self.setting_value)
        elif self.setting_type == self.SettingType.BOOLEAN:
            self._parse_boolean_value(self.setting_value)
        elif self.setting_type == self.SettingType.JSON:
            json.loads(self.setting_value)
        elif self.setting_type == self.SettingType.LIST:
            if not self.setting_value.startswith('['):
                # Convert comma-separated string to JSON list
                items = [item.strip() for item in self.setting_value.split(',')]
                self.setting_value = json.dumps(items)
            else:
                json.loads(self.setting_value)
    
    def _validate_constraints(self) -> None:
        """Validate setting value against defined constraints."""
        # Check allowed values
        if self.allowed_values:
            current_value = self.get_typed_value()
            if current_value not in self.allowed_values:
                raise ValidationError(
                    f"Value must be one of: {', '.join(map(str, self.allowed_values))}"
                )
        
        # Check numeric constraints
        if self.setting_type in [self.SettingType.INTEGER, self.SettingType.FLOAT]:
            value = self.get_typed_value()
            
            if self.min_value:
                min_val = float(self.min_value)
                if value < min_val:
                    raise ValidationError(f"Value must be at least {min_val}")
            
            if self.max_value:
                max_val = float(self.max_value)
                if value > max_val:
                    raise ValidationError(f"Value must be at most {max_val}")
        
        # Check regex validation
        if self.validation_regex and self.setting_type == self.SettingType.STRING:
            import re
            if not re.match(self.validation_regex, self.setting_value):
                raise ValidationError("Value does not match required pattern")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to track changes."""
        if self.pk:
            # Get previous value for change tracking
            old_instance = SecurityConfiguration.objects.get(pk=self.pk)
            if old_instance.setting_value != self.setting_value:
                self.previous_value = old_instance.setting_value
        
        super().save(*args, **kwargs)
    
    def get_typed_value(self) -> Any:
        """Get setting value converted to appropriate Python type."""
        if not self.setting_value:
            return None
        
        try:
            if self.setting_type == self.SettingType.INTEGER:
                return int(self.setting_value)
            elif self.setting_type == self.SettingType.FLOAT:
                return float(self.setting_value)
            elif self.setting_type == self.SettingType.BOOLEAN:
                return self._parse_boolean_value(self.setting_value)
            elif self.setting_type == self.SettingType.JSON:
                return json.loads(self.setting_value)
            elif self.setting_type == self.SettingType.LIST:
                return json.loads(self.setting_value)
            else:
                return self.setting_value
        except (ValueError, json.JSONDecodeError):
            logger.warning(f"Failed to convert setting {self.setting_name} to type {self.setting_type}")
            return self.setting_value
    
    def get_display_value(self) -> str:
        """Get setting value for display purposes (masks sensitive values)."""
        if self.is_sensitive:
            return "***SENSITIVE***"
        
        if len(self.setting_value) > 50:
            return f"{self.setting_value[:47]}..."
        
        return self.setting_value
    
    @staticmethod
    def _parse_boolean_value(value: str) -> bool:
        """Parse boolean value from string."""
        if isinstance(value, bool):
            return value
        
        return str(value).lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    @classmethod
    def get_setting(cls, setting_name: str, default: Any = None, environment: str = None) -> Any:
        """
        Get a security setting value with proper type conversion.
        
        Args:
            setting_name: Name of the setting
            default: Default value if setting not found
            environment: Target environment filter
            
        Returns:
            Setting value converted to appropriate type
        """
        try:
            query = cls.objects.filter(setting_name=setting_name, is_active=True)
            
            # Filter by environment if specified
            if environment:
                query = query.filter(environment__in=[environment, 'all'])
            
            setting = query.first()
            
            if setting:
                return setting.get_typed_value()
            else:
                return default
                
        except Exception as e:
            logger.error(f"Error retrieving setting {setting_name}: {str(e)}")
            return default
    
    @classmethod
    def set_setting(
        cls,
        setting_name: str,
        setting_value: Any,
        setting_type: str = None,
        category: str = None,
        description: str = '',
        updated_by: User = None,
        change_reason: str = '',
        **kwargs
    ) -> 'SecurityConfiguration':
        """
        Set or update a security setting.
        
        Args:
            setting_name: Name of the setting
            setting_value: Value to set
            setting_type: Type of the setting
            category: Category of the setting
            description: Description of the setting
            updated_by: User making the change
            change_reason: Reason for the change
            **kwargs: Additional setting attributes
            
        Returns:
            SecurityConfiguration instance
        """
        # Convert value to string based on type
        if isinstance(setting_value, (list, dict)):
            str_value = json.dumps(setting_value)
            setting_type = setting_type or cls.SettingType.JSON
        elif isinstance(setting_value, bool):
            str_value = str(setting_value).lower()
            setting_type = setting_type or cls.SettingType.BOOLEAN
        elif isinstance(setting_value, int):
            str_value = str(setting_value)
            setting_type = setting_type or cls.SettingType.INTEGER
        elif isinstance(setting_value, float):
            str_value = str(setting_value)
            setting_type = setting_type or cls.SettingType.FLOAT
        else:
            str_value = str(setting_value)
            setting_type = setting_type or cls.SettingType.STRING
        
        defaults = {
            'setting_value': str_value,
            'setting_type': setting_type,
            'description': description,
            'updated_by': updated_by,
            'change_reason': change_reason,
            'is_active': True,
            **kwargs
        }
        
        if category:
            defaults['category'] = category
        
        setting, created = cls.objects.update_or_create(
            setting_name=setting_name,
            defaults=defaults
        )
        
        if not created:
            logger.info(f"Security setting updated: {setting_name} by {updated_by}")
        
        return setting
    
    @classmethod
    def get_settings_by_category(cls, category: str, environment: str = None) -> Dict[str, Any]:
        """Get all settings in a specific category."""
        query = cls.objects.filter(category=category, is_active=True)
        
        if environment:
            query = query.filter(environment__in=[environment, 'all'])
        
        return {
            setting.setting_name: setting.get_typed_value()
            for setting in query
        }
    
    @classmethod
    def get_all_settings(cls, environment: str = None, include_sensitive: bool = False) -> Dict[str, Any]:
        """Get all active settings as a dictionary."""
        query = cls.objects.filter(is_active=True)
        
        if environment:
            query = query.filter(environment__in=[environment, 'all'])
        
        if not include_sensitive:
            query = query.filter(is_sensitive=False)
        
        return {
            setting.setting_name: setting.get_typed_value()
            for setting in query
        }
    
    @classmethod
    def reset_to_defaults(cls, category: str = None) -> int:
        """Reset settings to their default values."""
        query = cls.objects.filter(is_active=True, is_system_setting=False)
        
        if category:
            query = query.filter(category=category)
        
        count = 0
        for setting in query:
            if setting.default_value:
                setting.setting_value = setting.default_value
                setting.save()
                count += 1
        
        return count
    
    @classmethod
    def export_configuration(cls, categories: List[str] = None, environment: str = None) -> Dict[str, Any]:
        """Export configuration settings for backup or migration."""
        query = cls.objects.filter(is_active=True)
        
        if categories:
            query = query.filter(category__in=categories)
        
        if environment:
            query = query.filter(environment__in=[environment, 'all'])
        
        export_data = {
            'exported_at': timezone.now().isoformat(),
            'environment': environment,
            'categories': categories,
            'settings': []
        }
        
        for setting in query:
            setting_data = {
                'name': setting.setting_name,
                'value': setting.setting_value if not setting.is_sensitive else '***SENSITIVE***',
                'type': setting.setting_type,
                'category': setting.category,
                'description': setting.description,
                'default_value': setting.default_value,
                'environment': setting.environment,
                'is_system_setting': setting.is_system_setting,
                'requires_restart': setting.requires_restart,
                'validation': {
                    'min_value': setting.min_value,
                    'max_value': setting.max_value,
                    'allowed_values': setting.allowed_values,
                    'validation_regex': setting.validation_regex
                }
            }
            export_data['settings'].append(setting_data)
        
        return export_data
    
    @classmethod
    def import_configuration(cls, config_data: Dict[str, Any], updated_by: User = None) -> Dict[str, int]:
        """Import configuration settings from exported data."""
        results = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        if 'settings' not in config_data:
            raise ValueError("Invalid configuration data format")
        
        for setting_data in config_data['settings']:
            try:
                setting_name = setting_data['name']
                
                # Skip sensitive settings in import
                if '***SENSITIVE***' in setting_data.get('value', ''):
                    results['skipped'] += 1
                    continue
                
                setting, created = cls.objects.update_or_create(
                    setting_name=setting_name,
                    defaults={
                        'setting_value': setting_data['value'],
                        'setting_type': setting_data.get('type', cls.SettingType.STRING),
                        'category': setting_data.get('category', cls.Category.GENERAL),
                        'description': setting_data.get('description', ''),
                        'default_value': setting_data.get('default_value', ''),
                        'environment': setting_data.get('environment', 'all'),
                        'is_system_setting': setting_data.get('is_system_setting', False),
                        'requires_restart': setting_data.get('requires_restart', False),
                        'min_value': setting_data.get('validation', {}).get('min_value', ''),
                        'max_value': setting_data.get('validation', {}).get('max_value', ''),
                        'allowed_values': setting_data.get('validation', {}).get('allowed_values', []),
                        'validation_regex': setting_data.get('validation', {}).get('validation_regex', ''),
                        'updated_by': updated_by,
                        'change_reason': 'Configuration import',
                        'is_active': True
                    }
                )
                
                if created:
                    results['created'] += 1
                else:
                    results['updated'] += 1
                    
            except Exception as e:
                logger.error(f"Error importing setting {setting_data.get('name', 'unknown')}: {str(e)}")
                results['errors'] += 1
        
        return results
    
    def get_setting_info(self) -> Dict[str, Any]:
        """Get comprehensive information about this setting."""
        return {
            'name': self.setting_name,
            'value': self.get_display_value(),
            'typed_value': self.get_typed_value() if not self.is_sensitive else None,
            'type': self.get_setting_type_display(),
            'category': self.get_category_display(),
            'description': self.description,
            'default_value': self.default_value,
            'is_active': self.is_active,
            'is_system_setting': self.is_system_setting,
            'is_sensitive': self.is_sensitive,
            'requires_restart': self.requires_restart,
            'environment': self.environment,
            'deployment_group': self.deployment_group,
            'constraints': {
                'min_value': self.min_value,
                'max_value': self.max_value,
                'allowed_values': self.allowed_values,
                'validation_regex': self.validation_regex
            },
            'metadata': {
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat(),
                'created_by': self.created_by.corporate_email if self.created_by else None,
                'updated_by': self.updated_by.corporate_email if self.updated_by else None,
                'previous_value': self.previous_value if not self.is_sensitive else None,
                'change_reason': self.change_reason
            }
        }
