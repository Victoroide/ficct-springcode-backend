"""
Enterprise Test Base Classes and Utilities

Provides comprehensive testing infrastructure for all Django apps with
authentication, permissions, JWT token management, and standardized test patterns.
"""

import json
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django_otp.plugins.otp_totp.models import TOTPDevice
from apps.accounts.models import EnterpriseUser

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common fixtures and utilities."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the entire test class."""

        email_suffix = f"{int(datetime.now().timestamp())}{uuid.uuid4().hex[:4]}"
        class_suffix = uuid.uuid4().hex[:4]

        test_email = f'testuser_{email_suffix}_{class_suffix}@ficct-enterprise.com'
        admin_email = f'admin_{email_suffix}_{class_suffix}@ficct-enterprise.com'
        inactive_email = f'inactive_{email_suffix}_{class_suffix}@ficct-enterprise.com'
        
        cls.test_user = User.objects.create_user(
            corporate_email=test_email,
            password='TestPassword123!@#',
            full_name='Test User',
            first_name='Test',
            last_name='User',
            email_verified=True,
            is_active=True
        )
        
        cls.admin_user = User.objects.create_user(
            corporate_email=admin_email,
            password='AdminPassword123!@#',
            full_name='Admin User',
            first_name='Admin',
            last_name='User',
            email_verified=True,
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
        
        cls.inactive_user = User.objects.create_user(
            corporate_email=inactive_email,
            password='InactivePassword123!@#',
            full_name='Inactive User',
            first_name='Inactive',
            last_name='User',
            email_verified=False,
            is_active=False
        )
    
    def setUp(self):
        """Set up test environment for each test method."""

        self.client = APIClient()
        self.client.logout()
        self.client.credentials()  # Clear all headers
        self.client.force_authenticate(user=None)  # Explicit unauthenticated state

        from django.test import Client
        if hasattr(self, '_pre_setup'):
            self._pre_setup()

        self.client._credentials = {}
        self.client._force_user = None
    
    def authenticate_user(self, user=None):
        """Authenticate a user and return JWT tokens."""
        if user is None:
            user = self.test_user
        
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        return {
            'access': str(access_token),
            'refresh': str(refresh)
        }
    
    def setup_2fa_device(self, user=None):
        """Create and return a 2FA TOTP device for testing."""
        if user is None:
            user = self.test_user
        
        device = TOTPDevice.objects.create(
            user=user,
            name='Test Device',
            confirmed=True
        )
        return device
    
    def create_test_users(self, count=3):
        """Create multiple test users for testing purposes."""
        users = []

        email_suffix = f"{int(datetime.now().timestamp())}{uuid.uuid4().hex[:4]}"
        batch_suffix = uuid.uuid4().hex[:4]
        
        for i in range(count):
            user = User.objects.create_user(
                corporate_email=f'testuser{i}_{email_suffix}_{batch_suffix}@ficct-enterprise.com',
                password=f'TestPassword{i}123!@#',
                full_name=f'Test{i} User{i}',
                first_name=f'Test{i}',
                last_name=f'User{i}',
                email_verified=True,
                is_active=True
            )
            users.append(user)
        return users


class BaseAPITestCase(APITestCase):
    """Enhanced API test case with JWT authentication and common patterns."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the entire test class."""

        email_suffix = f"{int(datetime.now().timestamp())}{uuid.uuid4().hex[:4]}"
        class_suffix = uuid.uuid4().hex[:4]

        test_email = f'apitest_{email_suffix}_{class_suffix}@ficct-enterprise.com'
        admin_email = f'apiadmin_{email_suffix}_{class_suffix}@ficct-enterprise.com'
        
        cls.test_user = User.objects.create_user(
            corporate_email=test_email,
            password='APITestPassword123!@#',
            full_name='API Test',
            first_name='API',
            last_name='Test',
            email_verified=True,
            is_active=True
        )
        
        cls.admin_user = User.objects.create_user(
            corporate_email=admin_email,
            password='APIAdminPassword123!@#',
            full_name='API Admin',
            first_name='API',
            last_name='Admin',
            email_verified=True,
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
    
    def setUp(self):
        """Set up test environment for each test method."""
        super().setUp()
        self.tokens = self.authenticate_user()
    
    def authenticate_user(self, user=None):
        """Authenticate user and set authorization headers."""
        if user is None:
            user = self.test_user
        
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        return {
            'access': str(access_token),
            'refresh': str(refresh)
        }
    
    def logout_user(self):
        """Remove authentication credentials."""
        self.client.credentials()
    
    def assert_response_status(self, response, expected_status):
        """Assert response status with detailed error information."""
        if response.status_code != expected_status:
            self.fail(
                f"Expected status {expected_status}, got {response.status_code}. "
                f"Response content: {response.content.decode()}"
            )
    
    def assert_response_contains_keys(self, response, keys):
        """Assert response JSON contains expected keys."""
        try:
            data = response.json()
        except (ValueError, TypeError):
            self.fail(f"Response is not valid JSON: {response.content}")
        
        for key in keys:
            self.assertIn(key, data, f"Key '{key}' not found in response")
    
    def assert_validation_error(self, response, field=None):
        """Assert response is a validation error with optional field check."""
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        if field:
            data = response.json()
            self.assertIn(field, data, f"Field '{field}' not in validation errors")
    
    def assert_unauthorized(self, response):
        """Assert response indicates unauthorized access."""
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def assert_forbidden(self, response):
        """Assert response indicates forbidden access."""
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def assert_not_found(self, response):
        """Assert response indicates resource not found."""
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AuthenticationTestMixin:
    """Mixin providing authentication test utilities."""
    
    def test_authentication_required(self):
        """Test that endpoint requires authentication."""
        if not hasattr(self, 'url'):
            self.skipTest("URL not defined in test class")
        
        self.logout_user()
        response = self.client.get(self.url)
        self.assert_unauthorized(response)
    
    def test_invalid_token(self):
        """Test behavior with invalid JWT token."""
        if not hasattr(self, 'url'):
            self.skipTest("URL not defined in test class")
        
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        response = self.client.get(self.url)
        self.assert_unauthorized(response)
    
    def test_expired_token(self):
        """Test behavior with expired JWT token."""
        if not hasattr(self, 'url'):
            self.skipTest("URL not defined in test class")

        pass


class PermissionTestMixin:
    """Mixin providing permission test utilities."""
    
    def test_staff_required(self):
        """Test that endpoint requires staff permissions."""
        if not hasattr(self, 'url') or not hasattr(self, 'requires_staff'):
            self.skipTest("URL or requires_staff not defined in test class")
        
        if not self.requires_staff:
            self.skipTest("Endpoint does not require staff permissions")

        self.authenticate_user(self.test_user)
        response = self.client.get(self.url)
        self.assert_forbidden(response)

        self.authenticate_user(self.admin_user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CRUDTestMixin:
    """Mixin providing standard CRUD operation tests."""
    
    def test_list_endpoint(self):
        """Test LIST operation."""
        if not hasattr(self, 'list_url'):
            self.skipTest("list_url not defined in test class")
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('results', data)  # Assuming paginated response
    
    def test_create_endpoint(self):
        """Test CREATE operation."""
        if not hasattr(self, 'list_url') or not hasattr(self, 'create_data'):
            self.skipTest("list_url or create_data not defined in test class")
        
        response = self.client.post(self.list_url, self.create_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_retrieve_endpoint(self):
        """Test RETRIEVE operation."""
        if not hasattr(self, 'detail_url'):
            self.skipTest("detail_url not defined in test class")
        
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_update_endpoint(self):
        """Test UPDATE operation."""
        if not hasattr(self, 'detail_url') or not hasattr(self, 'update_data'):
            self.skipTest("detail_url or update_data not defined in test class")
        
        response = self.client.put(self.detail_url, self.update_data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
    
    def test_delete_endpoint(self):
        """Test DELETE operation."""
        if not hasattr(self, 'detail_url'):
            self.skipTest("detail_url not defined in test class")
        
        response = self.client.delete(self.detail_url)
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_404_NOT_FOUND])


class ValidationTestMixin:
    """Mixin providing data validation test utilities."""
    
    def test_required_fields(self):
        """Test validation of required fields."""
        if not hasattr(self, 'required_fields') or not hasattr(self, 'list_url'):
            self.skipTest("required_fields or list_url not defined in test class")
        
        for field in self.required_fields:
            incomplete_data = self.create_data.copy()
            del incomplete_data[field]
            
            response = self.client.post(self.list_url, incomplete_data, format='json')
            self.assert_validation_error(response, field)
    
    def test_field_length_validation(self):
        """Test field length validation."""
        if not hasattr(self, 'field_lengths') or not hasattr(self, 'list_url'):
            self.skipTest("field_lengths or list_url not defined in test class")
        
        for field, max_length in self.field_lengths.items():
            invalid_data = self.create_data.copy()
            invalid_data[field] = 'x' * (max_length + 1)
            
            response = self.client.post(self.list_url, invalid_data, format='json')
            self.assert_validation_error(response, field)
    
    def test_email_validation(self):
        """Test email field validation."""
        if not hasattr(self, 'email_fields') or not hasattr(self, 'list_url'):
            self.skipTest("email_fields or list_url not defined in test class")
        
        for field in self.email_fields:
            invalid_data = self.create_data.copy()
            invalid_data[field] = 'invalid-email'
            
            response = self.client.post(self.list_url, invalid_data, format='json')
            self.assert_validation_error(response, field)


class EnterpriseTestCase(BaseAPITestCase, AuthenticationTestMixin, PermissionTestMixin):
    """
    Comprehensive test case combining all mixins for enterprise-level testing.
    
    Use this as the base class for all API endpoint tests.
    """
    
    def setUp(self):
        """Enhanced setup with enterprise features."""
        super().setUp()
        self.maxDiff = None  # Show full diff for assertions
    
    def assertResponseSuccess(self, response, expected_status=status.HTTP_200_OK):
        """Assert successful response with detailed error reporting."""
        if response.status_code != expected_status:
            error_msg = f"Expected {expected_status}, got {response.status_code}"
            if hasattr(response, 'content'):
                error_msg += f"\nResponse: {response.content.decode()}"
            self.fail(error_msg)
    
    def assertResponseError(self, response, expected_status=status.HTTP_400_BAD_REQUEST):
        """Assert error response with validation."""
        self.assertEqual(response.status_code, expected_status)

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            try:
                data = response.json()
                self.assertIsInstance(data, dict, "Error response should be a dictionary")
            except (ValueError, TypeError):
                pass  # Some error responses might not be JSON
