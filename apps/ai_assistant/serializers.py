from rest_framework import serializers


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
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError(
                "La pregunta debe ser al menos de un caracter."
            )
        return value.strip()


class AIAssistantResponseSerializer(serializers.Serializer):
    """Serializer for AI assistant responses."""
    
    answer = serializers.CharField(
        help_text="AI assistant's answer in Spanish"
    )
    suggestions = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        default=list,
        help_text="List of suggested actions or follow-up questions"
    )
    related_features = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
        help_text="List of related system features"
    )
    context_type = serializers.CharField(
        required=False,
        default='general',
        help_text="Context type that was used for the response"
    )
    timestamp = serializers.DateTimeField(
        required=False,
        allow_null=True,
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


class UMLCommandRequestSerializer(serializers.Serializer):
    """Serializer for UML command processing requests."""
    
    MODEL_CHOICES = [
        ('nova-pro', 'Amazon Nova Pro'),
        ('o4-mini', 'Azure OpenAI o4-mini'),
    ]
    
    command = serializers.CharField(
        max_length=2000,
        help_text="Natural language command for UML diagram generation"
    )
    diagram_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional UUID of diagram for context"
    )
    current_diagram_data = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Current diagram state with nodes and edges"
    )
    model = serializers.ChoiceField(
        choices=MODEL_CHOICES,
        required=False,
        allow_null=True,
        default=None,
        help_text="AI model to use for processing (defaults to nova-pro if not specified)"
    )
    
    def validate_command(self, value):
        """Validate command content."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Command must be at least 3 characters long."
            )
        return value.strip()


class UMLElementSerializer(serializers.Serializer):
    """Serializer for UML elements in command responses."""
    
    type = serializers.ChoiceField(
        choices=[('node', 'Node'), ('edge', 'Edge'), ('attribute_update', 'Attribute Update'), ('method_update', 'Method Update')],
        help_text="Type of UML element"
    )
    data = serializers.JSONField(
        help_text="Element data structure"
    )


class UMLCommandResponseSerializer(serializers.Serializer):
    """Serializer for UML command processing responses."""
    
    action = serializers.CharField(
        help_text="Type of action performed"
    )
    elements = serializers.ListField(
        child=UMLElementSerializer(),
        help_text="List of generated UML elements"
    )
    confidence = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        help_text="Confidence score for the interpretation"
    )
    interpretation = serializers.CharField(
        help_text="Human-readable interpretation of the command"
    )
    error = serializers.CharField(
        required=False,
        help_text="Error message if processing failed"
    )
    suggestion = serializers.CharField(
        required=False,
        help_text="Suggestion for fixing errors or improving command"
    )


class ModelInfoSerializer(serializers.Serializer):
    """Serializer for AI model information."""
    
    id = serializers.CharField(
        help_text="Model identifier (e.g., nova-pro, o4-mini)"
    )
    name = serializers.CharField(
        help_text="Display name of the model"
    )
    description = serializers.CharField(
        help_text="Description of model capabilities"
    )
    provider = serializers.CharField(
        help_text="Provider of the model (aws, azure)"
    )
    avg_response_time = serializers.IntegerField(
        help_text="Average response time in seconds"
    )
    cost_estimate = serializers.FloatField(
        help_text="Estimated cost per request in USD"
    )
    is_default = serializers.BooleanField(
        help_text="Whether this is the default model"
    )
    enabled = serializers.BooleanField(
        help_text="Whether the model is currently enabled"
    )


class AvailableModelsSerializer(serializers.Serializer):
    """Serializer for list of available AI models."""
    
    default = serializers.CharField(
        help_text="Default model identifier"
    )
    models = serializers.ListField(
        child=ModelInfoSerializer(),
        help_text="List of available models with their metadata"
    )


class SupportedCommandsSerializer(serializers.Serializer):
    """Serializer for supported command patterns documentation."""
    
    create_class = serializers.ListField(
        child=serializers.CharField(),
        help_text="Examples of class creation commands"
    )
    add_attribute = serializers.ListField(
        child=serializers.CharField(),
        help_text="Examples of attribute addition commands"
    )
    add_method = serializers.ListField(
        child=serializers.CharField(),
        help_text="Examples of method addition commands"
    )
    create_relationship = serializers.ListField(
        child=serializers.CharField(),
        help_text="Examples of relationship creation commands"
    )
