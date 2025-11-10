"""Vision Model Router for Image Processing.

Routes UML diagram image processing to appropriate AI model with automatic fallback.
Primary: Llama 4 Maverick (70% cheaper) → Fallback: Nova Pro (reliable)
"""

import logging
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class VisionModelRouterService:
    """
    Routes image processing requests to selected vision model with fallback.
    
    Supported models:
        - llama4-maverick: Llama 4 Maverick 17B (default, 70% cheaper)
        - nova-pro: Amazon Nova Pro (reliable fallback)
    
    Features:
        - Automatic model selection
        - Transparent fallback on error
        - Unified response format
        - Cost tracking per model
    
    Example:
        router = VisionModelRouterService()
        result = router.process_image(
            image_data=base64_image,
            model="llama4-maverick"
        )
    """
    
    def __init__(self):
        """Initialize vision model router with available services."""
        self.logger = logging.getLogger(__name__)
        self._services = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize available vision model services."""
        try:
            from .llama4_vision_service import Llama4VisionService
            self._services['llama4-maverick'] = Llama4VisionService()
            self.logger.info("Llama 4 Maverick vision service initialized")
        except Exception as e:
            self.logger.warning(f"Llama 4 vision service not available: {e}")
        
        try:
            from .nova_vision_service import NovaVisionService
            self._services['nova-pro'] = NovaVisionService()
            self.logger.info("Nova Pro vision service initialized")
        except Exception as e:
            self.logger.warning(f"Nova Pro vision service not available: {e}")
        
        if not self._services:
            self.logger.error("No vision models available for image processing")
    
    def process_image(
        self,
        base64_image: str,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        existing_diagram: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process image with selected model and automatic fallback.
        
        Args:
            base64_image: Base64 encoded image data
            model: Model identifier (llama4-maverick, nova-pro) or None for default
            session_id: Optional session identifier
            existing_diagram: Optional existing diagram for merging
            
        Returns:
            Dict with nodes, edges, metadata, cost_info
        """
        selected_model = model or self._get_default_model()
        
        self.logger.info(f"Processing image with model: {selected_model}")
        
        if not self._is_model_available(selected_model):
            self.logger.warning(f"Model {selected_model} not available, trying fallback")
            selected_model = self._get_fallback_model(selected_model)
            
            if not selected_model:
                return {
                    'nodes': [],
                    'edges': [],
                    'success': False,
                    'message': 'No vision models available',
                    'metadata': {
                        'error_type': 'no_models_available'
                    }
                }
        
        try:
            service = self._get_model_service(selected_model)
            
            result = service.process_uml_diagram(
                base64_image=base64_image,
                session_id=session_id,
                existing_diagram=existing_diagram
            )
            
            if 'metadata' not in result:
                result['metadata'] = {}
            
            result['metadata']['model_used'] = selected_model
            result['metadata']['model_requested'] = model or 'default'
            result['metadata']['fallback_used'] = False
            
            self.logger.info(f"Image processed successfully with {selected_model}: "
                           f"{result['metadata'].get('node_count', 0)} nodes, "
                           f"{result['metadata'].get('edge_count', 0)} edges")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing image with {selected_model}: {e}", exc_info=True)
            
            fallback_model = self._get_fallback_model(selected_model)
            
            if fallback_model and fallback_model != selected_model:
                self.logger.info(f"Attempting fallback to {fallback_model}")
                
                try:
                    fallback_service = self._get_model_service(fallback_model)
                    
                    result = fallback_service.process_uml_diagram(
                        base64_image=base64_image,
                        session_id=session_id,
                        existing_diagram=existing_diagram
                    )
                    
                    if 'metadata' not in result:
                        result['metadata'] = {}
                    
                    result['metadata']['model_used'] = fallback_model
                    result['metadata']['model_requested'] = selected_model
                    result['metadata']['fallback_used'] = True
                    result['metadata']['primary_error'] = str(e)
                    
                    self.logger.info(f"Fallback successful with {fallback_model}")
                    
                    return result
                    
                except Exception as fallback_error:
                    self.logger.error(f"Fallback to {fallback_model} also failed: {fallback_error}")
            
            return {
                'nodes': [],
                'edges': [],
                'success': False,
                'message': f'Image processing failed: {str(e)}',
                'metadata': {
                    'error_type': 'processing_failed',
                    'model_attempted': selected_model,
                    'fallback_attempted': fallback_model if fallback_model else None
                }
            }
    
    def _get_model_service(self, model_id: str):
        """
        Get service instance for model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Service instance
        """
        if model_id not in self._services:
            raise ValueError(f"Model {model_id} not available")
        
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
        
        models_config = getattr(settings, 'VISION_PROCESSING_MODELS', {})
        model_config = models_config.get(model_id, {})
        
        return model_config.get('enabled', True)
    
    def _get_default_model(self) -> str:
        """
        Get default vision model from configuration.
        
        Returns:
            Default model identifier
        """
        default = getattr(settings, 'DEFAULT_VISION_MODEL', 'llama4-maverick')
        
        if self._is_model_available(default):
            return default
        
        for model_id in self._services.keys():
            if self._is_model_available(model_id):
                self.logger.info(f"Default model {default} unavailable, using {model_id}")
                return model_id
        
        self.logger.error("No available vision models found")
        return 'llama4-maverick'
    
    def _get_fallback_model(self, current_model: str) -> Optional[str]:
        """
        Get fallback model if current model fails.
        
        Args:
            current_model: Current model identifier
            
        Returns:
            Fallback model identifier or None
        """
        fallback_order = getattr(settings, 'VISION_FALLBACK_ORDER', ['llama4-maverick', 'nova-pro'])
        
        for model_id in fallback_order:
            if model_id != current_model and self._is_model_available(model_id):
                return model_id
        
        return None
    
    def get_available_models(self) -> Dict[str, Any]:
        """
        Get list of available vision models with details.
        
        Returns:
            Dict with available models and configuration
        """
        models_config = getattr(settings, 'VISION_PROCESSING_MODELS', {})
        default_model = self._get_default_model()
        
        available = []
        
        for model_id, service in self._services.items():
            config = models_config.get(model_id, {})
            
            available.append({
                'id': model_id,
                'name': config.get('name', model_id),
                'provider': config.get('provider', 'unknown'),
                'enabled': config.get('enabled', True),
                'cost_estimate': config.get('cost_estimate', 0.0),
                'avg_response_time': config.get('avg_response_time', 0),
                'description': config.get('description', ''),
                'is_default': model_id == default_model,
                'available': True
            })
        
        return {
            'models': available,
            'default_model': default_model,
            'fallback_enabled': True
        }
