from rest_framework import serializers
from typing import List


class AIAssistantQuestionSerializer(serializers.Serializer):
    """Serializer for AI assistant question requests."""
    
    CONTEXT_CHOICES = [
        ('general', 'General Help'),
        ('diagram', 'Diagram-Specific Help'),
        ('code-generation', 'Code Generation Help'),
    ]
    
    question = serializers.CharField(
        max_length=1000,
        help_text="User question in Spanish about UML diagrams or system functionality"
    )
    diagram_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional UUID of diagram for context-specific help"
    )
    context_type = serializers.ChoiceField(
        choices=CONTEXT_CHOICES,
        default='general',
        help_text="Type of context for the question"
    )
    
    def validate_question(self, value):
        """Validate question content."""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                "La pregunta debe tener al menos 5 caracteres."
            )
        return value.strip()


class AIAssistantResponseSerializer(serializers.Serializer):
    """Serializer for AI assistant responses."""
    
    answer = serializers.CharField(
        help_text="AI assistant's answer in Spanish"
    )
    suggestions = serializers.ListField(
        child=serializers.CharField(max_length=200),
        help_text="List of suggested actions or follow-up questions"
    )
    related_features = serializers.ListField(
        child=serializers.CharField(max_length=100),
        help_text="List of related system features"
    )
    context_type = serializers.CharField(
        help_text="Context type that was used for the response"
    )
    timestamp = serializers.DateTimeField(
        help_text="Response generation timestamp"
    )


class DiagramAnalysisSerializer(serializers.Serializer):
    """Serializer for diagram analysis responses."""
    
    complexity_score = serializers.IntegerField(
        help_text="Diagram complexity score (0-100)"
    )
    completeness = serializers.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        help_text="Diagram completeness level"
    )
    springboot_ready = serializers.BooleanField(
        help_text="Whether diagram is ready for SpringBoot code generation"
    )
    collaboration_active = serializers.BooleanField(
        help_text="Whether there are active collaborative sessions"
    )
    recommendations = serializers.ListField(
        child=serializers.CharField(max_length=200),
        help_text="List of recommendations for diagram improvement"
    )


class SystemStatisticsSerializer(serializers.Serializer):
    """Serializer for system statistics."""
    
    total_diagrams = serializers.IntegerField(
        help_text="Total number of diagrams in the system"
    )
    diagrams_today = serializers.IntegerField(
        help_text="Number of diagrams created today"
    )
    system_status = serializers.CharField(
        help_text="Current system operational status"
    )
