import uuid
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.uml_diagrams.models import UMLDiagram
from .services import AIAssistantService, UMLCommandProcessorService


class AIAssistantServiceTests(TestCase):
    """Test cases for AI Assistant Service."""
    
    def setUp(self):
        self.client = APIClient()

        self.test_diagram = UMLDiagram.objects.create(
            title="Test Diagram",
            description="A test UML diagram",
            session_id="test_session_123",
            diagram_type="CLASS",
            content={
                "classes": [
                    {
                        "id": "class1",
                        "name": "User",
                        "attributes": ["id: Long", "name: String"]
                    }
                ],
                "relationships": []
            }
        )
    
    @patch('apps.ai_assistant.services.ai_assistant_service.OpenAIService')
    def test_get_contextual_help_general(self, mock_openai_service):
        """Test getting general contextual help."""

        mock_service_instance = MagicMock()
        mock_service_instance.call_api.return_value = "Esta es una respuesta de ayuda general sobre UML."
        mock_openai_service.return_value = mock_service_instance
        
        ai_service = AIAssistantService()
        
        response = ai_service.get_contextual_help(
            user_question="¿Cómo creo un diagrama de clases?",
            context_type="general"
        )
        
        self.assertIn("answer", response)
        self.assertIn("suggestions", response)
        self.assertIn("related_features", response)
        self.assertEqual(response["context_type"], "general")
    
    @patch('apps.ai_assistant.services.ai_assistant_service.OpenAIService')
    def test_get_contextual_help_with_diagram(self, mock_openai_service):
        """Test getting help with diagram context."""

        mock_service_instance = MagicMock()
        mock_service_instance.call_api.return_value = "Basado en tu diagrama actual con la clase User..."
        mock_openai_service.return_value = mock_service_instance
        
        ai_service = AIAssistantService()
        
        response = ai_service.get_contextual_help(
            user_question="¿Cómo mejoro este diagrama?",
            diagram_id=str(self.test_diagram.id),
            context_type="diagram"
        )
        
        self.assertIn("answer", response)
        self.assertIn("suggestions", response)
        self.assertIn("related_features", response)
    
    def test_get_diagram_analysis(self):
        """Test diagram analysis functionality."""
        ai_service = AIAssistantService()
        
        analysis = ai_service.get_diagram_analysis(str(self.test_diagram.id))
        
        self.assertIn("complexity_score", analysis)
        self.assertIn("completeness", analysis)
        self.assertIn("springboot_ready", analysis)
        self.assertIn("collaboration_active", analysis)
        self.assertIn("recommendations", analysis)
    
    def test_get_system_statistics(self):
        """Test system statistics retrieval."""
        ai_service = AIAssistantService()
        
        stats = ai_service.get_system_statistics()
        
        self.assertIn("total_diagrams", stats)
        self.assertIn("diagrams_today", stats)
        self.assertIn("system_status", stats)
        self.assertGreaterEqual(stats["total_diagrams"], 1)  # We created one diagram


