import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from base.settings import env
from .services import AIAssistantService, UMLCommandProcessorService
from .serializers import (
    AIAssistantQuestionSerializer,
    AIAssistantResponseSerializer,
    DiagramAnalysisSerializer,
    SystemStatisticsSerializer,
    UMLCommandRequestSerializer,
    UMLCommandResponseSerializer,
    SupportedCommandsSerializer
)


logger = logging.getLogger(__name__)


class AIAssistantRateThrottle(AnonRateThrottle):
    """Custom rate throttle for AI assistant endpoints."""
    rate = env('AI_ASSISTANT_RATE_LIMIT', default='100/minute')


@extend_schema(
    tags=['AI Assistant'],
    summary='Ask AI Assistant for Help',
    description='Get contextual help from AI assistant about UML diagrams and system functionality',
    request=AIAssistantQuestionSerializer,
    responses={
        200: AIAssistantResponseSerializer,
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        429: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'message': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AIAssistantRateThrottle])
def ask_ai_assistant(request):
    """
    Main endpoint for asking AI assistant questions.
    
    Provides contextual help about UML diagrams, system functionality,
    and best practices in Spanish.
    """
    try:

        serializer = AIAssistantQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        ai_service = AIAssistantService()

        response_data = ai_service.get_contextual_help(
            user_question=validated_data['question'],
            diagram_id=validated_data.get('diagram_id'),
            context_type=validated_data.get('context_type', 'general')
        )

        response_serializer = AIAssistantResponseSerializer(data=response_data)
        if response_serializer.is_valid():
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid response format',
                'details': response_serializer.errors
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error',
            'message': 'Lo siento, hubo un error procesando tu pregunta. Por favor, inténtalo de nuevo.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='Ask About Specific Diagram',
    description='Get AI help about a specific UML diagram with context-aware assistance',
    request=AIAssistantQuestionSerializer,
    responses={
        200: AIAssistantResponseSerializer,
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'message': {'type': 'string'}
            }
        }
    },
    parameters=[
        OpenApiParameter(
            name='diagram_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the diagram to ask about'
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AIAssistantRateThrottle])
def ask_about_diagram(request, diagram_id):
    """
    Get AI assistant help about a specific diagram.
    
    Provides context-aware assistance based on the current state
    of the specified diagram.
    """
    try:

        serializer = AIAssistantQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        ai_service = AIAssistantService()

        response_data = ai_service.get_contextual_help(
            user_question=validated_data['question'],
            diagram_id=str(diagram_id),
            context_type='diagram'
        )

        if 'error' in response_data and 'not found' in response_data.get('answer', '').lower():
            return Response({
                'error': 'Diagram not found',
                'message': f'No se encontró el diagrama con ID: {diagram_id}'
            }, status=status.HTTP_404_NOT_FOUND)

        response_serializer = AIAssistantResponseSerializer(data=response_data)
        if response_serializer.is_valid():
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid response format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error',
            'message': 'Error procesando la pregunta sobre el diagrama.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='Get Diagram Analysis',
    description='Get AI-powered analysis and recommendations for a specific diagram',
    responses={
        200: DiagramAnalysisSerializer,
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    parameters=[
        OpenApiParameter(
            name='diagram_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the diagram to analyze'
        )
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AIAssistantRateThrottle])
def get_diagram_analysis(request, diagram_id):
    """
    Get AI-powered analysis of a specific diagram.
    
    Provides complexity analysis, completeness assessment,
    and improvement recommendations.
    """
    try:
        ai_service = AIAssistantService()

        analysis_data = ai_service.get_diagram_analysis(str(diagram_id))

        if 'error' in analysis_data:
            return Response({
                'error': 'Diagram not found'
            }, status=status.HTTP_404_NOT_FOUND)

        analysis_serializer = DiagramAnalysisSerializer(data=analysis_data)
        if analysis_serializer.is_valid():
            return Response(analysis_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid analysis format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='Get System Statistics',
    description='Get current system statistics for AI assistant context',
    responses={200: SystemStatisticsSerializer}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_system_statistics(request):
    """
    Get system statistics for AI assistant context.
    
    Provides current system status and usage statistics.
    """
    try:
        ai_service = AIAssistantService()

        stats_data = ai_service.get_system_statistics()

        stats_serializer = SystemStatisticsSerializer(data=stats_data)
        if stats_serializer.is_valid():
            return Response(stats_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid statistics format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='AI Assistant Health Check',
    description='Check if AI assistant service is operational',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'service': {'type': 'string'},
                'timestamp': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def ai_assistant_health(request):
    """Health check for AI assistant service."""
    try:
        from datetime import datetime

        ai_service = AIAssistantService()
        
        return Response({
            'status': 'healthy',
            'service': 'AI Assistant',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'service': 'AI Assistant',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@extend_schema(
    tags=['AI Assistant'],
    summary='Process Natural Language UML Command',
    description='Convert natural language commands into UML diagram elements using AI processing',
    request=UMLCommandRequestSerializer,
    responses={
        200: UMLCommandResponseSerializer,
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        429: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'message': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AIAssistantRateThrottle])
def process_uml_command(request):
    """
    Process natural language commands for UML diagram generation.
    
    Accepts commands in multiple languages and generates React Flow compatible
    JSON structures for UML elements like classes, attributes, methods, and relationships.
    """
    try:

        serializer = UMLCommandRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        processor_service = UMLCommandProcessorService()

        result = processor_service.process_command(
            command=validated_data['command'],
            diagram_id=validated_data.get('diagram_id'),
            current_diagram_data=validated_data.get('current_diagram_data')
        )

        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = UMLCommandResponseSerializer(data=result)
        if response_serializer.is_valid():
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid response format',
                'details': response_serializer.errors
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error',
            'message': 'Error processing UML command. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='Process UML Command for Specific Diagram',
    description='Process natural language command with context from a specific diagram',
    request=UMLCommandRequestSerializer,
    responses={
        200: UMLCommandResponseSerializer,
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'message': {'type': 'string'}
            }
        }
    },
    parameters=[
        OpenApiParameter(
            name='diagram_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the diagram to use for context'
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AIAssistantRateThrottle])
def process_uml_command_for_diagram(request, diagram_id):
    """
    Process natural language command with diagram context.
    
    Uses the specified diagram's current state to provide context-aware
    UML element generation and validation.
    """
    try:

        serializer = UMLCommandRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        processor_service = UMLCommandProcessorService()

        result = processor_service.process_command(
            command=validated_data['command'],
            diagram_id=str(diagram_id),
            current_diagram_data=validated_data.get('current_diagram_data')
        )

        if 'error' in result and 'not found' in result.get('error', '').lower():
            return Response({
                'error': 'Diagram not found',
                'message': f'No diagram found with ID: {diagram_id}'
            }, status=status.HTTP_404_NOT_FOUND)

        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = UMLCommandResponseSerializer(data=result)
        if response_serializer.is_valid():
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid response format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error',
            'message': 'Error processing UML command for diagram.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI Assistant'],
    summary='Get Supported Command Patterns',
    description='Get documentation of supported natural language command patterns for UML generation',
    responses={200: SupportedCommandsSerializer}
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_supported_commands(request):
    """
    Get documentation of supported command patterns.
    
    Returns examples of supported natural language commands for
    creating UML elements in multiple languages.
    """
    try:
        processor_service = UMLCommandProcessorService()

        commands_data = processor_service.get_supported_commands()

        commands_serializer = SupportedCommandsSerializer(data=commands_data)
        if commands_serializer.is_valid():
            return Response(commands_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid commands format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
