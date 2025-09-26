"""
Comprehensive Unit Tests for Authentication Endpoints

Tests for ALL authentication endpoints including authentication ViewSet,
registration ViewSet, user profile ViewSet, and security ViewSet actions.
"""

import json
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from base.test_base import BaseTestCase
from base.test_factories import EnterpriseUserFactory, AdminUserFactory
from apps.accounts.models import EnterpriseUser, AuthorizedDomain
from apps.audit.models import AuditLog

User = get_user_model()


class AuthenticationViewSetTestCase(BaseTestCase):
    """Test cases for AuthenticationViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = APIClient()
        self.login_url = reverse('auth:auth-login')
        self.verify_2fa_url = reverse('auth:auth-verify-2fa')
        self.logout_url = reverse('auth:auth-logout')
        self.refresh_token_url = reverse('auth:auth-refresh-token')
    
    @patch('apps.authentication.services.AuthenticationService.authenticate_user')
    def test_login_success_without_2fa(self, mock_authenticate):
        """Test successful login without 2FA requirement."""
        mock_authenticate.return_value = {
            'status': 'success',
            'requires_2fa': False,
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
            'user': {
                'email': self.test_user.email,
                'name': f"{self.test_user.first_name} {self.test_user.last_name}"
            }
        }
        
        data = {
            'corporate_email': self.test_user.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertFalse(response.data['requires_2fa'])
        self.assertIn('access_token', response.data)
        mock_authenticate.assert_called_once()
    
    @patch('apps.authentication.services.AuthenticationService.authenticate_user')
    def test_login_success_with_2fa_required(self, mock_authenticate):
        """Test successful login with 2FA requirement."""
        mock_authenticate.return_value = {
            'status': 'success',
            'requires_2fa': True,
            'session_token': 'mock_session_token',
            'message': '2FA required'
        }
        
        data = {
            'corporate_email': self.test_user.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertTrue(response.data['requires_2fa'])
        self.assertIn('session_token', response.data)
        mock_authenticate.assert_called_once()
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        data = {
            'corporate_email': 'invalid@example.com',
            'password': 'WrongPassword'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'error')
    
    def test_login_missing_fields(self):
        """Test login with missing required fields."""
        data = {
            'corporate_email': self.test_user.email
            # Missing password
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_invalid_email_format(self):
        """Test login with invalid email format."""
        data = {
            'corporate_email': 'invalid-email',
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('apps.authentication.services.AuthenticationService.verify_2fa_code')
    def test_verify_2fa_success(self, mock_verify_2fa):
        """Test successful 2FA verification."""
        mock_verify_2fa.return_value = {
            'status': 'success',
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
            'user': {
                'email': self.test_user.email,
                'name': f"{self.test_user.first_name} {self.test_user.last_name}"
            }
        }
        
        data = {
            'session_token': 'mock_session_token',
            'code': '123456'
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access_token', response.data)
        mock_verify_2fa.assert_called_once()
    
    def test_verify_2fa_invalid_code(self):
        """Test 2FA verification with invalid code."""
        data = {
            'session_token': 'mock_session_token',
            'code': '000000'
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
    
    def test_verify_2fa_missing_fields(self):
        """Test 2FA verification with missing fields."""
        data = {
            'session_token': 'mock_session_token'
            # Missing code
        }
        
        response = self.client.post(self.verify_2fa_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('apps.authentication.services.AuthenticationService.logout_user')
    def test_logout_success(self, mock_logout):
        """Test successful logout."""
        # Simulate authenticated user
        refresh = RefreshToken.for_user(self.test_user)
        self.client.force_authenticate(user=self.test_user)
        
        mock_logout.return_value = {
            'status': 'success',
            'message': 'Logged out successfully'
        }
        
        data = {
            'refresh_token': str(refresh)
        }
        
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        mock_logout.assert_called_once()
    
    def test_logout_unauthenticated(self):
        """Test logout without authentication."""
        data = {
            'refresh_token': 'some_token'
        }
        
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_missing_token(self):
        """Test logout with missing refresh token."""
        self.client.force_authenticate(user=self.test_user)
        
        data = {}
        
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_refresh_token_endpoint_exists(self):
        """Test that refresh token endpoint is accessible."""
        data = {
            'token': 'invalid_token'
        }
        
        response = self.client.post(self.refresh_token_url, data, format='json')
        
        # Should not return 404, even if token is invalid
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RegistrationViewSetTestCase(BaseTestCase):
    """Test cases for RegistrationViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = APIClient()
        self.register_url = reverse('auth:registration-register')
        self.verify_email_url = reverse('auth:registration-verify-email')
        self.setup_2fa_url = reverse('auth:registration-setup-2fa')
        
        # Create authorized domain
        self.authorized_domain = AuthorizedDomain.objects.create(
            domain='ficct-enterprise.com',
            is_active=True
        )
    
    @patch('apps.authentication.services.RegistrationService.create_enterprise_user')
    def test_register_success(self, mock_create_user):
        """Test successful user registration."""
        mock_create_user.return_value = {
            'status': 'success',
            'message': 'Registration successful',
            'user_id': 123,
            'verification_required': True
        }
        
        data = {
            'corporate_email': 'newuser@ficct-enterprise.com',
            'full_name': 'New Test User',
            'role': 'developer',
            'password': 'NewPassword123!@#',
            'confirm_password': 'NewPassword123!@#'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        mock_create_user.assert_called_once()
    
    def test_register_password_mismatch(self):
        """Test registration with password mismatch."""
        data = {
            'corporate_email': 'newuser@ficct-enterprise.com',
            'full_name': 'New Test User',
            'role': 'developer',
            'password': 'NewPassword123!@#',
            'confirm_password': 'DifferentPassword123!@#'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_invalid_email_domain(self):
        """Test registration with unauthorized email domain."""
        data = {
            'corporate_email': 'newuser@unauthorized-domain.com',
            'full_name': 'New Test User',
            'role': 'developer',
            'password': 'NewPassword123!@#',
            'confirm_password': 'NewPassword123!@#'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_missing_fields(self):
        """Test registration with missing required fields."""
        data = {
            'corporate_email': 'newuser@ficct-enterprise.com',
            'full_name': 'New Test User'
            # Missing role, password, confirm_password
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_weak_password(self):
        """Test registration with weak password."""
        data = {
            'corporate_email': 'newuser@ficct-enterprise.com',
            'full_name': 'New Test User',
            'role': 'developer',
            'password': '123',
            'confirm_password': '123'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('apps.authentication.services.RegistrationService.verify_email')
    def test_verify_email_success(self, mock_verify_email):
        """Test successful email verification."""
        mock_verify_email.return_value = {
            'status': 'success',
            'message': 'Email verified successfully'
        }
        
        data = {
            'user_id': 123,
            'token': 'verification_token_123'
        }
        
        response = self.client.post(self.verify_email_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        mock_verify_email.assert_called_once()
    
    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token."""
        data = {
            'user_id': 123,
            'token': 'invalid_token'
        }
        
        response = self.client.post(self.verify_email_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
    
    def test_verify_email_missing_fields(self):
        """Test email verification with missing fields."""
        data = {
            'user_id': 123
            # Missing token
        }
        
        response = self.client.post(self.verify_email_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('apps.authentication.services.RegistrationService.setup_2fa')
    def test_setup_2fa_success(self, mock_setup_2fa):
        """Test successful 2FA setup."""
        self.client.force_authenticate(user=self.test_user)
        
        mock_setup_2fa.return_value = {
            'status': 'success',
            'qr_code': 'mock_qr_code_data',
            'secret': 'mock_secret',
            'backup_tokens': ['token1', 'token2']
        }
        
        response = self.client.post(self.setup_2fa_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('qr_code', response.data)
        mock_setup_2fa.assert_called_once()
    
    def test_setup_2fa_unauthenticated(self):
        """Test 2FA setup without authentication."""
        response = self.client.post(self.setup_2fa_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileViewSetTestCase(BaseTestCase):
    """Test cases for UserProfileViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Construct URLs manually since they might not be in URL patterns yet
        self.profile_url = '/api/v1/auth/profile/'
        self.update_profile_url = '/api/v1/auth/update-profile/'
        self.change_password_url = '/api/v1/auth/change-password/'
    
    def test_get_profile_success(self):
        """Test successful user profile retrieval."""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.test_user.email)
        self.assertEqual(response.data['first_name'], self.test_user.first_name)
        self.assertEqual(response.data['last_name'], self.test_user.last_name)
    
    def test_get_profile_unauthenticated(self):
        """Test profile retrieval without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile_success(self):
        """Test successful profile update."""
        data = {
            'first_name': 'Updated First',
            'last_name': 'Updated Last'
        }
        
        response = self.client.patch(self.update_profile_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated First')
        self.assertEqual(response.data['last_name'], 'Updated Last')
    
    def test_update_profile_partial(self):
        """Test partial profile update."""
        data = {
            'first_name': 'Only First Name Updated'
        }
        
        response = self.client.patch(self.update_profile_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Only First Name Updated')
        # Last name should remain unchanged
        self.assertEqual(response.data['last_name'], self.test_user.last_name)
    
    def test_update_profile_unauthenticated(self):
        """Test profile update without authentication."""
        self.client.force_authenticate(user=None)
        data = {
            'first_name': 'Updated First'
        }
        
        response = self.client.patch(self.update_profile_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_change_password_success(self):
        """Test successful password change."""
        data = {
            'current_password': 'TestPassword123!@#',
            'new_password': 'NewTestPassword123!@#',
            'confirm_password': 'NewTestPassword123!@#'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['message'], 'Password changed successfully.')
    
    def test_change_password_wrong_current(self):
        """Test password change with wrong current password."""
        data = {
            'current_password': 'WrongCurrentPassword',
            'new_password': 'NewTestPassword123!@#',
            'confirm_password': 'NewTestPassword123!@#'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['message'], 'Current password is incorrect.')
    
    def test_change_password_mismatch(self):
        """Test password change with password mismatch."""
        data = {
            'current_password': 'TestPassword123!@#',
            'new_password': 'NewTestPassword123!@#',
            'confirm_password': 'DifferentPassword123!@#'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_change_password_unauthenticated(self):
        """Test password change without authentication."""
        self.client.force_authenticate(user=None)
        data = {
            'current_password': 'TestPassword123!@#',
            'new_password': 'NewTestPassword123!@#',
            'confirm_password': 'NewTestPassword123!@#'
        }
        
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SecurityViewSetTestCase(BaseTestCase):
    """Test cases for SecurityViewSet endpoints."""
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = APIClient()
        self.client.force_authenticate(user=self.test_user)
        
        # Construct URLs manually since they might not be in URL patterns yet
        self.authorized_domains_url = '/api/v1/auth/authorized-domains/'
        self.audit_logs_url = '/api/v1/auth/audit-logs/'
        self.security_report_url = '/api/v1/auth/security-report/'
        
        # Create test data
        self.authorized_domain = AuthorizedDomain.objects.create(
            domain='ficct-enterprise.com',
            is_active=True
        )
    
    def test_get_authorized_domains_success(self):
        """Test successful retrieval of authorized domains."""
        response = self.client.get(self.authorized_domains_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['domain'], 'ficct-enterprise.com')
    
    def test_get_authorized_domains_unauthenticated(self):
        """Test authorized domains retrieval without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.authorized_domains_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_audit_logs_success(self):
        """Test successful retrieval of user audit logs."""
        # Create some audit logs for the user
        AuditLog.objects.create(
            user=self.test_user,
            action=AuditLog.ActionType.LOGIN_SUCCESS,
            severity=AuditLog.Severity.LOW,
            details={'test': 'data'}
        )
        
        response = self.client.get(self.audit_logs_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_get_audit_logs_unauthenticated(self):
        """Test audit logs retrieval without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.audit_logs_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    @patch('apps.audit.models.AuditLog.objects.filter')
    def test_get_audit_logs_limit(self, mock_filter):
        """Test that audit logs are limited to 50 entries."""
        mock_queryset = Mock()
        mock_filter.return_value = mock_queryset
        
        response = self.client.get(self.audit_logs_url)
        
        # Check that the queryset was sliced to 50
        mock_queryset.__getitem__.assert_called_with(slice(None, 50))
    
    @patch('apps.authentication.services.AuditService.generate_security_report')
    def test_get_security_report_success(self, mock_generate_report):
        """Test successful security report generation."""
        mock_generate_report.return_value = {
            'login_attempts': 10,
            'failed_attempts': 2,
            'security_score': 85,
            'recommendations': ['Enable 2FA']
        }
        
        response = self.client.get(self.security_report_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('login_attempts', response.data)
        self.assertIn('security_score', response.data)
        mock_generate_report.assert_called_once()
    
    @patch('apps.authentication.services.AuditService.generate_security_report')
    def test_get_security_report_with_days_parameter(self, mock_generate_report):
        """Test security report with custom days parameter."""
        mock_generate_report.return_value = {
            'login_attempts': 5,
            'failed_attempts': 1,
            'security_score': 90
        }
        
        response = self.client.get(f'{self.security_report_url}?days=7')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify that the service was called with days=7
        mock_generate_report.assert_called_with(user=self.test_user, days=7)
    
    def test_get_security_report_unauthenticated(self):
        """Test security report retrieval without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.security_report_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticationErrorHandlingTestCase(BaseTestCase):
    """Test cases for authentication error handling."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.login_url = reverse('auth:auth-login')
    
    @patch('apps.authentication.services.AuthenticationService.authenticate_user')
    def test_login_service_exception(self, mock_authenticate):
        """Test login with service throwing unexpected exception."""
        mock_authenticate.side_effect = Exception("Unexpected error")
        
        data = {
            'corporate_email': self.test_user.email,
            'password': 'TestPassword123!@#'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['message'], 'An unexpected error occurred.')
    
    def test_method_not_allowed(self):
        """Test endpoints with wrong HTTP methods."""
        # Test GET on login endpoint (should be POST only)
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Test PUT on login endpoint
        response = self.client.put(self.login_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_content_type_validation(self):
        """Test endpoints with invalid content types."""
        response = self.client.post(
            self.login_url,
            'invalid json',
            content_type='text/plain'
        )
        
        # Should handle invalid content type gracefully
        self.assertIn(response.status_code, [400, 415])


class AuthenticationPermissionsTestCase(BaseTestCase):
    """Test cases for authentication endpoint permissions."""
    
    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
    
    def test_login_allows_anonymous(self):
        """Test that login endpoint allows anonymous access."""
        url = reverse('auth:auth-login')
        response = self.client.post(url, {})
        
        # Should not return 401/403 for anonymous user
        self.assertNotIn(response.status_code, [401, 403])
    
    def test_registration_allows_anonymous(self):
        """Test that registration endpoint allows anonymous access."""
        url = reverse('auth:registration-register')
        response = self.client.post(url, {})
        
        # Should not return 401/403 for anonymous user  
        self.assertNotIn(response.status_code, [401, 403])
    
    def test_logout_requires_authentication(self):
        """Test that logout endpoint requires authentication."""
        url = reverse('auth:auth-logout')
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
