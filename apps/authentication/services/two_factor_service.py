"""
Two-Factor Authentication Service - Business logic for enterprise 2FA management.
"""

from django.utils import timezone
from apps.accounts.models import EnterpriseUser
from typing import Dict, Any, List, Optional
import pyotp
import qrcode
import io
import base64
import secrets
import logging

logger = logging.getLogger('authentication')


class TwoFactorService:
    """
    Service class for handling enterprise Two-Factor Authentication.
    
    Implements:
    - TOTP secret generation and management
    - QR code generation for authenticator apps
    - Backup code generation and validation
    - 2FA verification and validation
    - 2FA recovery processes
    """
    
    def __init__(self):
        self.issuer_name = 'FICCT Enterprise'
        self.backup_code_count = 8
        self.backup_code_length = 8
    
    def generate_secret_key(self) -> str:
        """
        Generate a new Base32 secret key for TOTP.
        
        Returns:
            str: Base32 encoded secret key
        """
        return pyotp.random_base32()
    
    def generate_qr_code_data(self, user: EnterpriseUser, secret: Optional[str] = None) -> Dict[str, str]:
        """
        Generate QR code data for TOTP setup.
        
        Args:
            user: EnterpriseUser instance
            secret: Optional secret key, generates new one if not provided
            
        Returns:
            Dict containing QR code URI, secret, and Base64 image data
        """
        try:
            if not secret:
                secret = self.generate_secret_key()
                user.two_factor_secret = secret
                user.save(update_fields=['two_factor_secret'])
            
            # Generate provisioning URI
            totp = pyotp.TOTP(secret)
            qr_uri = totp.provisioning_uri(
                name=user.corporate_email,
                issuer_name=self.issuer_name
            )
            
            # Generate QR code image
            qr_image_data = self._generate_qr_code_image(qr_uri)
            
            return {
                'secret': secret,
                'qr_uri': qr_uri,
                'qr_image_base64': qr_image_data,
                'issuer': self.issuer_name,
                'account_name': user.corporate_email
            }
            
        except Exception as e:
            logger.error(f"QR code generation error for user {user.id}: {str(e)}")
            raise ValueError("Failed to generate QR code data")
    
    def _generate_qr_code_image(self, qr_uri: str) -> str:
        """
        Generate QR code image as Base64 string.
        
        Args:
            qr_uri: TOTP provisioning URI
            
        Returns:
            str: Base64 encoded QR code image
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_uri)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to Base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            image_data = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{image_data}"
            
        except Exception as e:
            logger.error(f"QR code image generation error: {str(e)}")
            return ""
    
    def verify_totp_code(self, secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verify TOTP code against secret.
        
        Args:
            secret: Base32 encoded secret key
            code: 6-digit TOTP code
            valid_window: Number of time steps to allow (default: 1 = ±30 seconds)
            
        Returns:
            bool: True if code is valid, False otherwise
        """
        try:
            if not secret or not code:
                return False
            
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=valid_window)
            
        except Exception as e:
            logger.error(f"TOTP verification error: {str(e)}")
            return False
    
    def generate_backup_codes(self, user: EnterpriseUser, count: Optional[int] = None) -> List[str]:
        """
        Generate backup codes for 2FA recovery.
        
        Args:
            user: EnterpriseUser instance
            count: Number of backup codes to generate
            
        Returns:
            List of backup codes
        """
        try:
            if count is None:
                count = self.backup_code_count
            
            # Generate random backup codes
            codes = []
            for _ in range(count):
                code = secrets.token_hex(self.backup_code_length // 2).upper()
                # Format as XXXX-XXXX for readability
                formatted_code = f"{code[:4]}-{code[4:8]}"
                codes.append(formatted_code)
            
            # Save codes to user
            user.backup_codes = codes
            user.save(update_fields=['backup_codes'])
            
            logger.info(f"Generated {count} backup codes for user {user.corporate_email}")
            
            return codes
            
        except Exception as e:
            logger.error(f"Backup code generation error for user {user.id}: {str(e)}")
            raise ValueError("Failed to generate backup codes")
    
    def validate_backup_code(self, user: EnterpriseUser, code: str) -> bool:
        """
        Validate and consume a backup code.
        
        Args:
            user: EnterpriseUser instance
            code: Backup code to validate
            
        Returns:
            bool: True if code is valid and consumed, False otherwise
        """
        try:
            if not code or not user.backup_codes:
                return False
            
            # Normalize code format
            normalized_code = code.replace('-', '').replace(' ', '').upper()
            
            # Check all backup codes
            for backup_code in user.backup_codes:
                normalized_backup = backup_code.replace('-', '').replace(' ', '').upper()
                if normalized_code == normalized_backup:
                    # Remove used code
                    user.backup_codes.remove(backup_code)
                    user.save(update_fields=['backup_codes'])
                    
                    logger.info(f"Backup code used for user {user.corporate_email}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Backup code validation error for user {user.id}: {str(e)}")
            return False
    
    def enable_2fa_for_user(self, user: EnterpriseUser, secret: str, verification_code: str) -> Dict[str, Any]:
        """
        Enable 2FA for user after verifying setup.
        
        Args:
            user: EnterpriseUser instance
            secret: TOTP secret key
            verification_code: 6-digit verification code from authenticator app
            
        Returns:
            Dict containing setup result and backup codes
        """
        try:
            # Verify the code first
            if not self.verify_totp_code(secret, verification_code):
                raise ValueError("Invalid verification code")
            
            # Save secret and enable 2FA
            user.two_factor_secret = secret
            user.enable_2fa()
            
            # Generate backup codes
            backup_codes = self.generate_backup_codes(user)
            
            logger.info(f"2FA enabled for user {user.corporate_email}")
            
            return {
                'success': True,
                'backup_codes': backup_codes,
                'message': '2FA enabled successfully',
                'codes_generated': len(backup_codes)
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"2FA enable error for user {user.id}: {str(e)}")
            raise ValueError("Failed to enable 2FA")
    
    def disable_2fa(self, user: EnterpriseUser) -> bool:
        """
        Disable 2FA for user and clean up related data.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            bool: True if 2FA was disabled successfully
        """
        try:
            user.disable_2fa()
            
            logger.info(f"2FA disabled for user {user.corporate_email}")
            return True
            
        except Exception as e:
            logger.error(f"2FA disable error for user {user.id}: {str(e)}")
            return False
    
    def get_2fa_status(self, user: EnterpriseUser) -> Dict[str, Any]:
        """
        Get detailed 2FA status for user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            Dict containing 2FA status and statistics
        """
        try:
            status = {
                'enabled': user.is_2fa_enabled,
                'secret_configured': bool(user.two_factor_secret),
                'backup_codes_available': len(user.backup_codes) if user.backup_codes else 0,
                'backup_codes_remaining': len(user.backup_codes) if user.backup_codes else 0,
                'setup_complete': user.is_2fa_enabled and bool(user.two_factor_secret),
            }
            
            # Add recommendations
            recommendations = []
            if not user.is_2fa_enabled:
                recommendations.append("Enable 2FA for enhanced account security")
            elif user.backup_codes and len(user.backup_codes) < 3:
                recommendations.append("Generate new backup codes (running low)")
            elif not user.backup_codes:
                recommendations.append("Generate backup codes for account recovery")
            
            status['recommendations'] = recommendations
            
            return status
            
        except Exception as e:
            logger.error(f"2FA status error for user {user.id}: {str(e)}")
            return {'error': 'Unable to get 2FA status'}
    
    def regenerate_backup_codes(self, user: EnterpriseUser) -> List[str]:
        """
        Regenerate backup codes for user (replaces existing codes).
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            List of new backup codes
        """
        try:
            if not user.is_2fa_enabled:
                raise ValueError("2FA must be enabled to generate backup codes")
            
            # Generate new codes (this replaces existing ones)
            new_codes = self.generate_backup_codes(user)
            
            logger.info(f"Backup codes regenerated for user {user.corporate_email}")
            
            return new_codes
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Backup code regeneration error for user {user.id}: {str(e)}")
            raise ValueError("Failed to regenerate backup codes")
    
    def validate_2fa_attempt(self, user: EnterpriseUser, code: str) -> Dict[str, Any]:
        """
        Validate 2FA attempt (tries TOTP first, then backup codes).
        
        Args:
            user: EnterpriseUser instance
            code: 6-digit TOTP code or backup code
            
        Returns:
            Dict containing validation result and method used
        """
        try:
            if not user.is_2fa_enabled:
                return {
                    'valid': False,
                    'error': '2FA is not enabled for this user',
                    'method': None
                }
            
            # Try TOTP verification first
            if len(code) == 6 and code.isdigit():
                if self.verify_totp_code(user.two_factor_secret, code):
                    return {
                        'valid': True,
                        'method': 'totp',
                        'message': 'TOTP code verified successfully'
                    }
            
            # Try backup code if TOTP failed
            if self.validate_backup_code(user, code):
                remaining_codes = len(user.backup_codes) if user.backup_codes else 0
                return {
                    'valid': True,
                    'method': 'backup_code',
                    'message': 'Backup code verified successfully',
                    'backup_codes_remaining': remaining_codes,
                    'warning': 'Consider regenerating backup codes if running low' if remaining_codes < 3 else None
                }
            
            return {
                'valid': False,
                'error': 'Invalid or expired code',
                'method': None
            }
            
        except Exception as e:
            logger.error(f"2FA validation error for user {user.id}: {str(e)}")
            return {
                'valid': False,
                'error': 'Validation failed due to system error',
                'method': None
            }
    
    def get_2fa_recovery_options(self, user: EnterpriseUser) -> Dict[str, Any]:
        """
        Get available 2FA recovery options for user.
        
        Args:
            user: EnterpriseUser instance
            
        Returns:
            Dict containing available recovery options
        """
        try:
            options = {
                'backup_codes_available': len(user.backup_codes) if user.backup_codes else 0,
                'can_use_backup_codes': bool(user.backup_codes),
                'admin_recovery_available': True,  # Admins can always disable 2FA
                'recovery_options': []
            }
            
            if user.backup_codes:
                options['recovery_options'].append({
                    'type': 'backup_codes',
                    'description': 'Use one of your saved backup codes',
                    'available': True,
                    'codes_remaining': len(user.backup_codes)
                })
            
            options['recovery_options'].append({
                'type': 'admin_assistance',
                'description': 'Contact system administrator for account recovery',
                'available': True,
                'contact_info': 'support@ficct-enterprise.com'
            })
            
            return options
            
        except Exception as e:
            logger.error(f"2FA recovery options error for user {user.id}: {str(e)}")
            return {'error': 'Unable to get recovery options'}
    
    def admin_disable_2fa(self, admin_user: EnterpriseUser, target_user: EnterpriseUser, reason: str) -> bool:
        """
        Allow admin to disable 2FA for another user (emergency recovery).
        
        Args:
            admin_user: Admin user performing the action
            target_user: User whose 2FA is being disabled
            reason: Reason for disabling 2FA
            
        Returns:
            bool: True if 2FA was disabled successfully
        """
        try:
            # Check admin permissions
            if admin_user.role not in [EnterpriseUser.UserRole.SUPER_ADMIN, EnterpriseUser.UserRole.ADMIN]:
                raise ValueError("Insufficient permissions to disable 2FA")
            
            # Disable 2FA
            target_user.disable_2fa()
            
            # Log the admin action
            logger.warning(
                f"2FA disabled by admin {admin_user.corporate_email} "
                f"for user {target_user.corporate_email}. Reason: {reason}"
            )
            
            # Send notification to user
            from .email_service import EmailService
            email_service = EmailService()
            email_service.send_security_alert_email(
                user=target_user,
                alert_type='2fa_disabled',
                details={
                    'disabled_by_admin': True,
                    'admin_email': admin_user.corporate_email,
                    'reason': reason,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Admin 2FA disable error: {str(e)}")
            return False
    
    def get_2fa_statistics(self) -> Dict[str, Any]:
        """
        Get enterprise-wide 2FA statistics.
        
        Returns:
            Dict containing 2FA adoption and usage statistics
        """
        try:
            total_users = EnterpriseUser.objects.filter(is_active=True).count()
            users_with_2fa = EnterpriseUser.objects.filter(is_2fa_enabled=True, is_active=True).count()
            
            stats = {
                'total_active_users': total_users,
                'users_with_2fa_enabled': users_with_2fa,
                'users_without_2fa': total_users - users_with_2fa,
                '2fa_adoption_rate': round((users_with_2fa / total_users * 100), 2) if total_users > 0 else 0,
                'by_role': {}
            }
            
            # Get statistics by role
            for role_choice in EnterpriseUser.UserRole.choices:
                role = role_choice[0]
                role_total = EnterpriseUser.objects.filter(role=role, is_active=True).count()
                role_with_2fa = EnterpriseUser.objects.filter(role=role, is_2fa_enabled=True, is_active=True).count()
                
                stats['by_role'][role] = {
                    'total': role_total,
                    'with_2fa': role_with_2fa,
                    'without_2fa': role_total - role_with_2fa,
                    'adoption_rate': round((role_with_2fa / role_total * 100), 2) if role_total > 0 else 0
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"2FA statistics error: {str(e)}")
            return {'error': 'Unable to generate 2FA statistics'}
    
    def validate_secret_key(self, secret: str) -> bool:
        """
        Validate that a secret key is properly formatted for TOTP.
        
        Args:
            secret: Base32 encoded secret key
            
        Returns:
            bool: True if secret is valid
        """
        try:
            if not secret:
                return False
            
            # Check if it's valid Base32
            import re
            if not re.match(r'^[A-Z2-7]+$', secret.upper()):
                return False
            
            # Try to create TOTP object
            pyotp.TOTP(secret)
            return True
            
        except Exception:
            return False
