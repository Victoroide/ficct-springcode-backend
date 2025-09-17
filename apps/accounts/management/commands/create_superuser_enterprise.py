"""
Management command to create enterprise superuser with 2FA setup.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
import getpass
import qrcode
import io
import base64

User = get_user_model()


class Command(BaseCommand):
    help = 'Create an enterprise superuser with optional 2FA setup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Corporate email address for the superuser'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Full name for the superuser'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Company domain'
        )
        parser.add_argument(
            '--department',
            type=str,
            default='IT Administration',
            help='Department (default: IT Administration)'
        )
        parser.add_argument(
            '--role',
            type=str,
            choices=['SUPER_ADMIN', 'ADMIN', 'MANAGER'],
            default='SUPER_ADMIN',
            help='User role (default: SUPER_ADMIN)'
        )
        parser.add_argument(
            '--skip-2fa',
            action='store_true',
            help='Skip 2FA setup'
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Use interactive mode for all inputs'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔐 Enterprise Superuser Creation')
        )
        self.stdout.write('=' * 40)
        
        try:
            with transaction.atomic():
                user_data = self._collect_user_data(options)
                superuser = self._create_superuser(user_data)
                
                if not options.get('skip_2fa'):
                    self._setup_2fa(superuser)
                
                self._display_summary(superuser)
                
        except Exception as e:
            raise CommandError(f'Superuser creation failed: {str(e)}')

    def _collect_user_data(self, options):
        """Collect user data from options or interactive input."""
        data = {}
        
        # Corporate email
        data['email'] = options.get('email')
        if not data['email'] or options.get('interactive'):
            data['email'] = input('Corporate email: ').strip()
        
        if not data['email'] or '@' not in data['email']:
            raise CommandError('Valid corporate email is required')
        
        # Full name
        data['name'] = options.get('name')
        if not data['name'] or options.get('interactive'):
            data['name'] = input('Full name: ').strip()
        
        if not data['name']:
            raise CommandError('Full name is required')
        
        # Company domain
        data['domain'] = options.get('domain')
        if not data['domain']:
            data['domain'] = data['email'].split('@')[1]
            self.stdout.write(
                self.style.INFO(f'Using domain from email: {data["domain"]}')
            )
        
        # Department
        data['department'] = options.get('department', 'IT Administration')
        if options.get('interactive'):
            dept_input = input(f'Department [{data["department"]}]: ').strip()
            if dept_input:
                data['department'] = dept_input
        
        # Role
        data['role'] = options.get('role', 'SUPER_ADMIN')
        if options.get('interactive'):
            role_input = input(f'Role [{data["role"]}]: ').strip().upper()
            if role_input in ['SUPER_ADMIN', 'ADMIN', 'MANAGER']:
                data['role'] = role_input
        
        # Password
        password = getpass.getpass('Password: ')
        password_confirm = getpass.getpass('Confirm password: ')
        
        if password != password_confirm:
            raise CommandError('Passwords do not match')
        
        if len(password) < 8:
            raise CommandError('Password must be at least 8 characters long')
        
        data['password'] = password
        
        return data

    def _create_superuser(self, user_data):
        """Create the superuser."""
        self.stdout.write('\n👤 Creating Superuser...')
        
        # Check if user already exists
        if User.objects.filter(corporate_email=user_data['email']).exists():
            raise CommandError(f'User with email {user_data["email"]} already exists')
        
        # Create superuser
        superuser = User.objects.create_user(
            corporate_email=user_data['email'],
            full_name=user_data['name'],
            password=user_data['password'],
            role=getattr(User.UserRole, user_data['role']),
            company_domain=user_data['domain'],
            department=user_data['department'],
            email_verified=True,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Superuser created: {user_data["email"]}')
        )
        
        return superuser

    def _setup_2fa(self, superuser):
        """Set up 2FA for the superuser."""
        self.stdout.write('\n🔐 Setting up Two-Factor Authentication...')
        
        try:
            # Generate 2FA secret
            secret = superuser.generate_2fa_secret()
            
            # Generate QR code
            totp_uri = superuser.get_2fa_qr_uri()
            
            self.stdout.write('\n📱 2FA Setup Instructions:')
            self.stdout.write('1. Install a TOTP authenticator app (Google Authenticator, Authy, etc.)')
            self.stdout.write('2. Scan the QR code below or manually enter the secret')
            self.stdout.write('3. Enter the 6-digit code from your app to verify')
            
            self.stdout.write(f'\n🔑 Manual Entry Secret: {secret}')
            self.stdout.write(f'📋 TOTP URI: {totp_uri}')
            
            # Generate QR code (optional display)
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(totp_uri)
                qr.make(fit=True)
                
                # Create QR code as ASCII art for terminal display
                self.stdout.write('\n📱 QR Code:')
                qr.print_ascii(invert=True)
                
            except Exception:
                self.stdout.write('\n⚠️  Could not generate QR code display')
            
            # Verify 2FA setup
            while True:
                code = input('\nEnter 6-digit verification code: ').strip()
                
                if superuser.verify_2fa_token(code):
                    superuser.enable_2fa()
                    self.stdout.write(
                        self.style.SUCCESS('✓ 2FA enabled successfully!')
                    )
                    
                    # Generate and display backup codes
                    backup_codes = superuser.generate_backup_codes()
                    self.stdout.write('\n🔐 Backup Codes (save these securely):')
                    for i, code in enumerate(backup_codes, 1):
                        self.stdout.write(f'  {i:2d}. {code}')
                    
                    self.stdout.write('\n⚠️  Important: Save these backup codes in a secure location!')
                    break
                else:
                    self.stdout.write(
                        self.style.ERROR('❌ Invalid code. Please try again.')
                    )
                    
                    retry = input('Try again? (y/n): ').lower()
                    if retry != 'y':
                        self.stdout.write('2FA setup skipped.')
                        break
                        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'2FA setup failed: {str(e)}')
            )

    def _display_summary(self, superuser):
        """Display creation summary."""
        self.stdout.write('\n' + '=' * 40)
        self.stdout.write(
            self.style.SUCCESS('✅ Superuser Created Successfully!')
        )
        self.stdout.write('=' * 40)
        
        self.stdout.write(f'\n📧 Email: {superuser.corporate_email}')
        self.stdout.write(f'👤 Name: {superuser.full_name}')
        self.stdout.write(f'🏢 Domain: {superuser.company_domain}')
        self.stdout.write(f'🏪 Department: {superuser.department}')
        self.stdout.write(f'👑 Role: {superuser.get_role_display()}')
        self.stdout.write(f'🔐 2FA Enabled: {"Yes" if superuser.is_2fa_enabled else "No"}')
        self.stdout.write(f'✅ Status: {"Active" if superuser.is_active else "Inactive"}')
        
        self.stdout.write('\n🚀 Next Steps:')
        self.stdout.write('• Access Django Admin: http://localhost:8000/admin/')
        self.stdout.write('• Login with the created credentials')
        if superuser.is_2fa_enabled:
            self.stdout.write('• Use your authenticator app for 2FA verification')
        self.stdout.write('• Configure additional enterprise settings as needed')
        
        self.stdout.write('\n' + self.style.SUCCESS('Superuser setup complete! 🎉'))
