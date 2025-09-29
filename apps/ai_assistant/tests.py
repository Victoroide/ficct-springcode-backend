import uuid
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.uml_diagrams.models import UMLDiagram
from .services import AIAssistantService


class AIAssistantServiceTests(TestCase):
    """Test cases for AI Assistant Service."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create a test diagram
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
        # Mock OpenAI response
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
        # Mock OpenAI response
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
        
        # Create a test diagram
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
        # Mock OpenAI response
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
        # Mock OpenAI response
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
        
        # This should still work but return a response indicating diagram not found
        response = self.client.post(url, data, format='json')
        
        # The response might be 404 or 200 with error message depending on implementation
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
