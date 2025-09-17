"""
Comprehensive tests for Authentication models.

Tests all model functionality including validation, methods, and business logic.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from base.test_base import BaseTestCase
from base.test_factories import EnterpriseUserFactory, TOTPDeviceFactory
from apps.accounts.models import EnterpriseUser, AuthorizedDomain

User = get_user_model()


class EnterpriseUserModelTestCase(BaseTestCase):
    """Test EnterpriseUser model functionality."""
    
    def test_user_creation_success(self):
        """Test successful user creation with all required fields."""
        user = EnterpriseUserFactory(
            email='test@ficct-enterprise.com',
            first_name='Test',
            last_name='User',
            role='DEVELOPER',
            department='Engineering'
        )
        
        self.assertTrue(isinstance(user, EnterpriseUser))
        self.assertEqual(user.email, 'test@ficct-enterprise.com')
        self.assertEqual(user.full_name, 'Test User')
        self.assertEqual(user.role, 'DEVELOPER')
        self.assertEqual(user.department, 'Engineering')
    
    def test_user_string_representation(self):
        """Test user string representation."""
        user = EnterpriseUserFactory(
            email='repr@ficct-enterprise.com',
            first_name='Repr',
            last_name='Test'
        )
        
        expected_str = 'Repr Test (repr@ficct-enterprise.com)'
        self.assertEqual(str(user), expected_str)
    
    def test_full_name_property(self):
        """Test full_name property."""
        user = EnterpriseUserFactory(
            first_name='John',
            last_name='Doe'
        )
        
        self.assertEqual(user.full_name, 'John Doe')
        
        # Test with only first name
        user.last_name = ''
        self.assertEqual(user.full_name, 'John')
        
        # Test with only last name
        user.first_name = ''
        user.last_name = 'Doe'
        self.assertEqual(user.full_name, 'Doe')
    
    def test_company_domain_property(self):
        """Test company_domain property."""
        user = EnterpriseUserFactory(email='test@ficct-enterprise.com')
        self.assertEqual(user.company_domain, 'ficct-enterprise.com')
        
        user.email = 'another@different-company.org'
        self.assertEqual(user.company_domain, 'different-company.org')
    
    def test_is_password_expired(self):
        """Test password expiration checking."""
        user = EnterpriseUserFactory()
        
        # New user should not have expired password
        self.assertFalse(user.is_password_expired())
        
        # Set password change date to 100 days ago
        user.password_changed_at = timezone.now() - timedelta(days=100)
        user.save()
        
        # Should be expired (assuming 90 day expiry)
        self.assertTrue(user.is_password_expired())
    
    def test_failed_login_attempts(self):
        """Test failed login attempt tracking."""
        user = EnterpriseUserFactory()
        
        # Initial state
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertFalse(user.is_locked_out())
        
        # Increment failed attempts
        user.increment_failed_attempts()
        self.assertEqual(user.failed_login_attempts, 1)
        
        # Lock out after max attempts
        for _ in range(4):  # Assuming max is 5
            user.increment_failed_attempts()
        
        self.assertTrue(user.is_locked_out())
        
        # Reset attempts
        user.reset_failed_attempts()
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertFalse(user.is_locked_out())
    
    def test_update_login_info(self):
        """Test login information update."""
        user = EnterpriseUserFactory()
        
        ip_address = '192.168.1.100'
        user_agent = 'Mozilla/5.0 Test Browser'
        
        user.update_login_info(ip_address, user_agent)
        
        self.assertEqual(user.last_login_ip, ip_address)
        self.assertEqual(user.last_user_agent, user_agent)
        self.assertIsNotNone(user.last_login)
    
    def test_generate_email_verification_token(self):
        """Test email verification token generation."""
        user = EnterpriseUserFactory(is_email_verified=False)
        
        # Generate token
        user.generate_email_verification_token()
        
        self.assertIsNotNone(user.email_verification_token)
        self.assertIsNotNone(user.email_verification_expires)
        
        # Token should be valid
        self.assertTrue(user.is_email_verification_token_valid())
        
        # Expire token
        user.email_verification_expires = timezone.now() - timedelta(hours=1)
        user.save()
        
        self.assertFalse(user.is_email_verification_token_valid())
    
    def test_verify_email(self):
        """Test email verification process."""
        user = EnterpriseUserFactory(
            is_email_verified=False,
            is_active=False
        )
        
        user.generate_email_verification_token()
        token = user.email_verification_token
        
        # Verify email
        user.verify_email(token)
        
        self.assertTrue(user.is_email_verified)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.email_verification_token)
        self.assertIsNone(user.email_verification_expires)
    
    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token."""
        user = EnterpriseUserFactory(is_email_verified=False)
        user.generate_email_verification_token()
        
        with self.assertRaises(ValidationError):
            user.verify_email('invalid_token')
    
    def test_verify_email_expired_token(self):
        """Test email verification with expired token."""
        user = EnterpriseUserFactory(is_email_verified=False)
        user.generate_email_verification_token()
        
        # Expire token
        user.email_verification_expires = timezone.now() - timedelta(hours=1)
        user.save()
        
        with self.assertRaises(ValidationError):
            user.verify_email(user.email_verification_token)
    
    def test_can_login_active_user(self):
        """Test login capability for active user."""
        user = EnterpriseUserFactory(
            is_active=True,
            is_email_verified=True
        )
        
        self.assertTrue(user.can_login())
    
    def test_can_login_inactive_user(self):
        """Test login capability for inactive user."""
        user = EnterpriseUserFactory(
            is_active=False,
            is_email_verified=True
        )
        
        self.assertFalse(user.can_login())
    
    def test_can_login_unverified_email(self):
        """Test login capability for user with unverified email."""
        user = EnterpriseUserFactory(
            is_active=True,
            is_email_verified=False
        )
        
        self.assertFalse(user.can_login())
    
    def test_can_login_locked_out_user(self):
        """Test login capability for locked out user."""
        user = EnterpriseUserFactory(
            is_active=True,
            is_email_verified=True
        )
        
        # Lock out user
        for _ in range(5):
            user.increment_failed_attempts()
        
        self.assertFalse(user.can_login())
    
    def test_enable_2fa(self):
        """Test 2FA enablement."""
        user = EnterpriseUserFactory(is_2fa_enabled=False)
        
        user.enable_2fa()
        
        self.assertTrue(user.is_2fa_enabled)
        self.assertIsNotNone(user.two_factor_enabled_at)
    
    def test_disable_2fa(self):
        """Test 2FA disablement."""
        user = EnterpriseUserFactory(is_2fa_enabled=True)
        
        user.disable_2fa()
        
        self.assertFalse(user.is_2fa_enabled)
        self.assertIsNone(user.two_factor_enabled_at)
    
    def test_get_active_users(self):
        """Test getting active users."""
        # Create active and inactive users
        active_user1 = EnterpriseUserFactory(is_active=True)
        active_user2 = EnterpriseUserFactory(is_active=True)
        inactive_user = EnterpriseUserFactory(is_active=False)
        
        active_users = EnterpriseUser.get_active_users()
        
        self.assertIn(active_user1, active_users)
        self.assertIn(active_user2, active_users)
        self.assertNotIn(inactive_user, active_users)
    
    def test_get_users_by_role(self):
        """Test getting users by role."""
        developer = EnterpriseUserFactory(role='DEVELOPER')
        admin = EnterpriseUserFactory(role='ADMIN')
        manager = EnterpriseUserFactory(role='MANAGER')
        
        developers = EnterpriseUser.get_users_by_role('DEVELOPER')
        admins = EnterpriseUser.get_users_by_role('ADMIN')
        
        self.assertIn(developer, developers)
        self.assertNotIn(admin, developers)
        self.assertNotIn(manager, developers)
        
        self.assertIn(admin, admins)
        self.assertNotIn(developer, admins)
        self.assertNotIn(manager, admins)
    
    def test_get_users_by_department(self):
        """Test getting users by department."""
        engineering = EnterpriseUserFactory(department='Engineering')
        marketing = EnterpriseUserFactory(department='Marketing')
        sales = EnterpriseUserFactory(department='Sales')
        
        eng_users = EnterpriseUser.get_users_by_department('Engineering')
        marketing_users = EnterpriseUser.get_users_by_department('Marketing')
        
        self.assertIn(engineering, eng_users)
        self.assertNotIn(marketing, eng_users)
        self.assertNotIn(sales, eng_users)
        
        self.assertIn(marketing, marketing_users)
        self.assertNotIn(engineering, marketing_users)
        self.assertNotIn(sales, marketing_users)


