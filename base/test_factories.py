"""
Enterprise Test Data Factories

Factory classes for generating realistic test data across all Django apps.
Uses FactoryBoy for dynamic test data generation with proper relationships.
"""

import factory
from factory.django import DjangoModelFactory
from factory import fuzzy
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice
from apps.accounts.models import EnterpriseUser
from datetime import datetime, timedelta
from django.utils import timezone
import uuid

User = get_user_model()


class EnterpriseUserFactory(DjangoModelFactory):
    """Factory for creating EnterpriseUser instances."""
    
    class Meta:
        model = EnterpriseUser
    
    corporate_email = factory.Sequence(lambda n: f'user{n}@ficct-enterprise.com')
    full_name = factory.Faker('name')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'TestPassword123!@#')
    email_verified = True
    is_active = True
    is_staff = False
    is_superuser = False
    date_joined = factory.LazyFunction(timezone.now)


class AdminUserFactory(EnterpriseUserFactory):
    """Factory for creating admin users."""
    
    corporate_email = factory.Sequence(lambda n: f'admin{n}@ficct-enterprise.com')
    is_staff = True
    is_superuser = True


class InactiveUserFactory(EnterpriseUserFactory):
    """Factory for creating inactive users."""
    
    corporate_email = factory.Sequence(lambda n: f'inactive{n}@ficct-enterprise.com')
    email_verified = False
    is_active = False


class TOTPDeviceFactory(DjangoModelFactory):
    """Factory for creating TOTP devices for 2FA testing."""
    
    class Meta:
        model = TOTPDevice
    
    user = factory.SubFactory(EnterpriseUserFactory)
    name = factory.Faker('word')
    confirmed = True


# UML Diagrams App Factories (Refactored - no project dependency)


# UML Diagrams App Factories
class UMLDiagramFactory(DjangoModelFactory):
    """Factory for UML diagrams."""
    
    class Meta:
        model = 'uml_diagrams.UMLDiagram'
    
    owner = factory.SubFactory(EnterpriseUserFactory)
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    diagram_type = fuzzy.FuzzyChoice(['CLASS', 'SEQUENCE', 'USE_CASE', 'ACTIVITY', 'STATE', 'COMPONENT', 'DEPLOYMENT'])
    status = fuzzy.FuzzyChoice(['DRAFT', 'IN_REVIEW', 'APPROVED', 'DEPRECATED'])
    visibility = fuzzy.FuzzyChoice(['PRIVATE', 'TEAM', 'ORGANIZATION', 'PUBLIC'])
    created_by = factory.SubFactory(EnterpriseUserFactory)
    last_modified_by = factory.SubFactory(EnterpriseUserFactory)
    diagram_data = factory.LazyFunction(lambda: {'classes': [], 'relationships': []})
    layout_config = factory.LazyFunction(lambda: {})
    validation_results = factory.LazyFunction(lambda: {})
    tags = factory.LazyFunction(lambda: [])
    metadata = factory.LazyFunction(lambda: {})
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    last_validated_at = None
    version_number = 1
    is_template = False
    parent_template = None


class UMLElementFactory(DjangoModelFactory):
    """Factory for UML elements (using UMLClass model)."""
    
    class Meta:
        model = 'uml_diagrams.UMLClass'
    
    diagram = factory.SubFactory(UMLDiagramFactory)
    name = factory.Faker('word')
    package = factory.Faker('word')
    class_type = fuzzy.FuzzyChoice(['CLASS', 'ABSTRACT_CLASS', 'INTERFACE', 'ENUM', 'RECORD'])
    visibility = 'PUBLIC'
    is_abstract = False
    is_final = False
    is_static = False
    attributes = factory.LazyFunction(lambda: [])
    methods = factory.LazyFunction(lambda: [])
    position_x = factory.Faker('random_int', min=0, max=1000)
    position_y = factory.Faker('random_int', min=0, max=1000)
    width = 120.0
    height = 80.0
    created_by = factory.SubFactory(EnterpriseUserFactory)
    created_at = factory.LazyFunction(timezone.now)


