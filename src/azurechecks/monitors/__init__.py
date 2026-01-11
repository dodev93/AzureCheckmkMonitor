"""
Azure Monitor Package for Checkmk Integration

This package provides modules for monitoring Azure resources:
- APIM (API Management) services
- Storage accounts, blobs, and tables
- Service Bus namespaces
- Secrets and certificates
- Container Apps
"""

__version__ = "1.0.0"

# Import main modules for easier access
from . import apim_monitor
from . import storage_account_monitor
from . import storage_blob_monitor
from . import storage_table_monitor
from . import servicebus_monitor
from . import secrets_monitor
from . import container_apps_monitor
from . import aks_monitor
from . import base_monitor

__all__ = [
    'apim_monitor',
    'storage_account_monitor',
    'storage_blob_monitor',
    'storage_table_monitor',
    'servicebus_monitor',
    'secrets_monitor',
    'container_apps_monitor',
    'aks_monitor',
    'base_monitor'
]

