"""
Password History Model for enterprise security policy compliance.
"""

from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .enterprise_user import EnterpriseUser


class PasswordHistory(models.Model):
    """
    Model to track password history for enterprise security policy.
    Prevents password reuse and maintains audit trail.
    """
    
    user = models.ForeignKey(
        'accounts.EnterpriseUser',
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_hash = models.CharField(
        max_length=128,
        help_text='Hashed password for security comparison'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this password was set'
    )
    
    class Meta:
        app_label = 'accounts'
        db_table = 'accounts_password_history'
        verbose_name = 'Password History'
        verbose_name_plural = 'Password Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self) -> str:
        return f"Password for {self.user.corporate_email} at {self.created_at}"
    
    @classmethod
    def add_password_to_history(cls, user: 'EnterpriseUser', raw_password: str) -> None:
        """
        Add a password to the user's history.
        
        Args:
            user: The EnterpriseUser instance
            raw_password: The plain text password to hash and store
        """
        password_hash = make_password(raw_password)
        cls.objects.create(
            user=user,
            password_hash=password_hash
        )
        
        # Limit history to last 12 passwords (enterprise standard)
        cls.cleanup_old_passwords(user, keep_count=12)
    
    @classmethod
    def cleanup_old_passwords(cls, user: 'EnterpriseUser', keep_count: int = 12) -> None:
        """
        Clean up old password history entries, keeping only the most recent.
        
        Args:
            user: The EnterpriseUser instance
            keep_count: Number of passwords to keep in history
        """
        old_passwords = cls.objects.filter(user=user)[keep_count:]
        for password_entry in old_passwords:
            password_entry.delete()
    
    @classmethod
    def check_password_reuse(cls, user: 'EnterpriseUser', raw_password: str, 
                           check_count: int = 12) -> bool:
        """
        Check if a password has been used recently.
        
        Args:
            user: The EnterpriseUser instance
            raw_password: The plain text password to check
            check_count: Number of recent passwords to check against
            
        Returns:
            bool: True if password has been used recently, False otherwise
        """
        recent_passwords = cls.objects.filter(user=user)[:check_count]
        
        for password_entry in recent_passwords:
            if check_password(raw_password, password_entry.password_hash):
                return True
        
        return False
    
    @classmethod
    def get_user_password_count(cls, user: 'EnterpriseUser') -> int:
        """
        Get the number of passwords stored in history for a user.
        
        Args:
            user: The EnterpriseUser instance
            
        Returns:
            int: Number of passwords in history
        """
        return cls.objects.filter(user=user).count()
    
    @classmethod
    def clear_user_history(cls, user: 'EnterpriseUser') -> int:
        """
        Clear all password history for a user.
        
        Args:
            user: The EnterpriseUser instance
            
        Returns:
            int: Number of password entries deleted
        """
        count = cls.objects.filter(user=user).count()
        cls.objects.filter(user=user).delete()
        return count