class UMLRelationshipFactory(DjangoModelFactory):
    """Factory for UML relationships."""
    
    class Meta:
        model = 'uml_diagrams.UMLRelationship'
    
    diagram = factory.SubFactory(UMLDiagramFactory)
    name = factory.Faker('word')
    relationship_type = fuzzy.FuzzyChoice(['ASSOCIATION', 'AGGREGATION', 'COMPOSITION', 'INHERITANCE', 'REALIZATION', 'DEPENDENCY', 'GENERALIZATION'])
    source_class = factory.SubFactory(UMLElementFactory)
    target_class = factory.SubFactory(UMLElementFactory)
    source_multiplicity = fuzzy.FuzzyChoice(['0..1', '1', '0..*', '1..*', '*'])
    target_multiplicity = fuzzy.FuzzyChoice(['0..1', '1', '0..*', '1..*', '*'])
    source_role = ''
    target_role = ''
    source_navigable = True
    target_navigable = True
    documentation = ''
    stereotype = ''
    style_config = factory.LazyFunction(lambda: {})
    path_points = factory.LazyFunction(lambda: [])
    created_by = factory.SubFactory(EnterpriseUserFactory)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)




# Audit App Factories
class AuditLogFactory(DjangoModelFactory):
    """Factory for audit logs."""
    
    class Meta:
        model = 'audit.AuditLog'
    
    user = factory.SubFactory(EnterpriseUserFactory)
    action_type = fuzzy.FuzzyChoice(['LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'API_ACCESS', 'DATA_CREATE'])
    resource_type = fuzzy.FuzzyChoice(['User', 'Project', 'UMLDiagram'])
    resource_id = factory.Faker('random_int', min=1, max=1000)
    changes = factory.LazyFunction(lambda: {'field': 'new_value'})
    ip_address = factory.Faker('ipv4')
    user_agent = factory.Faker('user_agent')
    timestamp = factory.LazyFunction(timezone.now)


# Security App Factories  
class SecurityAlertFactory(DjangoModelFactory):
    """Factory for security alerts."""
    
    class Meta:
        model = 'audit.SecurityAlert'
    
    alert_type = fuzzy.FuzzyChoice(['BRUTE_FORCE', 'ACCOUNT_TAKEOVER', 'SUSPICIOUS_LOCATION', 'RATE_LIMITING', 'MULTIPLE_FAILURES', 'ANOMALOUS_BEHAVIOR', 'PRIVILEGE_ESCALATION', 'DATA_EXFILTRATION', 'SESSION_ANOMALY', 'API_ABUSE'])
    status = fuzzy.FuzzyChoice(['OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE', 'ESCALATED'])
    severity = fuzzy.FuzzyChoice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
    user = factory.SubFactory(EnterpriseUserFactory)
    title = factory.Faker('sentence')
    description = factory.Faker('text', max_nb_chars=200)
    risk_score = factory.Faker('random_int', min=0, max=100)
    ip_address = factory.Faker('ipv4')
    user_agent = factory.Faker('user_agent')
    affected_resources = factory.LazyFunction(lambda: [])
    detection_rules = factory.LazyFunction(lambda: [])
    confidence_score = factory.Faker('random_int', min=0, max=100)
    investigation_notes = ''
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    first_seen = factory.LazyFunction(timezone.now)
    last_seen = factory.LazyFunction(timezone.now)


class IPWhitelistFactory(DjangoModelFactory):
    """Factory for IP whitelist entries."""
    
    class Meta:
        model = 'security.IPWhitelist'
    
    ip_address = factory.Faker('ipv4')
    description = factory.Faker('sentence')
    is_active = True
    access_level = fuzzy.FuzzyChoice(['ADMIN', 'API', 'FULL', 'LIMITED', 'READONLY'])
    allowed_paths = factory.LazyFunction(lambda: [])
    blocked_paths = factory.LazyFunction(lambda: [])
    is_network_range = False
    network_mask = None
    allowed_countries = factory.LazyFunction(lambda: [])
    access_start_time = None
    access_end_time = None
    timezone_name = 'UTC'
    max_requests_per_hour = None
    max_concurrent_sessions = None
    created_by = factory.SubFactory(EnterpriseUserFactory)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    last_used = None
    usage_count = 0
    last_user_agent = ''
    expires_at = None
    is_trusted = False
    requires_2fa = True
    bypass_rate_limits = False
