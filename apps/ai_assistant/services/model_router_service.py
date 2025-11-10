"""Model Router Service for Command Processing.

Routes natural language commands to appropriate AI model based on selection.
Provides unified interface for multiple models (Nova Pro, o4-mini, etc.).
"""

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class ModelNotAvailableError(Exception):
    """Raised when selected model is not available."""
    pass


class ModelRouterService:
    """
    Routes command processing requests to selected AI model.
    
    Supported models:
        - llama4-maverick: Llama 4 Maverick 17B (default, 70% cheaper, 1M context)
        - nova-pro: Amazon Nova Pro (fast and reliable)
        - o4-mini: Azure OpenAI o4-mini (advanced reasoning, slower)
    
    Features:
        - Automatic model selection based on availability
        - Fallback to alternative models if primary fails
        - Unified response format across all models
        - Performance and cost tracking per model
    
    Example:
        router = ModelRouterService()
        result = router.process_command(
            command="crea clase User",
            model="llama4-maverick"
        )
    """
    
    def __init__(self):
        """Initialize model router with available services."""
        self.logger = logging.getLogger(__name__)
        self._services = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize available model services."""
        try:
            from .llama4_command_service import Llama4CommandService
            self._services['llama4-maverick'] = Llama4CommandService()
            self.logger.info("Llama 4 Maverick service initialized")
        except Exception as e:
            self.logger.warning(f"Llama 4 Maverick service not available: {e}")
        
        try:
            from .nova_command_service import NovaCommandService
            self._services['nova-pro'] = NovaCommandService()
            self.logger.info("Nova Pro service initialized")
        except Exception as e:
            self.logger.warning(f"Nova Pro service not available: {e}")
        
        try:
            from .command_processor_service import UMLCommandProcessorService
            self._services['o4-mini'] = UMLCommandProcessorService()
            self.logger.info("o4-mini service initialized")
        except Exception as e:
            self.logger.warning(f"o4-mini service not available: {e}")
        
        if not self._services:
            self.logger.error("No AI models available for command processing")
    
    def process_command(
        self,
        command: str,
        model: Optional[str] = None,
        diagram_id: Optional[str] = None,
        current_diagram_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process natural language command using selected model.
        
        Args:
            command: Natural language command
            model: Model identifier (nova-pro, o4-mini) or None for default
            diagram_id: Optional diagram ID for context
            current_diagram_data: Current diagram state
            
        Returns:
            Dict with action, elements, confidence, interpretation, metadata
            
        Raises:
            ModelNotAvailableError: If selected model is not available
        """
        selected_model = model or self._get_default_model()
        
        self.logger.info(f"Processing command with model: {selected_model}")
        
        if not self._is_model_available(selected_model):
            self.logger.warning(f"Model {selected_model} not available, trying fallback")
            selected_model = self._get_fallback_model(selected_model)
            
            if not selected_model:
                return {
                    'action': 'error',
                    'elements': [],
                    'confidence': 0.0,
                    'interpretation': 'No AI models available',
                    'error': 'AI service unavailable. Please contact support.',
                    'suggestion': 'Check server configuration or try again later.',
                    'metadata': {
                        'error_type': 'no_models_available'
                    }
                }
        
        try:
            service = self._get_model_service(selected_model)
            
            result = service.process_command(
                command=command,
                diagram_id=diagram_id,
                current_diagram_data=current_diagram_data
            )
            
            if 'metadata' not in result:
                result['metadata'] = {}
            
            result['metadata']['model_used'] = selected_model
            result['metadata']['model_requested'] = model or 'default'
            
            self.logger.info(f"Command processed successfully with {selected_model}: "
                           f"action={result.get('action')}, "
                           f"elements={len(result.get('elements', []))}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing command with {selected_model}: {e}", exc_info=True)
            
            fallback_model = self._get_fallback_model(selected_model)
            if fallback_model and fallback_model != selected_model:
                self.logger.info(f"Attempting fallback to {fallback_model}")
                return self.process_command(
                    command=command,
                    model=fallback_model,
                    diagram_id=diagram_id,
                    current_diagram_data=current_diagram_data
                )
            
            return {
                'action': 'error',
                'elements': [],
                'confidence': 0.0,
                'interpretation': f'Command processing failed: {str(e)}',
                'error': str(e),
                'suggestion': 'Please try again or rephrase your command.',
                'metadata': {
                    'model_used': selected_model,
                    'error_occurred': True
                }
            }
    
    def _get_model_service(self, model_id: str):
        """
        Get service instance for model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Service instance
            
        Raises:
            ModelNotAvailableError: If model not available
        """
        if model_id not in self._services:
            raise ModelNotAvailableError(f"Model {model_id} not available")
        
        return self._services[model_id]
    
    def _is_model_available(self, model_id: str) -> bool:
        """
        Check if model is available.
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if model is available and enabled
        """
        if model_id not in self._services:
            return False
        
        models_config = getattr(settings, 'COMMAND_PROCESSING_MODELS', {})
        model_config = models_config.get(model_id, {})
        
        return model_config.get('enabled', True)
    
    def _get_default_model(self) -> str:
        """
        Get default model from configuration.
        
        Returns:
            Default model identifier
        """
        default = getattr(settings, 'DEFAULT_COMMAND_MODEL', 'nova-pro')
        
        if self._is_model_available(default):
            return default
        
        for model_id in self._services.keys():
            if self._is_model_available(model_id):
                self.logger.info(f"Default model {default} unavailable, using {model_id}")
                return model_id
        
        self.logger.error("No available models found")
        return 'nova-pro'
    
    def _get_fallback_model(self, current_model: str) -> Optional[str]:
        """
        Get fallback model if current model fails.
        
        Args:
            current_model: Current model identifier
            
        Returns:
            Fallback model identifier or None
        """
        fallback_order = getattr(settings, 'MODEL_FALLBACK_ORDER', ['nova-pro', 'o4-mini'])
        
        for model_id in fallback_order:
            if model_id != current_model and self._is_model_available(model_id):
                return model_id
        
        return None
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models with metadata.
        
        Returns:
            List of dicts with model information
        """
        models_config = getattr(settings, 'COMMAND_PROCESSING_MODELS', {})
        default_model = self._get_default_model()
        
        available_models = []
        
        for model_id, config in models_config.items():
            if config.get('enabled', True) and model_id in self._services:
                available_models.append({
                    'id': model_id,
                    'name': config.get('name', model_id),
                    'description': config.get('description', ''),
                    'provider': config.get('provider', 'unknown'),
                    'avg_response_time': config.get('avg_response_time', 0),
                    'cost_estimate': config.get('cost_estimate', 0.0),
                    'is_default': model_id == default_model,
                    'enabled': True
                })
        
        available_models.sort(key=lambda x: (not x['is_default'], x['avg_response_time']))
        
        return available_models
    
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about specific model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Dict with model information or None if not found
        """
        models = self.get_available_models()
        
        for model in models:
            if model['id'] == model_id:
                return model
        
        return None
    
    def validate_model(self, model_id: str) -> bool:
        """
        Validate that model is available and enabled.
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if model is valid and available
        """
        return self._is_model_available(model_id)
