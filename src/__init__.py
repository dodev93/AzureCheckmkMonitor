"""
Azure Monitor Package for Checkmk Integration

This is the root package for Azure monitoring functionality.
"""

__version__ = "1.0.0"

# Expose top-level utilities
from . import exceptions
from . import utils

__all__ = [
    'exceptions',
    'utils',
]

