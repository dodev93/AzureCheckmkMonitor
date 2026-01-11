#!/usr/bin/env python3
"""
Configuration Generators for Tests

Provides helper functions to generate test configurations for each resource type.
"""

from typing import Dict, Any, List, Optional


def generate_apim_config(
    api_ids: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate APIM test configuration.
    
    Args:
        api_ids: List of API IDs to monitor (empty list = all APIs)
        metrics: Dict of metric configurations
        **kwargs: Additional config overrides
    
    Returns:
        Complete APIM configuration dict
    """
    default_metrics = {
        'request_count': {
            'enabled': True,
            'time_range': 'PT1H',
            'aggregation': 'sum',
            'granularity': 'PT5M',
            'api_ids': api_ids or [],
            'warn_threshold': None,
            'crit_threshold': None
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    config = {
        'resource_type': 'apim',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'apim-name',
        'location': 'westeurope',
        'time_range': 'PT1H',
        'aggregation': 'sum',
        'granularity': 'PT5M',
        'service_name': 'APIM - Test',
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config


def generate_storage_account_config(
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate Storage Account test configuration."""
    default_metrics = {
        'capacity': {
            'enabled': True,
            'scope': 'account',
            'time_range': 'PT1H',
            'aggregation': 'average'
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    config = {
        'resource_type': 'storage_account',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'storageaccount',
        'location': 'westeurope',
        'time_range': 'PT1H',
        'aggregation': 'average',
        'service_name': 'Storage Account - Test',
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config


def generate_storage_blob_config(
    container_name: str = 'mycontainer',
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate Storage Blob test configuration."""
    default_metrics = {
        'file_existence': {
            'enabled': True,
            'files': ['file1.txt', 'file2.txt'],
            'missing_status': 'CRIT'
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    config = {
        'resource_type': 'storage_blob',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'storageaccount',
        'container_name': container_name,
        'location': 'westeurope',
        'service_name': 'Storage Blob - Test',
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config


def generate_storage_table_config(
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate Storage Table test configuration."""
    default_metrics = {
        'table_existence': {
            'enabled': True,
            'list_all': True
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    config = {
        'resource_type': 'storage_table',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'storageaccount',
        'location': 'westeurope',
        'service_name': 'Storage Table - Test',
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config


def generate_servicebus_config(
    filter_metadata_values: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate Service Bus test configuration.
    
    Args:
        filter_metadata_values: List of queue names to filter by (None = all queues)
        metrics: Dict of metric configurations
        **kwargs: Additional config overrides
    """
    if metrics:
        # Use provided metrics directly (replace defaults)
        default_metrics = metrics
    else:
        # Use default metrics if none provided
        default_metrics = {
            'incoming_requests': {
                'enabled': True,
                'type': 'incoming_requests',
                'time_range': 'PT1H',
                'aggregation': 'sum'
            }
        }
    
    config = {
        'resource_type': 'servicebus',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'servicebus-namespace',
        'location': 'westeurope',
        'time_range': 'PT1H',
        'aggregation': 'sum',
        'group_by_metadata': 'EntityName',
        'service_name': 'Service Bus - Test',
        'metrics': default_metrics
    }
    
    # Only add filter_metadata_values if provided
    if filter_metadata_values is not None:
        config['filter_metadata_values'] = filter_metadata_values
    
    config.update(kwargs)
    return config


def generate_secrets_config(
    app_registration_ids: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate Secrets test configuration."""
    default_metrics = {
        'secret_expiration': {
            'enabled': True,
            'type': 'secrets',
            'expiration_threshold': 30
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    # Convert app_registration_ids to app_registrations format
    app_registrations = []
    if app_registration_ids:
        app_registrations = [
            {'app_id': app_id, 'app_name': None}
            for app_id in app_registration_ids
        ]
    
    config = {
        'resource_type': 'secrets',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'app-registration',
        'location': 'westeurope',
        'service_name': 'Secrets - Test',
        'app_registrations': app_registrations,
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config


def generate_container_apps_config(
    metrics: Optional[Dict[str, Dict]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate Container Apps test configuration."""
    default_metrics = {
        'restarts': {
            'enabled': True,
            'time_range': 'PT1H',
            'aggregation': 'sum'
        }
    }
    
    if metrics:
        default_metrics.update(metrics)
    
    config = {
        'resource_type': 'container_apps',
        'subscription_id': 'sub-id',
        'resource_group': 'rg',
        'resource_name': 'container-app',
        'location': 'westeurope',
        'time_range': 'PT1H',
        'aggregation': 'sum',
        'service_name': 'Container Apps - Test',
        'metrics': default_metrics
    }
    
    config.update(kwargs)
    return config