class AIAssistantViewsTests(TestCase):
    """Test cases for AI Assistant API views."""
    
    def setUp(self):
        self.client = APIClient()

        self.test_diagram = UMLDiagram.objects.create(
            title="Test Diagram",
            description="A test UML diagram",
            session_id="test_session_123",
            diagram_type="CLASS",
            content={
                "classes": [
                    {
                        "id": "class1",
                        "name": "User",
                        "attributes": ["id: Long", "name: String"]
                    }
                ],
                "relationships": []
            }
        )
    
    @patch('apps.ai_assistant.services.ai_assistant_service.OpenAIService')
    def test_ask_ai_assistant_endpoint(self, mock_openai_service):
        """Test the main AI assistant ask endpoint."""

        mock_service_instance = MagicMock()
        mock_service_instance.call_api.return_value = "Esta es una respuesta de prueba."
        mock_openai_service.return_value = mock_service_instance
        
        url = reverse('ai_assistant:ask')
        data = {
            "question": "¿Cómo creo un diagrama UML?",
            "context_type": "general"
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("answer", response.data)
        self.assertIn("suggestions", response.data)
        self.assertIn("related_features", response.data)
    
    def test_ask_ai_assistant_invalid_data(self):
        """Test AI assistant endpoint with invalid data."""
        url = reverse('ai_assistant:ask')
        data = {
            "question": "",  # Empty question should be invalid
            "context_type": "general"
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
    
    @patch('apps.ai_assistant.services.ai_assistant_service.OpenAIService')
    def test_ask_about_diagram_endpoint(self, mock_openai_service):
        """Test the diagram-specific AI assistant endpoint."""

        mock_service_instance = MagicMock()
        mock_service_instance.call_api.return_value = "Análisis del diagrama específico."
        mock_openai_service.return_value = mock_service_instance
        
        url = reverse('ai_assistant:ask_about_diagram', kwargs={'diagram_id': self.test_diagram.id})
        data = {
            "question": "¿Cómo mejoro este diagrama?",
            "context_type": "diagram"
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("answer", response.data)
    
    def test_ask_about_nonexistent_diagram(self):
        """Test asking about a diagram that doesn't exist."""
        nonexistent_id = uuid.uuid4()
        url = reverse('ai_assistant:ask_about_diagram', kwargs={'diagram_id': nonexistent_id})
        data = {
            "question": "¿Cómo mejoro este diagrama?",
            "context_type": "diagram"
        }

        response = self.client.post(url, data, format='json')

        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK])
    
    def test_get_diagram_analysis_endpoint(self):
        """Test the diagram analysis endpoint."""
        url = reverse('ai_assistant:diagram_analysis', kwargs={'diagram_id': self.test_diagram.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("complexity_score", response.data)
        self.assertIn("completeness", response.data)
        self.assertIn("springboot_ready", response.data)
        self.assertIn("collaboration_active", response.data)
        self.assertIn("recommendations", response.data)
    
    def test_get_system_statistics_endpoint(self):
        """Test the system statistics endpoint."""
        url = reverse('ai_assistant:system_statistics')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_diagrams", response.data)
        self.assertIn("diagrams_today", response.data)
        self.assertIn("system_status", response.data)
    
    def test_ai_assistant_health_endpoint(self):
        """Test the AI assistant health check endpoint."""
        url = reverse('ai_assistant:health')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)
        self.assertIn("service", response.data)
        self.assertEqual(response.data["service"], "AI Assistant")


class UMLCommandProcessorServiceTests(TestCase):
    """Test cases for UML command processor service."""
    
    def setUp(self):
        self.service = UMLCommandProcessorService()

        self.test_diagram = UMLDiagram.objects.create(
            title="Test Diagram",
            session_id="test-session",
            content={
                "nodes": [
                    {
                        "id": "class-user",
                        "data": {
                            "label": "User",
                            "attributes": [
                                {"id": "attr-1", "name": "name", "type": "String", "visibility": "private"}
                            ],
                            "methods": [],
                            "nodeType": "class"
                        },
                        "type": "class",
                        "position": {"x": 100, "y": 100}
                    }
                ],
                "edges": []
            }
        )
    
    def test_pattern_based_class_creation(self):
        """Test pattern-based class creation."""
        result = self.service.process_command("Create class Product")
        
        self.assertEqual(result['action'], 'create_class')
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['type'], 'node')
        self.assertEqual(result['elements'][0]['data']['data']['label'], 'Product')
        self.assertGreaterEqual(result['confidence'], 0.8)
    
    def test_pattern_based_attribute_creation(self):
        """Test pattern-based attribute creation."""
        result = self.service.process_command("with attributes name string, age int")
        
        self.assertEqual(result['action'], 'add_attribute')
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['type'], 'attribute_update')
        
        attributes = result['elements'][0]['data']['attributes']
        self.assertEqual(len(attributes), 2)
        self.assertEqual(attributes[0]['name'], 'name')
        self.assertEqual(attributes[0]['type'], 'String')
        self.assertEqual(attributes[1]['name'], 'age')
        self.assertEqual(attributes[1]['type'], 'Integer')
    
    def test_pattern_based_method_creation(self):
        """Test pattern-based method creation."""
        result = self.service.process_command("add method login")
        
        self.assertEqual(result['action'], 'add_method')
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['type'], 'method_update')
        
        methods = result['elements'][0]['data']['methods']
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0]['name'], 'login')
        self.assertEqual(methods[0]['returnType'], 'void')
        self.assertEqual(methods[0]['visibility'], 'public')
    
    def test_pattern_based_relationship_creation(self):
        """Test pattern-based relationship creation."""
        result = self.service.process_command("User has many Orders")
        
        self.assertEqual(result['action'], 'create_relationship')
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['type'], 'edge')
        
        edge_data = result['elements'][0]['data']
        self.assertEqual(edge_data['type'], 'umlRelationship')
        self.assertEqual(edge_data['data']['relationshipType'], 'ASSOCIATION')
        self.assertEqual(edge_data['data']['sourceMultiplicity'], '1')
        self.assertEqual(edge_data['data']['targetMultiplicity'], '1..*')
    
    def test_inheritance_relationship_pattern(self):
        """Test inheritance relationship pattern recognition."""
        result = self.service.process_command("Admin extends User")
        
        self.assertEqual(result['action'], 'create_relationship')
        edge_data = result['elements'][0]['data']
        self.assertEqual(edge_data['data']['relationshipType'], 'INHERITANCE')
    
    def test_multilingual_support(self):
        """Test multilingual command support."""

        result_es = self.service.process_command("Crear clase Usuario")
        self.assertEqual(result_es['action'], 'create_class')
        self.assertEqual(result_es['elements'][0]['data']['data']['label'], 'Usuario')

        result_attr_es = self.service.process_command("con atributos nombre string, edad int")
        self.assertEqual(result_attr_es['action'], 'add_attribute')
        self.assertEqual(len(result_attr_es['elements'][0]['data']['attributes']), 2)
    
    def test_type_mapping(self):
        """Test data type mapping functionality."""
        result = self.service.process_command("with attributes count int, active bool, created date")
        
        attributes = result['elements'][0]['data']['attributes']
        type_mapping = {attr['name']: attr['type'] for attr in attributes}
        
        self.assertEqual(type_mapping['count'], 'Integer')
        self.assertEqual(type_mapping['active'], 'Boolean')
        self.assertEqual(type_mapping['created'], 'Date')
    
    def test_diagram_context_integration(self):
        """Test diagram context integration."""
        result = self.service.process_command(
            "Create class Order", 
            diagram_id=str(self.test_diagram.id)
        )
        
        self.assertEqual(result['action'], 'create_class')

        position = result['elements'][0]['data']['position']
        self.assertTrue(position['x'] >= 100 and position['y'] >= 100)
    
    def test_intelligent_positioning(self):
        """Test intelligent positioning algorithm."""

        position1 = self.service._calculate_next_position(
            "DIAGRAMA EXISTENTE: Test\nCLASES EXISTENTES: User, Product"
        )
        position2 = self.service._calculate_next_position(
            "DIAGRAMA EXISTENTE: Test\nCLASES EXISTENTES: User, Product, Category, Order"
        )

        self.assertNotEqual(position1, position2)
    
    def test_supported_commands_documentation(self):
        """Test supported commands documentation."""
        commands = self.service.get_supported_commands()
        
        self.assertIn('create_class', commands)
        self.assertIn('add_attribute', commands)
        self.assertIn('add_method', commands)
        self.assertIn('create_relationship', commands)

        self.assertGreater(len(commands['create_class']), 0)
        self.assertGreater(len(commands['add_attribute']), 0)


