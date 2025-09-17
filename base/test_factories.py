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
import uuid

User = get_user_model()


class EnterpriseUserFactory(DjangoModelFactory):
    """Factory for creating EnterpriseUser instances."""
    
    class Meta:
        model = EnterpriseUser
    
    email = factory.Sequence(lambda n: f'user{n}@ficct-enterprise.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'TestPassword123!@#')
    is_email_verified = True
    is_active = True
    is_staff = False
    is_superuser = False
    date_joined = factory.LazyFunction(datetime.now)


class AdminUserFactory(EnterpriseUserFactory):
    """Factory for creating admin users."""
    
    email = factory.Sequence(lambda n: f'admin{n}@ficct-enterprise.com')
    is_staff = True
    is_superuser = True


class InactiveUserFactory(EnterpriseUserFactory):
    """Factory for creating inactive users."""
    
    email = factory.Sequence(lambda n: f'inactive{n}@ficct-enterprise.com')
    is_email_verified = False
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
    
    session_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    project = factory.SubFactory('base.test_factories.ProjectFactory')
    created_by = factory.SubFactory(EnterpriseUserFactory)
    is_active = True
    created_at = factory.LazyFunction(datetime.now)


class SessionParticipantFactory(DjangoModelFactory):
    """Factory for session participants."""
    
    class Meta:
        model = 'collaboration.SessionParticipant'
    
    session = factory.SubFactory(CollaborationSessionFactory)
    user = factory.SubFactory(EnterpriseUserFactory)
    role = fuzzy.FuzzyChoice(['viewer', 'editor', 'owner'])
    joined_at = factory.LazyFunction(datetime.now)
    is_active = True


class UMLChangeEventFactory(DjangoModelFactory):
    """Factory for UML change events."""
    
    class Meta:
        model = 'collaboration.UMLChangeEvent'
    
    session = factory.SubFactory(CollaborationSessionFactory)
    user = factory.SubFactory(EnterpriseUserFactory)
    event_type = fuzzy.FuzzyChoice(['create', 'update', 'delete'])
    element_type = fuzzy.FuzzyChoice(['class', 'relationship', 'attribute', 'method'])
    element_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    changes = factory.LazyFunction(lambda: {'field': 'value'})
    timestamp = factory.LazyFunction(datetime.now)


# Projects App Factories
class WorkspaceFactory(DjangoModelFactory):
    """Factory for workspaces."""
    
    class Meta:
        model = 'projects.Workspace'
    
    name = factory.Faker('company')
    description = factory.Faker('text', max_nb_chars=200)
    owner = factory.SubFactory(EnterpriseUserFactory)
    is_active = True
    created_at = factory.LazyFunction(datetime.now)


class ProjectFactory(DjangoModelFactory):
    """Factory for projects."""
    
    class Meta:
        model = 'projects.Project'
    
    name = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=500)
    workspace = factory.SubFactory(WorkspaceFactory)
    owner = factory.SubFactory(EnterpriseUserFactory)
    project_type = fuzzy.FuzzyChoice(['springboot', 'microservice', 'monolith'])
    status = fuzzy.FuzzyChoice(['active', 'archived', 'template'])
    created_at = factory.LazyFunction(datetime.now)


class ProjectMemberFactory(DjangoModelFactory):
    """Factory for project members."""
    
    class Meta:
        model = 'projects.ProjectMember'
    
    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(EnterpriseUserFactory)
    role = fuzzy.FuzzyChoice(['owner', 'admin', 'developer', 'viewer'])
    permissions = factory.LazyFunction(lambda: ['read', 'write'])
    joined_at = factory.LazyFunction(datetime.now)


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
    created_at = factory.LazyFunction(datetime.now)


# UML Diagrams App Factories
class UMLDiagramFactory(DjangoModelFactory):
    """Factory for UML diagrams."""
    
    class Meta:
        model = 'uml_diagrams.UMLDiagram'
    
    project = factory.SubFactory(ProjectFactory)
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    diagram_type = fuzzy.FuzzyChoice(['class', 'sequence', 'activity', 'use_case'])
    version = '1.0.0'
    created_by = factory.SubFactory(EnterpriseUserFactory)
    created_at = factory.LazyFunction(datetime.now)


