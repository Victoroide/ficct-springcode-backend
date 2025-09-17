"""
Management command for initial enterprise platform setup.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import AuthorizedDomain
from apps.security.models import IPWhitelist, SecurityConfiguration
import getpass
import ipaddress

User = get_user_model()


class Command(BaseCommand):
    help = 'Sets up the FICCT Enterprise Platform with initial configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Email address for the initial admin user'
        )
        parser.add_argument(
            '--admin-name',
            type=str,
            help='Full name for the initial admin user'
        )
        parser.add_argument(
            '--company-domain',
            type=str,
            help='Initial authorized company domain (e.g., example.com)'
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Company name for the authorized domain'
        )
        parser.add_argument(
            '--admin-ip',
            type=str,
            help='IP address to whitelist for admin access'
        )
        parser.add_argument(
            '--skip-interactive',
            action='store_true',
            help='Skip interactive prompts (use provided args only)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 FICCT Enterprise Platform Setup')
        )
        self.stdout.write('=' * 50)
        
        try:
            with transaction.atomic():
                # Step 1: Create initial admin user
                admin_user = self._create_admin_user(options)
                
                # Step 2: Set up authorized domain
                self._setup_authorized_domain(options, admin_user)
                
                # Step 3: Configure IP whitelist
                self._setup_ip_whitelist(options, admin_user)
                
                # Step 4: Configure security settings
                self._setup_security_configuration(admin_user)
                
                # Step 5: Display summary
                self._display_setup_summary(admin_user)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Setup failed: {str(e)}')
            )
            raise CommandError(f'Enterprise setup failed: {str(e)}')

    def _create_admin_user(self, options):
        """Create the initial admin user."""
        self.stdout.write('\n📋 Step 1: Creating Initial Admin User')
        self.stdout.write('-' * 30)
        
        # Get admin email
        admin_email = options.get('admin_email')
        if not admin_email and not options.get('skip_interactive'):
            admin_email = input('Enter admin email address: ').strip()
        
        if not admin_email:
            raise CommandError('Admin email is required')
        
        # Check if admin already exists
        if User.objects.filter(corporate_email=admin_email).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user {admin_email} already exists')
            )
            return User.objects.get(corporate_email=admin_email)
        
        # Get admin name
        admin_name = options.get('admin_name')
        if not admin_name and not options.get('skip_interactive'):
            admin_name = input('Enter admin full name: ').strip()
        
        if not admin_name:
            admin_name = 'Enterprise Administrator'
        
        # Get password
        if not options.get('skip_interactive'):
            password = getpass.getpass('Enter admin password: ')
            password_confirm = getpass.getpass('Confirm admin password: ')
            
            if password != password_confirm:
                raise CommandError('Passwords do not match')
        else:
            password = User.objects.make_random_password(length=16)
            self.stdout.write(
                self.style.WARNING(f'Generated random password: {password}')
            )
        
        # Extract domain from email
        domain = admin_email.split('@')[1] if '@' in admin_email else None
        
        # Create admin user
        admin_user = User.objects.create_user(
            corporate_email=admin_email,
            full_name=admin_name,
            password=password,
            role=User.UserRole.SUPER_ADMIN,
            company_domain=domain,
            department='IT Administration',
            email_verified=True,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Admin user created: {admin_email}')
        )
        
        return admin_user

    def _setup_authorized_domain(self, options, admin_user):
        """Set up the initial authorized domain."""
        self.stdout.write('\n🏢 Step 2: Setting Up Authorized Domain')
        self.stdout.write('-' * 35)
        
        company_domain = options.get('company_domain')
        if not company_domain and not options.get('skip_interactive'):
            company_domain = input('Enter company domain (e.g., example.com): ').strip()
        
        # Use domain from admin email if not provided
        if not company_domain and '@' in admin_user.corporate_email:
            company_domain = admin_user.corporate_email.split('@')[1]
            self.stdout.write(
                self.style.INFO(f'Using domain from admin email: {company_domain}')
            )
        
        if not company_domain:
            self.stdout.write(
                self.style.WARNING('No domain specified, skipping domain setup')
            )
            return
        
        # Check if domain already exists
        if AuthorizedDomain.objects.filter(domain=company_domain).exists():
            self.stdout.write(
                self.style.WARNING(f'Domain {company_domain} already authorized')
            )
            return
        
        company_name = options.get('company_name')
        if not company_name and not options.get('skip_interactive'):
            company_name = input('Enter company name: ').strip()
        
        if not company_name:
            company_name = f'Company ({company_domain})'
        
        # Create authorized domain
        AuthorizedDomain.objects.create(
            domain=company_domain,
            company_name=company_name,
            created_by=admin_user,
            is_active=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Authorized domain added: {company_domain}')
        )

    def _setup_ip_whitelist(self, options, admin_user):
        """Set up IP whitelist for admin access."""
        self.stdout.write('\n🔒 Step 3: Configuring IP Whitelist')
        self.stdout.write('-' * 30)
        
        admin_ip = options.get('admin_ip')
        if not admin_ip and not options.get('skip_interactive'):
            admin_ip = input('Enter IP to whitelist for admin access (or press enter to skip): ').strip()
        
        if not admin_ip:
            # Add localhost by default
            admin_ip = '127.0.0.1'
            self.stdout.write(
                self.style.INFO('Using localhost (127.0.0.1) as default admin IP')
            )
        
        try:
            # Validate IP address
            ipaddress.ip_address(admin_ip)
            
            # Check if IP already whitelisted
            if IPWhitelist.objects.filter(ip_address=admin_ip).exists():
                self.stdout.write(
                    self.style.WARNING(f'IP {admin_ip} already whitelisted')
                )
                return
            
            # Create IP whitelist entry
            IPWhitelist.objects.create(
                ip_address=admin_ip,
                description='Initial admin access IP',
                access_level='ADMIN',
                created_by=admin_user,
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ IP whitelisted for admin access: {admin_ip}')
            )
            
        except ValueError:
            self.stdout.write(
                self.style.ERROR(f'Invalid IP address: {admin_ip}')
            )

    def _setup_security_configuration(self, admin_user):
        """Set up initial security configuration."""
        self.stdout.write('\n⚙️ Step 4: Configuring Security Settings')
        self.stdout.write('-' * 35)
        
        # Default security configurations
        security_configs = [
            {
                'setting_name': 'ENABLE_2FA_ENFORCEMENT',
                'setting_value': 'false',
                'description': 'Enforce 2FA for all users (can be enabled later)'
            },
            {
                'setting_name': 'PASSWORD_EXPIRY_DAYS',
                'setting_value': '90',
                'description': 'Password expiry period in days'
            },
            {
                'setting_name': 'MAX_LOGIN_ATTEMPTS',
                'setting_value': '5',
                'description': 'Maximum failed login attempts before lockout'
            },
            {
                'setting_name': 'ACCOUNT_LOCKOUT_DURATION',
                'setting_value': '15',
                'description': 'Account lockout duration in minutes'
            },
            {
                'setting_name': 'ENABLE_AUDIT_LOGGING',
                'setting_value': 'true',
                'description': 'Enable comprehensive audit logging'
            },
            {
                'setting_name': 'SESSION_TIMEOUT_MINUTES',
                'setting_value': '480',
                'description': 'User session timeout in minutes (8 hours)'
            }
        ]
        
        created_count = 0
        for config in security_configs:
            setting, created = SecurityConfiguration.objects.get_or_create(
                setting_name=config['setting_name'],
                defaults={
                    'setting_value': config['setting_value'],
                    'description': config['description'],
                    'updated_by': admin_user,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ {created_count} security settings configured')
        )

    def _display_setup_summary(self, admin_user):
        """Display setup summary and next steps."""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(
            self.style.SUCCESS('🎉 Enterprise Platform Setup Complete!')
        )
        self.stdout.write('=' * 50)
        
        self.stdout.write('\n📊 Setup Summary:')
        self.stdout.write(f'• Admin User: {admin_user.corporate_email}')
        self.stdout.write(f'• Role: {admin_user.get_role_display()}')
        self.stdout.write(f'• Company Domain: {admin_user.company_domain}')
        
        # Count configurations
        domain_count = AuthorizedDomain.objects.count()
        ip_count = IPWhitelist.objects.count()
        security_count = SecurityConfiguration.objects.count()
        
        self.stdout.write(f'• Authorized Domains: {domain_count}')
        self.stdout.write(f'• Whitelisted IPs: {ip_count}')
        self.stdout.write(f'• Security Settings: {security_count}')
        
        self.stdout.write('\n🚀 Next Steps:')
        self.stdout.write('1. Start the development server: python manage.py runserver')
        self.stdout.write('2. Access Django admin: http://localhost:8000/admin/')
        self.stdout.write('3. Test API endpoints: http://localhost:8000/api/docs/')
        self.stdout.write('4. Configure email settings in .env for production')
        self.stdout.write('5. Set up Redis and PostgreSQL for production deployment')
        
        self.stdout.write('\n📚 Documentation:')
        self.stdout.write('• API Documentation: /api/docs/')
        self.stdout.write('• Admin Interface: /admin/')
        self.stdout.write('• Health Check: /health/')
        
        self.stdout.write('\n⚠️  Security Notes:')
        self.stdout.write('• Change default passwords before production deployment')
        self.stdout.write('• Configure proper SSL certificates')
        self.stdout.write('• Review and customize security settings')
        self.stdout.write('• Set up monitoring and alerting')
        
        self.stdout.write('\n' + self.style.SUCCESS('Setup completed successfully! 🎉'))