class AuthorizedDomainModelTestCase(BaseTestCase):
    """Test AuthorizedDomain model functionality."""
    
    def test_domain_creation(self):
        """Test authorized domain creation."""
        domain = AuthorizedDomain.objects.create(
            domain='test-company.com',
            company_name='Test Company',
            is_active=True
        )
        
        self.assertEqual(domain.domain, 'test-company.com')
        self.assertEqual(domain.company_name, 'Test Company')
        self.assertTrue(domain.is_active)
    
    def test_domain_string_representation(self):
        """Test domain string representation."""
        domain = AuthorizedDomain.objects.create(
            domain='example.com',
            company_name='Example Corp'
        )
        
        expected_str = 'example.com (Example Corp)'
        self.assertEqual(str(domain), expected_str)
    
    def test_is_domain_authorized_active(self):
        """Test domain authorization check for active domain."""
        AuthorizedDomain.objects.create(
            domain='authorized.com',
            company_name='Authorized Company',
            is_active=True
        )
        
        self.assertTrue(AuthorizedDomain.is_domain_authorized('authorized.com'))
        self.assertTrue(AuthorizedDomain.is_domain_authorized('AUTHORIZED.COM'))  # Case insensitive
    
    def test_is_domain_authorized_inactive(self):
        """Test domain authorization check for inactive domain."""
        AuthorizedDomain.objects.create(
            domain='inactive.com',
            company_name='Inactive Company',
            is_active=False
        )
        
        self.assertFalse(AuthorizedDomain.is_domain_authorized('inactive.com'))
    
    def test_is_domain_authorized_nonexistent(self):
        """Test domain authorization check for nonexistent domain."""
        self.assertFalse(AuthorizedDomain.is_domain_authorized('nonexistent.com'))
    
    def test_get_active_domains(self):
        """Test getting active domains."""
        active_domain1 = AuthorizedDomain.objects.create(
            domain='active1.com',
            company_name='Active Company 1',
            is_active=True
        )
        active_domain2 = AuthorizedDomain.objects.create(
            domain='active2.com',
            company_name='Active Company 2',
            is_active=True
        )
        inactive_domain = AuthorizedDomain.objects.create(
            domain='inactive.com',
            company_name='Inactive Company',
            is_active=False
        )
        
        active_domains = AuthorizedDomain.get_active_domains()
        
        self.assertIn(active_domain1, active_domains)
        self.assertIn(active_domain2, active_domains)
        self.assertNotIn(inactive_domain, active_domains)
    
    def test_get_company_by_domain(self):
        """Test getting company name by domain."""
        domain = AuthorizedDomain.objects.create(
            domain='company.com',
            company_name='Test Company Inc.',
            is_active=True
        )
        
        company_name = AuthorizedDomain.get_company_by_domain('company.com')
        self.assertEqual(company_name, 'Test Company Inc.')
        
        # Test case insensitive
        company_name = AuthorizedDomain.get_company_by_domain('COMPANY.COM')
        self.assertEqual(company_name, 'Test Company Inc.')
        
        # Test nonexistent domain
        company_name = AuthorizedDomain.get_company_by_domain('nonexistent.com')
        self.assertIsNone(company_name)
    
    def test_domain_validation(self):
        """Test domain validation."""
        # Valid domain
        domain = AuthorizedDomain(
            domain='valid-domain.com',
            company_name='Valid Company'
        )
        domain.full_clean()  # Should not raise
        
        # Invalid domain formats
        invalid_domains = [
            'invalid',
            'invalid.',
            '.invalid',
            'invalid..com',
            'invalid-.com',
            '-invalid.com'
        ]
        
        for invalid_domain in invalid_domains:
            with self.assertRaises(ValidationError):
                domain = AuthorizedDomain(
                    domain=invalid_domain,
                    company_name='Invalid Company'
                )
                domain.full_clean()
    
    def test_unique_domain_constraint(self):
        """Test unique domain constraint."""
        AuthorizedDomain.objects.create(
            domain='duplicate.com',
            company_name='First Company'
        )
        
        with self.assertRaises(ValidationError):
            duplicate_domain = AuthorizedDomain(
                domain='duplicate.com',
                company_name='Second Company'
            )
            duplicate_domain.full_clean()
    
    def test_domain_case_insensitive_storage(self):
        """Test that domains are stored in lowercase."""
        domain = AuthorizedDomain.objects.create(
            domain='UPPERCASE-DOMAIN.COM',
            company_name='Test Company'
        )
        
        domain.refresh_from_db()
        self.assertEqual(domain.domain, 'uppercase-domain.com')