class UMLElementFactory(DjangoModelFactory):
    """Factory for UML elements."""
    
    class Meta:
        model = 'uml_diagrams.UMLElement'
    
    diagram = factory.SubFactory(UMLDiagramFactory)
    element_type = fuzzy.FuzzyChoice(['class', 'interface', 'enum'])
    name = factory.Faker('word')
    properties = factory.LazyFunction(lambda: {'visibility': 'public'})
    position_x = factory.Faker('random_int', min=0, max=1000)
    position_y = factory.Faker('random_int', min=0, max=1000)
    created_at = factory.LazyFunction(datetime.now)


class UMLRelationshipFactory(DjangoModelFactory):
    """Factory for UML relationships."""
    
    class Meta:
        model = 'uml_diagrams.UMLRelationship'
    
    diagram = factory.SubFactory(UMLDiagramFactory)
    source_element = factory.SubFactory(UMLElementFactory)
    target_element = factory.SubFactory(UMLElementFactory)
    relationship_type = fuzzy.FuzzyChoice(['association', 'inheritance', 'composition', 'aggregation'])
    properties = factory.LazyFunction(lambda: {'multiplicity': '1..*'})
    created_at = factory.LazyFunction(datetime.now)


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
    created_at = factory.LazyFunction(datetime.now)


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
    created_at = factory.LazyFunction(datetime.now)


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
    created_at = factory.LazyFunction(datetime.now)
    expires_at = factory.LazyFunction(lambda: datetime.now() + timedelta(days=7))


class GenerationHistoryFactory(DjangoModelFactory):
    """Factory for generation history."""
    
    class Meta:
        model = 'code_generation.GenerationHistory'
    
    user = factory.SubFactory(EnterpriseUserFactory)
    project = factory.SubFactory(ProjectFactory)
    generation_request = factory.SubFactory(GenerationRequestFactory)
    action = fuzzy.FuzzyChoice(['created', 'downloaded', 'deleted'])
    details = factory.LazyFunction(lambda: {'files_count': 10})
    timestamp = factory.LazyFunction(datetime.now)


# Audit App Factories
class AuditLogFactory(DjangoModelFactory):
    """Factory for audit logs."""
    
    class Meta:
        model = 'audit.AuditLog'
    
    user = factory.SubFactory(EnterpriseUserFactory)
    action = fuzzy.FuzzyChoice(['CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT'])
    resource_type = fuzzy.FuzzyChoice(['User', 'Project', 'UMLDiagram'])
    resource_id = factory.Faker('random_int', min=1, max=1000)
    changes = factory.LazyFunction(lambda: {'field': 'new_value'})
    ip_address = factory.Faker('ipv4')
    user_agent = factory.Faker('user_agent')
    timestamp = factory.LazyFunction(datetime.now)


# Security App Factories  
class SecurityEventFactory(DjangoModelFactory):
    """Factory for security events."""
    
    class Meta:
        model = 'security.SecurityEvent'
    
    user = factory.SubFactory(EnterpriseUserFactory)
    event_type = fuzzy.FuzzyChoice(['LOGIN_ATTEMPT', 'PASSWORD_CHANGE', '2FA_SETUP'])
    severity = fuzzy.FuzzyChoice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
    description = factory.Faker('sentence')
    ip_address = factory.Faker('ipv4')
    user_agent = factory.Faker('user_agent')
    metadata = factory.LazyFunction(lambda: {'additional_info': 'test'})
    timestamp = factory.LazyFunction(datetime.now)


class IPWhitelistFactory(DjangoModelFactory):
    """Factory for IP whitelist entries."""
    
    class Meta:
        model = 'security.IPWhitelist'
    
    ip_address = factory.Faker('ipv4')
    description = factory.Faker('sentence')
    created_by = factory.SubFactory(EnterpriseUserFactory)
    is_active = True
    created_at = factory.LazyFunction(datetime.now)
