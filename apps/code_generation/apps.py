"""
This module contains SpringBoot code generation services
It is no longer a Django app but a utility module
"""

def initialize_services():
    """
    Initialize code generation services.
    """

    from .services.template_rendering_service import TemplateRenderingService
    TemplateRenderingService.initialize_template_cache()
