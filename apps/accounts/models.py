# This file is deprecated. Models have been moved to individual files.
# Import models from the new structure for backward compatibility.

from .models.enterprise_user import EnterpriseUser
from .models.authorized_domain import AuthorizedDomain
from .models.password_history import PasswordHistory

__all__ = [
    'EnterpriseUser',
    'AuthorizedDomain',
    'PasswordHistory',
]
