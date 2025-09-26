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


# Collaboration App Factories
class CollaborationSessionFactory(DjangoModelFactory):
    """Factory for collaboration sessions."""
    
    class Meta:
        model = 'collaboration.CollaborationSession'
    
    project = factory.SubFactory('base.test_factories.ProjectFactory')
    diagram = factory.SubFactory('base.test_factories.UMLDiagramFactory')
    host_user = factory.SubFactory(EnterpriseUserFactory)
    status = 'ACTIVE'
    session_data = factory.LazyFunction(lambda: {'settings': {'auto_save': True}})
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    ended_at = None
    is_active = True


class SessionParticipantFactory(DjangoModelFactory):
    """Factory for session participants."""
    
    class Meta:
        model = 'collaboration.CollaborationParticipant'
    
    session = factory.SubFactory(CollaborationSessionFactory)
    user = factory.SubFactory(EnterpriseUserFactory)
    role = fuzzy.FuzzyChoice(['HOST', 'EDITOR', 'VIEWER', 'COMMENTER'])
    joined_at = factory.LazyFunction(timezone.now)
    is_active = True


class UMLChangeEventFactory(DjangoModelFactory):
    """Factory for UML change events."""
    
    class Meta:
        model = 'collaboration.ChangeEvent'
    
    session = factory.SubFactory(CollaborationSessionFactory)
    diagram = factory.SubFactory('base.test_factories.UMLDiagramFactory')
    user = factory.SubFactory(EnterpriseUserFactory)
    event_type = fuzzy.FuzzyChoice([
        'ELEMENT_CREATED', 'ELEMENT_UPDATED', 'ELEMENT_DELETED', 'ELEMENT_MOVED',
        'RELATIONSHIP_CREATED', 'RELATIONSHIP_UPDATED', 'RELATIONSHIP_DELETED',
        'ATTRIBUTE_ADDED', 'ATTRIBUTE_UPDATED', 'ATTRIBUTE_REMOVED',
        'METHOD_ADDED', 'METHOD_UPDATED', 'METHOD_REMOVED', 'DIAGRAM_SAVED'
    ])
    element_type = fuzzy.FuzzyChoice(['class', 'interface', 'enum', 'relationship', 'attribute', 'method'])
    element_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    change_data = factory.LazyFunction(lambda: {'field': 'value'})
    previous_data = factory.LazyFunction(lambda: {})
    timestamp = factory.LazyFunction(timezone.now)
    is_broadcasted = False
    broadcast_count = 0
    sequence_number = factory.Sequence(lambda n: n + 1)
    conflict_resolved = False


# Projects App Factories
class WorkspaceFactory(DjangoModelFactory):
    """Factory for workspaces."""
    
    class Meta:
        model = 'projects.Workspace'
    
    name = factory.Faker('company')
    slug = factory.Sequence(lambda n: f'workspace-{n}')
    description = factory.Faker('text', max_nb_chars=200)
    owner = factory.SubFactory(EnterpriseUserFactory)
    status = 'ACTIVE'
    workspace_type = 'PERSONAL'


class ProjectFactory(DjangoModelFactory):
    """Factory for projects."""
    
    class Meta:
        model = 'projects.Project'
    
    name = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=500)
    workspace = factory.SubFactory(WorkspaceFactory)
    owner = factory.SubFactory(EnterpriseUserFactory)
    status = fuzzy.FuzzyChoice(['ACTIVE', 'ARCHIVED', 'SUSPENDED'])
    visibility = fuzzy.FuzzyChoice(['PRIVATE', 'TEAM', 'ORGANIZATION'])
    created_at = factory.LazyFunction(timezone.now)


class ProjectMemberFactory(DjangoModelFactory):
    """Factory for project members."""
    
    class Meta:
        model = 'projects.ProjectMember'
    
    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(EnterpriseUserFactory)
    role = fuzzy.FuzzyChoice(['owner', 'admin', 'developer', 'viewer'])
    permissions = factory.LazyFunction(lambda: ['read', 'write'])
    joined_at = factory.LazyFunction(timezone.now)


class ProjectTemplateFactory(DjangoModelFactory):
    """Factory for project templates."""
    
    class Meta:
        model = 'projects.ProjectTemplate'
    
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=300)
    template_type = fuzzy.FuzzyChoice(['springboot', 'microservice'])
    configuration = factory.LazyFunction(lambda: {'java_version': '11', 'spring_version': '2.7.0'})
    created_by = factory.SubFactory(EnterpriseUserFactory)
    is_public = True
    created_at = factory.LazyFunction(timezone.now)


# UML Diagrams App Factories
class UMLDiagramFactory(DjangoModelFactory):
    """Factory for UML diagrams."""
    
    class Meta:
        model = 'uml_diagrams.UMLDiagram'
    
    project = factory.SubFactory(ProjectFactory)
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


# Code Generation App Factories
class GenerationRequestFactory(DjangoModelFactory):
    """Factory for generation requests."""
    
    class Meta:
        model = 'code_generation.GenerationRequest'
    
    project = factory.SubFactory(ProjectFactory)
    uml_diagram = factory.SubFactory(UMLDiagramFactory)
    requested_by = factory.SubFactory(EnterpriseUserFactory)
    generation_type = fuzzy.FuzzyChoice(['full_project', 'entities_only', 'controllers_only'])
    status = fuzzy.FuzzyChoice(['pending', 'processing', 'completed', 'failed'])
    configuration = factory.LazyFunction(lambda: {
        'java_version': '11',
        'spring_version': '2.7.0',
        'database': 'postgresql'
    })
    created_at = factory.LazyFunction(timezone.now)


class GenerationTemplateFactory(DjangoModelFactory):
    """Factory for generation templates."""
    
    class Meta:
        model = 'code_generation.GenerationTemplate'
    
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    template_type = fuzzy.FuzzyChoice(['entity', 'repository', 'service', 'controller'])
    language = 'java'
    framework = 'springboot'
    template_content = factory.LazyFunction(lambda: '// Template content')
    created_by = factory.SubFactory(EnterpriseUserFactory)
    is_active = True
    created_at = factory.LazyFunction(timezone.now)


class GeneratedProjectFactory(DjangoModelFactory):
    """Factory for generated projects."""
    
    class Meta:
        model = 'code_generation.GeneratedProject'
    
    generation_request = factory.SubFactory(GenerationRequestFactory)
    project_name = factory.Faker('word')
    generated_files = factory.LazyFunction(lambda: {
        'entities': ['User.java', 'Product.java'],
        'repositories': ['UserRepository.java', 'ProductRepository.java']
    })
    download_url = factory.LazyFunction(lambda: f'/downloads/{uuid.uuid4()}.zip')
    file_size = factory.Faker('random_int', min=1024, max=10485760)  # 1KB to 10MB
    created_at = factory.LazyFunction(timezone.now)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))


class GenerationHistoryFactory(DjangoModelFactory):
    """Factory for generation history."""
    
    class Meta:
        model = 'code_generation.GenerationHistory'
    
    user = factory.SubFactory(EnterpriseUserFactory)
    project = factory.SubFactory(ProjectFactory)
    generation_request = factory.SubFactory(GenerationRequestFactory)
    action = fuzzy.FuzzyChoice(['created', 'downloaded', 'deleted'])
    details = factory.LazyFunction(lambda: {'files_count': 10})
    timestamp = factory.LazyFunction(timezone.now)


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
