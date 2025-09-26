"""
Comprehensive tests for Authentication ViewSets.

Tests all authentication endpoints including login, 2FA, logout, registration,
email verification, and profile management with full coverage.
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from unittest.mock import patch, MagicMock
import json

from base.test_base import EnterpriseTestCase, BaseAPITestCase
from base.test_factories import EnterpriseUserFactory, TOTPDeviceFactory
from apps.accounts.models import EnterpriseUser, AuthorizedDomain

User = get_user_model()


class AuthenticationViewSetTestCase(EnterpriseTestCase):
    """Comprehensive tests for AuthenticationViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for authentication tests."""
        super().setUpTestData()
        
        # Create authorized domain
        cls.authorized_domain = AuthorizedDomain.objects.create(
            domain='ficct-enterprise.com',
            company_name='FICCT Enterprise',
            is_active=True
        )
        
        # Create test users with different states
        cls.active_user = EnterpriseUserFactory(
            email='active@ficct-enterprise.com',
            is_active=True,
            email_verified=True
        )
        
        cls.user_with_2fa = EnterpriseUserFactory(
            email='2fa@ficct-enterprise.com',
            is_active=True,
            email_verified=True,
            is_2fa_enabled=True
        )
        
        cls.inactive_user = EnterpriseUserFactory(
            email='inactive@ficct-enterprise.com',
            is_active=False,
            email_verified=False
        )
        
        # Create 2FA device for 2FA user
        cls.totp_device = TOTPDeviceFactory(user=cls.user_with_2fa)
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        self.login_url = reverse('authentication:auth-login')
        self.logout_url = reverse('authentication:auth-logout')
        self.refresh_url = reverse('authentication:auth-refresh-token')
        self.verify_2fa_url = reverse('authentication:auth-verify-2fa')
        self.profile_url = reverse('authentication:auth-get-user-profile')
    
    def test_successful_login_without_2fa(self):
        """Test successful login for user without 2FA."""
        data = {
            'corporate_email': self.active_user.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertFalse(response_data['requires_2fa'])
        self.assertIn('tokens', response_data)
        self.assertIn('access_token', response_data['tokens'])
        self.assertIn('refresh_token', response_data['tokens'])
        self.assertIn('user', response_data)
    
    def test_successful_login_with_2fa_required(self):
        """Test login that requires 2FA verification."""
        data = {
            'corporate_email': self.user_with_2fa.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertTrue(response_data['requires_2fa'])
        self.assertIn('user_id', response_data)
        self.assertNotIn('tokens', response_data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        data = {
            'corporate_email': self.active_user.email,
            'password': 'wrong_password'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data.get('success', True))
    
    def test_login_inactive_user(self):
        """Test login with inactive user."""
        data = {
            'corporate_email': self.inactive_user.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_missing_fields(self):
        """Test login with missing required fields."""
        # Missing password
        data = {
            'corporate_email': self.active_user.email
        }
        
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing email
        data = {
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_rate_limiting(self):
        """Test login rate limiting functionality."""
        data = {
            'corporate_email': 'nonexistent@ficct-enterprise.com',
            'password': 'wrong_password'
        }
        
        # Make multiple rapid requests to trigger rate limiting
        for i in range(6):  # Rate limit is 5/min
            response = self.client.post(self.login_url, data, format='json')
        
        # The 6th request should be rate limited
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    @patch('apps.authentication.services.TwoFactorService.verify_totp_token')
    def test_2fa_verification_success(self, mock_verify):
        """Test successful 2FA verification."""
        mock_verify.return_value = True
        
        data = {
            'user_id': str(self.user_with_2fa.id),
            'token': '123456'
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('tokens', response_data)
        self.assertIn('user', response_data)
    
    @patch('apps.authentication.services.TwoFactorService.verify_totp_token')
    def test_2fa_verification_invalid_token(self, mock_verify):
        """Test 2FA verification with invalid token."""
        mock_verify.return_value = False
        
        data = {
            'user_id': str(self.user_with_2fa.id),
            'token': '000000'
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data.get('success', True))
    
    def test_2fa_verification_missing_fields(self):
        """Test 2FA verification with missing required fields."""
        # Missing token
        data = {
            'user_id': str(self.user_with_2fa.id)
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing user_id
        data = {
            'token': '123456'
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_logout_success(self):
        """Test successful logout."""
        # First login to get tokens
        tokens = self.authenticate_user(self.active_user)
        
        data = {
            'refresh_token': tokens['refresh']
        }
        
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data['success'])
    
    def test_logout_without_authentication(self):
        """Test logout without authentication."""
        self.logout_user()
        
        data = {
            'refresh_token': 'some_token'
        }
        
        response = self.client.post(self.logout_url, data, format='json')
        self.assert_unauthorized(response)
    
    def test_refresh_token_success(self):
        """Test successful token refresh."""
        tokens = self.authenticate_user(self.active_user)
        
        data = {
            'refresh_token': tokens['refresh']
        }
        
        response = self.client.post(self.refresh_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('tokens', response_data)
        self.assertIn('access_token', response_data['tokens'])
    
    def test_refresh_token_invalid(self):
        """Test token refresh with invalid token."""
        data = {
            'refresh_token': 'invalid_token'
        }
        
        response = self.client.post(self.refresh_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_user_profile_success(self):
        """Test successful user profile retrieval."""
        self.authenticate_user(self.active_user)
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('user', response_data)
        self.assertEqual(response_data['user']['email'], self.active_user.email)
    
    def test_get_user_profile_unauthenticated(self):
        """Test user profile retrieval without authentication."""
        self.logout_user()
        
        response = self.client.get(self.profile_url)
        self.assert_unauthorized(response)
    
    def test_update_user_profile_success(self):
        """Test successful user profile update."""
        self.authenticate_user(self.active_user)
        
        update_url = reverse('authentication:auth-update-user-profile')
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(update_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['user']['first_name'], 'Updated')
        self.assertEqual(response_data['user']['last_name'], 'Name')
    
    def test_change_password_success(self):
        """Test successful password change."""
        self.authenticate_user(self.active_user)
        
        change_password_url = reverse('authentication:auth-change-password')
        data = {
            'current_password': 'TestPassword123!@#',
            'new_password': 'NewPassword456!@#',
            'confirm_password': 'NewPassword456!@#'
        }
        
        response = self.client.post(change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data['success'])
    
    def test_change_password_wrong_current(self):
        """Test password change with wrong current password."""
        self.authenticate_user(self.active_user)
        
        change_password_url = reverse('authentication:auth-change-password')
        data = {
            'current_password': 'WrongPassword',
            'new_password': 'NewPassword456!@#',
            'confirm_password': 'NewPassword456!@#'
        }
        
        response = self.client.post(change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_change_password_mismatch(self):
        """Test password change with password confirmation mismatch."""
        self.authenticate_user(self.active_user)
        
        change_password_url = reverse('authentication:auth-change-password')
        data = {
            'current_password': 'TestPassword123!@#',
            'new_password': 'NewPassword456!@#',
            'confirm_password': 'DifferentPassword789!@#'
        }
        
        response = self.client.post(change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegistrationViewSetTestCase(APITestCase):
    """Comprehensive tests for RegistrationViewSet."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for registration tests."""
        super().setUpTestData()
        
        # Create authorized domain
        cls.authorized_domain = AuthorizedDomain.objects.create(
            domain='ficct-enterprise.com',
            company_name='FICCT Enterprise',
            is_active=True
        )
    
    def setUp(self):
        """Set up test environment for each test."""
        super().setUp()
        # SYSTEMATIC AUTHENTICATION STATE RESET - affects ALL registration tests
        self.client = APIClient()
        self.client.logout()
        self.client.credentials()  # Clear all headers
        self.client.force_authenticate(user=None)  # Explicit unauthenticated state
        
        # Clear internal Django test client state
        self.client._credentials = {}
        self.client._force_user = None
        
        # Clear session data that might carry over from other tests
        if hasattr(self.client, 'session'):
            self.client.session.flush()
        
        # Create authorized domain for testing if it doesn't exist
        from apps.accounts.models import AuthorizedDomain
        self.test_domain = 'ficct-enterprise.com'
        AuthorizedDomain.objects.get_or_create(
            domain=self.test_domain,
            defaults={
                'company_name': 'FICCT Enterprise',
                'is_active': True
            }
        )
            
        self.register_url = reverse('authentication:registration-register')
        self.verify_email_url = reverse('authentication:registration-verify-email')
        self.setup_2fa_url = reverse('authentication:registration-setup-2fa')
        self.domains_url = reverse('authentication:registration-get-authorized-domains')
    
    @patch('apps.authentication.services.EmailService.send_verification_email')
    def test_successful_registration(self, mock_send_email):
        """Test successful user registration."""
        mock_send_email.return_value = True
        
        data = {
            'corporate_email': 'newuser@ficct-enterprise.com',
            'password': 'SecurePassword123!@#',
            'password_confirm': 'SecurePassword123!@#',
            'first_name': 'New',
            'last_name': 'User',
            'full_name': 'New User',
            'role': 'DEVELOPER',
            'department': 'Engineering'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('user_id', response_data)
        self.assertEqual(response_data['corporate_email'], data['corporate_email'])
        self.assertTrue(response_data['verification_required'])
        
        # Verify user was created
        user = User.objects.get(corporate_email=data['corporate_email'])
        self.assertFalse(user.is_active)  # Should be inactive until verification
        self.assertFalse(user.email_verified)
    
    def test_registration_unauthorized_domain(self):
        """Test registration with unauthorized domain."""
        data = {
            'corporate_email': 'user@unauthorized-domain.com',
            'password': 'SecurePassword123!@#',
            'password_confirm': 'SecurePassword123!@#',
            'first_name': 'New',
            'last_name': 'User',
            'full_name': 'New User',
            'role': 'DEVELOPER',
            'department': 'Engineering'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_registration_duplicate_email(self):
        """Test registration with already existing email."""
        # Create existing user
        existing_user = EnterpriseUserFactory(corporate_email='existing@ficct-enterprise.com')
        
        data = {
            'corporate_email': 'existing@ficct-enterprise.com',
            'password': 'SecurePassword123!@#',
            'password_confirm': 'SecurePassword123!@#',
            'first_name': 'New',
            'last_name': 'User',
            'full_name': 'New User',
            'role': 'DEVELOPER',
            'department': 'Engineering'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_registration_missing_required_fields(self):
        """Test registration with missing required fields."""
        incomplete_data = {
            'corporate_email': 'incomplete@ficct-enterprise.com',
            'password': 'SecurePassword123!@#'
            # Missing first_name, last_name, role, department
        }
        
        response = self.client.post(self.register_url, incomplete_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_registration_weak_password(self):
        """Test registration with weak password."""
        data = {
            'corporate_email': 'weakpass@ficct-enterprise.com',
            'password': '123',  # Too weak
            'password_confirm': '123',
            'first_name': 'Weak',
            'last_name': 'Password',
            'full_name': 'Weak Password',
            'role': 'DEVELOPER',
            'department': 'Engineering'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_registration_rate_limiting(self):
        """Test registration rate limiting."""
        base_data = {
            'password': 'SecurePassword123!@#',
            'password_confirm': 'SecurePassword123!@#',
            'first_name': 'Rate',
            'last_name': 'Limited',
            'full_name': 'Rate Limited',
            'role': 'DEVELOPER',
            'department': 'Engineering'
        }
        
        # Make multiple rapid registration requests
        for i in range(4):  # Rate limit is 3/hour
            data = base_data.copy()
            data['corporate_email'] = f'ratelimit{i}@ficct-enterprise.com'
            response = self.client.post(self.register_url, data, format='json')
        
        # The 4th request should be rate limited
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    
    @patch('apps.authentication.services.TwoFactorService.setup_totp_device')
    def test_2fa_setup_success(self, mock_setup):
        """Test successful 2FA setup."""
        mock_setup.return_value = {
            'secret': 'JBSWY3DPEHPK3PXP',
            'backup_tokens': ['token1', 'token2'],
            'success': True
        }
        
        user = EnterpriseUserFactory(
            email='2fa@ficct-enterprise.com',
            is_active=True,
            email_verified=True
        )
        
        setup_url = reverse('authentication:registration-setup-2fa')
        data = {
            'email': user.email
        }
        
        response = self.client.post(setup_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertIn('secret', response_data)
        self.assertIn('backup_tokens', response_data)
    
    @patch('apps.authentication.services.TwoFactorService.generate_qr_code_data')
    def test_2fa_qr_code_generation(self, mock_generate_qr):
        """Test successful 2FA QR code generation."""
        mock_generate_qr.return_value = {
            'qr_uri': 'otpauth://totp/FICCT%20Enterprise:test@ficct-enterprise.com?secret=JBSWY3DPEHPK3PXP&issuer=FICCT%20Enterprise',
            'secret': 'JBSWY3DPEHPK3PXP'
        }
        
        user = EnterpriseUserFactory(
            email='qrcode@ficct-enterprise.com',
            is_active=True,
            email_verified=True
        )
        
        qr_url = reverse('authentication:registration-generate-2fa-qr')
        data = {
            'email': user.email
        }
        
        response = self.client.post(qr_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('qr_code_uri', response_data)
        self.assertIn('secret_key', response_data)
        self.assertEqual(response_data['issuer'], 'FICCT Enterprise')
        self.assertEqual(response_data['account_name'], user.email)
    
    def test_email_verification(self):
        """Test email verification endpoint."""
        # Create unverified user
        user = EnterpriseUserFactory(
            email='verify@ficct-enterprise.com',
            is_active=False,
            email_verified=False
        )
        
        # Set verification token
        token = 'test-verification-token-12345'
        user.email_verification_token = token
        user.save()
        
        # Test email verification
        data = {
            'email': user.email,
            'verification_token': token
        }
        
        response = self.client.post(self.verify_email_url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertIn('user_id', response_data)
        self.assertEqual(response_data['user_id'], str(user.id))
        
        # Verify user is now verified
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)
