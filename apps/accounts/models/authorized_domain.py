"""
Authorized Domain Model for corporate domain validation.
"""

from django.db import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .enterprise_user import EnterpriseUser


class AuthorizedDomain(models.Model):
    """
    Model to store authorized corporate domains for user registration.
    Only users with emails from these domains can register.
    """
    
    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text='Authorized domain (e.g., company.com)'
    )
    company_name = models.CharField(
        max_length=200,
        help_text='Name of the company'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this domain is currently active'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When domain was added'
    )
    created_by = models.ForeignKey(
        'accounts.EnterpriseUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_domains',
        help_text='User who added this domain'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When domain was last updated'
    )
    
    class Meta:
        app_label = 'accounts'
        verbose_name = 'Authorized Domain'
        verbose_name_plural = 'Authorized Domains'
        db_table = 'accounts_authorized_domain'
        ordering = ['domain']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.company_name} ({self.domain})"
    
    def activate(self) -> None:
        """
        Activate this domain for user registration.
        """
        self.is_active = True
        self.save(update_fields=['is_active'])
    
    def deactivate(self) -> None:
        """
        Deactivate this domain to prevent new registrations.
        """
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    @classmethod
    def is_domain_authorized(cls, domain: str) -> bool:
        """
        Check if a domain is authorized for registration.
        
        Args:
            domain: Domain to check (e.g., 'company.com')
            
        Returns:
            bool: True if domain is authorized and active
        """
        return cls.objects.filter(
            domain=domain.lower(),
            is_active=True
        ).exists()
    
    @classmethod
    def get_active_domains(cls):
        """
        Get all active authorized domains.
        
        Returns:
            QuerySet of active AuthorizedDomain objects
        """
        return cls.objects.filter(is_active=True).order_by('domain')
