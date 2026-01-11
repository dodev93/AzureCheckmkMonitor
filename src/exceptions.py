#!/usr/bin/env python3
"""
Custom Exceptions for Azure Monitor Modules
"""

from typing import List


class AzureAuthError(Exception):
    """Custom exception for Azure authentication errors"""
    pass


class UnsupportedMetricTypeError(Exception):
    """Raised when a metric type is not supported by the monitoring module."""
    
    def __init__(self, metric_name: str, metric_type: str, supported_types: List[str]):
        self.metric_name = metric_name
        self.metric_type = metric_type
        self.supported_types = supported_types
        message = (
            f"Unsupported metric type '{metric_type}' for metric '{metric_name}'. "
            f"Supported types: {', '.join(supported_types)}"
        )
        super().__init__(message)

