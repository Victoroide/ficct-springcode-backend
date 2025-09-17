"""
Authentication ViewSets Package
"""

from .authentication_viewset import AuthenticationViewSet
from .registration_viewset import RegistrationViewSet

# Import from main viewsets.py file
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from ..viewsets import UserProfileViewSet, SecurityViewSet
    _main_viewsets_available = True
except ImportError:
    _main_viewsets_available = False
    UserProfileViewSet = None
    SecurityViewSet = None

__all__ = [
    'AuthenticationViewSet',
    'RegistrationViewSet',
]

if _main_viewsets_available:
    __all__.extend(['UserProfileViewSet', 'SecurityViewSet'])
