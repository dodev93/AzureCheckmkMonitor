"""
Azure Package

Provides Azure-specific functionality including authentication and monitoring.
"""

from . import azure_auth
from . import generic_check

__all__ = [
    'azure_auth',
    'generic_check',
]