class UMLCommandProcessorAPITests(TestCase):
    """Test cases for UML command processor API endpoints."""
    
    def setUp(self):
        self.client = APIClient()

        self.test_diagram = UMLDiagram.objects.create(
            title="Test Diagram",
            session_id="test-session",
            content={"nodes": [], "edges": []}
        )
    
    def test_process_uml_command_endpoint(self):
        """Test the main command processing endpoint."""
        data = {
            "command": "Create class User"
        }
        
        response = self.client.post('/api/ai-assistant/process-command/', data, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('action', response.data)
        self.assertIn('elements', response.data)
        self.assertIn('confidence', response.data)
        self.assertIn('interpretation', response.data)
    
    def test_process_uml_command_for_diagram_endpoint(self):
        """Test the diagram-specific command processing endpoint."""
        data = {
            "command": "Add class Product"
        }
        
        response = self.client.post(
            f'/api/ai-assistant/process-command/{self.test_diagram.id}/', 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('action', response.data)
        self.assertIn('elements', response.data)
    
    def test_get_supported_commands_endpoint(self):
        """Test the supported commands documentation endpoint."""
        response = self.client.get('/api/ai-assistant/supported-commands/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('create_class', response.data)
        self.assertIn('add_attribute', response.data)
        self.assertIn('add_method', response.data)
        self.assertIn('create_relationship', response.data)
    
    def test_command_validation(self):
        """Test command validation in API endpoints."""

        data = {"command": ""}
        response = self.client.post('/api/ai-assistant/process-command/', data, format='json')
        self.assertEqual(response.status_code, 400)

        data = {"command": "hi"}
        response = self.client.post('/api/ai-assistant/process-command/', data, format='json')
        self.assertEqual(response.status_code, 400)

        data = {"diagram_id": str(self.test_diagram.id)}
        response = self.client.post('/api/ai-assistant/process-command/', data, format='json')
        self.assertEqual(response.status_code, 400)
