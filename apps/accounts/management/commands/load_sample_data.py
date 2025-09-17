"""
Management command to load sample enterprise data for development and testing.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import AuthorizedDomain
from apps.security.models import IPWhitelist, SecurityConfiguration
from apps.audit.models import AuditLog, SecurityAlert
from datetime import timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Load sample data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of sample users to create (default: 10)'
        )
        parser.add_argument(
            '--domains',
            type=int,
            default=3,
            help='Number of sample domains to create (default: 3)'
        )
        parser.add_argument(
            '--audit-logs',
            type=int,
            default=50,
            help='Number of sample audit logs to create (default: 50)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing sample data before loading new data'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('📊 Loading Sample Enterprise Data')
        )
        self.stdout.write('=' * 40)
        
        try:
            with transaction.atomic():
                if options.get('clear_existing'):
                    self._clear_existing_data()
                
                domains = self._create_sample_domains(options['domains'])
                users = self._create_sample_users(options['users'], domains)
                self._create_sample_ip_whitelist()
                self._create_sample_audit_logs(options['audit_logs'], users)
                self._create_sample_security_alerts(users)
                
                self._display_summary(options)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to load sample data: {str(e)}')
            )
            raise

    def _clear_existing_data(self):
        """Clear existing sample data."""
        self.stdout.write('\n🗑️ Clearing existing sample data...')
        
        # Don't delete superusers, just regular users
        User.objects.filter(is_superuser=False).delete()
        AuthorizedDomain.objects.all().delete()
        IPWhitelist.objects.all().delete()
        AuditLog.objects.all().delete()
        SecurityAlert.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS('✓ Existing data cleared'))

    def _create_sample_domains(self, count):
        """Create sample authorized domains."""
        self.stdout.write(f'\n🏢 Creating {count} sample domains...')
        
        sample_domains = [
            {'domain': 'techcorp.com', 'company': 'TechCorp Industries'},
            {'domain': 'innovatesoft.com', 'company': 'InnovateSoft Solutions'},
            {'domain': 'datatech.com', 'company': 'DataTech Systems'},
            {'domain': 'cloudsystems.com', 'company': 'Cloud Systems Inc'},
            {'domain': 'devworks.com', 'company': 'DevWorks Ltd'},
        ]
        
        domains = []
        for i in range(min(count, len(sample_domains))):
            domain_data = sample_domains[i]
            domain, created = AuthorizedDomain.objects.get_or_create(
                domain=domain_data['domain'],
                defaults={
                    'company_name': domain_data['company'],
                    'is_active': True
                }
            )
            domains.append(domain)
            
            if created:
                self.stdout.write(f'  • {domain.domain} ({domain.company_name})')
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(domains)} domains'))
        return domains

    def _create_sample_users(self, count, domains):
        """Create sample users."""
        self.stdout.write(f'\n👥 Creating {count} sample users...')
        
        sample_users = [
            {'name': 'Alice Johnson', 'role': 'ADMIN', 'dept': 'IT Operations'},
            {'name': 'Bob Smith', 'role': 'MANAGER', 'dept': 'Engineering'},
            {'name': 'Carol Davis', 'role': 'DEVELOPER', 'dept': 'Software Development'},
            {'name': 'David Wilson', 'role': 'DEVELOPER', 'dept': 'Software Development'},
            {'name': 'Eva Brown', 'role': 'ANALYST', 'dept': 'Data Analysis'},
            {'name': 'Frank Miller', 'role': 'MANAGER', 'dept': 'Project Management'},
            {'name': 'Grace Lee', 'role': 'DEVELOPER', 'dept': 'Frontend Development'},
            {'name': 'Henry Taylor', 'role': 'ADMIN', 'dept': 'System Administration'},
            {'name': 'Ivy Chen', 'role': 'ANALYST', 'dept': 'Business Analysis'},
            {'name': 'Jack Wilson', 'role': 'DEVELOPER', 'dept': 'Backend Development'},
        ]
        
        users = []
        for i in range(min(count, len(sample_users))):
            user_data = sample_users[i]
            domain = random.choice(domains)
            
            # Generate email
            first_name = user_data['name'].split()[0].lower()
            last_name = user_data['name'].split()[1].lower()
            email = f'{first_name}.{last_name}@{domain.domain}'
            
            # Skip if user already exists
            if User.objects.filter(corporate_email=email).exists():
                continue
            
            user = User.objects.create_user(
                corporate_email=email,
                full_name=user_data['name'],
                password='TempPassword123!',
                role=getattr(User.UserRole, user_data['role']),
                company_domain=domain.domain,
                department=user_data['dept'],
                email_verified=True,
                is_active=True,
                is_2fa_enabled=random.choice([True, False])
            )
            
            users.append(user)
            self.stdout.write(f'  • {user.corporate_email} ({user.get_role_display()})')
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(users)} users'))
        return users

    def _create_sample_ip_whitelist(self):
        """Create sample IP whitelist entries."""
        self.stdout.write('\n🔒 Creating sample IP whitelist...')
        
        sample_ips = [
            {'ip': '192.168.1.100', 'desc': 'Office Network - Admin Workstation', 'level': 'ADMIN'},
            {'ip': '10.0.0.50', 'desc': 'VPN Gateway', 'level': 'FULL'},
            {'ip': '203.0.113.10', 'desc': 'External API Server', 'level': 'API'},
            {'ip': '127.0.0.1', 'desc': 'Localhost', 'level': 'ADMIN'},
        ]
        
        for ip_data in sample_ips:
            ip_entry, created = IPWhitelist.objects.get_or_create(
                ip_address=ip_data['ip'],
                defaults={
                    'description': ip_data['desc'],
                    'access_level': ip_data['level'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f'  • {ip_entry.ip_address} ({ip_entry.get_access_level_display()})')
        
        self.stdout.write(self.style.SUCCESS('✓ Sample IP whitelist created'))

    def _create_sample_audit_logs(self, count, users):
        """Create sample audit logs."""
        self.stdout.write(f'\n📋 Creating {count} sample audit logs...')
        
        action_types = [
            AuditLog.ActionType.LOGIN_SUCCESS,
            AuditLog.ActionType.LOGIN_FAILED,
            AuditLog.ActionType.LOGOUT,
            AuditLog.ActionType.PASSWORD_CHANGE,
            AuditLog.ActionType.TWO_FA_SUCCESS,
            AuditLog.ActionType.PROFILE_UPDATED,
        ]
        
        severities = [
            AuditLog.Severity.LOW,
            AuditLog.Severity.MEDIUM,
            AuditLog.Severity.HIGH,
        ]
        
        sample_ips = ['192.168.1.100', '10.0.0.50', '203.0.113.10', '127.0.0.1']
        
        for i in range(count):
            user = random.choice(users) if users else None
            action_type = random.choice(action_types)
            severity = random.choice(severities)
            
            # Adjust severity based on action type
            if action_type == AuditLog.ActionType.LOGIN_FAILED:
                severity = random.choice([AuditLog.Severity.MEDIUM, AuditLog.Severity.HIGH])
            
            AuditLog.objects.create(
                user=user,
                action_type=action_type,
                severity=severity,
                ip_address=random.choice(sample_ips),
                user_agent='Mozilla/5.0 (Sample User Agent)',
                resource='/api/auth/login/',
                method='POST',
                status_code=200 if 'SUCCESS' in action_type else 400,
                details={'sample': True, 'test_data': True},
                timestamp=timezone.now() - timedelta(days=random.randint(0, 30))
            )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {count} audit logs'))

    def _create_sample_security_alerts(self, users):
        """Create sample security alerts."""
        self.stdout.write('\n🚨 Creating sample security alerts...')
        
        alert_data = [
            {
                'type': SecurityAlert.AlertType.BRUTE_FORCE,
                'title': 'Brute Force Attack Detected',
                'description': 'Multiple failed login attempts from same IP',
                'severity': AuditLog.Severity.HIGH,
                'risk_score': 85
            },
            {
                'type': SecurityAlert.AlertType.SUSPICIOUS_LOCATION,
                'title': 'Login from Unusual Location',
                'description': 'User logged in from unexpected geographic location',
                'severity': AuditLog.Severity.MEDIUM,
                'risk_score': 60
            },
            {
                'type': SecurityAlert.AlertType.MULTIPLE_FAILURES,
                'title': 'Multiple Authentication Failures',
                'description': 'User had multiple consecutive authentication failures',
                'severity': AuditLog.Severity.MEDIUM,
                'risk_score': 45
            }
        ]
        
        for alert_info in alert_data:
            user = random.choice(users) if users else None
            
            SecurityAlert.objects.create(
                alert_type=alert_info['type'],
                title=alert_info['title'],
                description=alert_info['description'],
                severity=alert_info['severity'],
                risk_score=alert_info['risk_score'],
                user=user,
                ip_address='203.0.113.10',
                status=random.choice(['OPEN', 'INVESTIGATING', 'RESOLVED']),
                created_at=timezone.now() - timedelta(hours=random.randint(1, 72))
            )
            
            self.stdout.write(f'  • {alert_info["title"]}')
        
        self.stdout.write(self.style.SUCCESS('✓ Sample security alerts created'))

    def _display_summary(self, options):
        """Display summary of loaded data."""
        self.stdout.write('\n' + '=' * 40)
        self.stdout.write(
            self.style.SUCCESS('✅ Sample Data Loaded Successfully!')
        )
        self.stdout.write('=' * 40)
        
        # Count all data
        user_count = User.objects.count()
        domain_count = AuthorizedDomain.objects.count()
        ip_count = IPWhitelist.objects.count()
        audit_count = AuditLog.objects.count()
        alert_count = SecurityAlert.objects.count()
        
        self.stdout.write(f'\n📊 Data Summary:')
        self.stdout.write(f'• Users: {user_count}')
        self.stdout.write(f'• Authorized Domains: {domain_count}')
        self.stdout.write(f'• IP Whitelist Entries: {ip_count}')
        self.stdout.write(f'• Audit Logs: {audit_count}')
        self.stdout.write(f'• Security Alerts: {alert_count}')
        
        self.stdout.write('\n🔑 Sample User Credentials:')
        self.stdout.write('• Password: TempPassword123!')
        self.stdout.write('• 2FA: Randomly enabled for some users')
        
        self.stdout.write('\n🌐 Access Points:')
        self.stdout.write('• Django Admin: http://localhost:8000/admin/')
        self.stdout.write('• API Docs: http://localhost:8000/api/docs/')
        self.stdout.write('• API Login: POST /api/auth/login/')
        
        self.stdout.write('\n⚠️  Note: Sample data is for development only!')
        self.stdout.write('Change all passwords before production use.')
        
        self.stdout.write('\n' + self.style.SUCCESS('Sample data loading complete! 📊'))
