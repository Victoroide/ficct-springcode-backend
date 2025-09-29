import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .services import AIAssistantService
from .serializers import (
    AIAssistantQuestionSerializer,
    AIAssistantResponseSerializer,
    DiagramAnalysisSerializer,
    SystemStatisticsSerializer
)


logger = logging.getLogger(__name__)


class AIAssistantRateThrottle(AnonRateThrottle):
    """Custom rate throttle for AI assistant endpoints."""
    rate = '30/hour'


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
        # Validate request data
        serializer = AIAssistantQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Initialize AI assistant service
        ai_service = AIAssistantService()
        
        # Get contextual help
        response_data = ai_service.get_contextual_help(
            user_question=validated_data['question'],
            diagram_id=validated_data.get('diagram_id'),
            context_type=validated_data.get('context_type', 'general')
        )
        
        # Validate response format
        response_serializer = AIAssistantResponseSerializer(data=response_data)
        if response_serializer.is_valid():
            logger.info(f"AI Assistant question processed: {validated_data['question'][:50]}...")
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"Invalid response format: {response_serializer.errors}")
            return Response({
                'error': 'Invalid response format',
                'details': response_serializer.errors
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error in ask_ai_assistant: {e}")
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
        # Validate request data
        serializer = AIAssistantQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Initialize AI assistant service
        ai_service = AIAssistantService()
        
        # Get diagram-specific help
        response_data = ai_service.get_contextual_help(
            user_question=validated_data['question'],
            diagram_id=str(diagram_id),
            context_type='diagram'
        )
        
        # Check if diagram was found
        if 'error' in response_data and 'not found' in response_data.get('answer', '').lower():
            return Response({
                'error': 'Diagram not found',
                'message': f'No se encontró el diagrama con ID: {diagram_id}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate and return response
        response_serializer = AIAssistantResponseSerializer(data=response_data)
        if response_serializer.is_valid():
            logger.info(f"AI Assistant diagram question processed for {diagram_id}")
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"Invalid response format: {response_serializer.errors}")
            return Response({
                'error': 'Invalid response format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error in ask_about_diagram: {e}")
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
        
        # Get diagram analysis
        analysis_data = ai_service.get_diagram_analysis(str(diagram_id))
        
        # Check if diagram was found
        if 'error' in analysis_data:
            return Response({
                'error': 'Diagram not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate and return analysis
        analysis_serializer = DiagramAnalysisSerializer(data=analysis_data)
        if analysis_serializer.is_valid():
            logger.info(f"Diagram analysis completed for {diagram_id}")
            return Response(analysis_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"Invalid analysis format: {analysis_serializer.errors}")
            return Response({
                'error': 'Invalid analysis format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error in get_diagram_analysis: {e}")
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
        
        # Get system statistics
        stats_data = ai_service.get_system_statistics()
        
        # Validate and return statistics
        stats_serializer = SystemStatisticsSerializer(data=stats_data)
        if stats_serializer.is_valid():
            return Response(stats_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"Invalid statistics format: {stats_serializer.errors}")
            return Response({
                'error': 'Invalid statistics format'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error in get_system_statistics: {e}")
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
        
        # Try to initialize the service
        ai_service = AIAssistantService()
        
        return Response({
            'status': 'healthy',
            'service': 'AI Assistant',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"AI Assistant health check failed: {e}")
        return Response({
            'status': 'unhealthy',
            'service': 'AI Assistant',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
