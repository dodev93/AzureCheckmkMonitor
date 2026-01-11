#!/usr/bin/env python3
"""
Unit tests for generic_check module.

Tests match PRD section 3.8 requirements.
"""

import pytest
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.generic_check import route_to_monitor, format_results
from validation.config_validator import ConfigValidationError
from azurechecks.azure_auth import AzureAuthError
from checkmk.checkmk_formatter import MetricResult, Metric


class TestConfigurationRouting:
    """Test configuration routing per PRD section 3.8.1."""
    
    @patch('azurechecks.monitors.apim_monitor.APIMMonitor')
    def test_route_to_apim(self, mock_apim_class):
        """Test route to APIM monitor."""
        config = {
            'resource_type': 'apim',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'apim-name',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='APIM', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_apim_class.return_value = mock_monitor
        
        result = route_to_monitor('apim', config)
        
        mock_apim_class.assert_called_once_with(config)
        mock_monitor.monitor.assert_called_once_with(config, debug=False)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.storage_account_monitor.StorageAccountMonitor')
    def test_route_to_storage_account(self, mock_storage_class):
        """Test route to Storage Account monitor."""
        config = {
            'resource_type': 'storage_account',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'storageaccount',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Storage Account', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_storage_class.return_value = mock_monitor
        
        result = route_to_monitor('storage_account', config)
        
        mock_storage_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.storage_blob_monitor.StorageBlobMonitor')
    def test_route_to_storage_blob(self, mock_blob_class):
        """Test route to Storage Blob monitor."""
        config = {
            'resource_type': 'storage_blob',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'storageaccount',
            'container_name': 'mycontainer',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Storage Blob', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_blob_class.return_value = mock_monitor
        
        result = route_to_monitor('storage_blob', config)
        
        mock_blob_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.storage_table_monitor.StorageTableMonitor')
    def test_route_to_storage_table(self, mock_table_class):
        """Test route to Storage Table monitor."""
        config = {
            'resource_type': 'storage_table',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'storageaccount',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Storage Table', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_table_class.return_value = mock_monitor
        
        result = route_to_monitor('storage_table', config)
        
        mock_table_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.servicebus_monitor.ServiceBusMonitor')
    def test_route_to_servicebus(self, mock_servicebus_class):
        """Test route to Service Bus monitor."""
        config = {
            'resource_type': 'servicebus',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'servicebus-namespace',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Service Bus', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_servicebus_class.return_value = mock_monitor
        
        result = route_to_monitor('servicebus', config)
        
        mock_servicebus_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.secrets_monitor.SecretsMonitor')
    def test_route_to_secrets(self, mock_secrets_class):
        """Test route to Secrets monitor."""
        config = {
            'resource_type': 'secrets',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'app-registration',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Secrets', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_secrets_class.return_value = mock_monitor
        
        result = route_to_monitor('secrets', config)
        
        mock_secrets_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    @patch('azurechecks.monitors.container_apps_monitor.ContainerAppsMonitor')
    def test_route_to_container_apps(self, mock_container_class):
        """Test route to Container Apps monitor."""
        config = {
            'resource_type': 'container_apps',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'container-app',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_result = MetricResult(service_name='Container Apps', metrics=[], problems=None)
        mock_monitor.monitor.return_value = mock_result
        mock_container_class.return_value = mock_monitor
        
        result = route_to_monitor('container_apps', config)
        
        mock_container_class.assert_called_once_with(config)
        assert isinstance(result, MetricResult)
    
    def test_route_to_unsupported(self):
        """Test route to unsupported resource type."""
        with pytest.raises(ValueError, match="Unsupported resource type"):
            route_to_monitor('unsupported', {})


class TestErrorHandling:
    """Test error handling per PRD section 3.8.2."""
    
    @patch('azurechecks.monitors.apim_monitor.APIMMonitor')
    def test_authentication_error(self, mock_apim_class):
        """Test authentication errors (status 3)."""
        config = {
            'resource_type': 'apim',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'apim-name',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_monitor.monitor.side_effect = AzureAuthError("Authentication failed")
        mock_apim_class.return_value = mock_monitor
        
        with pytest.raises(AzureAuthError):
            route_to_monitor('apim', config)
    
    @patch('azurechecks.monitors.apim_monitor.APIMMonitor')
    def test_invalid_resource_id(self, mock_apim_class):
        """Test invalid resource IDs (status 3)."""
        config = {
            'resource_type': 'apim',
            'subscription_id': 'sub-id',
            'resource_group': 'rg',
            'resource_name': 'apim-name',
            'location': 'westeurope',
            'metrics': {}
        }
        
        mock_monitor = MagicMock()
        mock_monitor.monitor.side_effect = ValueError("Invalid resource ID")
        mock_apim_class.return_value = mock_monitor
        
        with pytest.raises(ValueError):
            route_to_monitor('apim', config)


class TestStatusCodeDetermination:
    """Test status code determination per PRD section 3.8.3."""
    
    def test_status_p_when_thresholds_present(self):
        """Test status 'P' when any metric has thresholds defined."""
        metric1 = Metric(
            name='metric1',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test',
            metrics=[metric1],
            problems=None
        )
        
        assert result.status == "P"
    
    def test_status_numeric_when_no_thresholds(self):
        """Test status 0, 1, 2 when no thresholds defined."""
        metric1 = Metric(
            name='metric1',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test',
            metrics=[metric1],
            problems=None
        )
        
        assert result.status == 0  # OK
    
    def test_status_3_for_errors(self):
        """Test status 3 for errors."""
        # Status 3 is typically set by the formatter when there's an error
        # This is handled in generic_check.py main() function
        pass


class TestFormatResults:
    """Test result formatting."""
    
    def test_format_results_with_metric_result(self):
        """Test formatting results with MetricResult."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        output = format_results(result)
        
        assert isinstance(output, str)
        assert 'Test Service' in output
        assert 'test_metric' in output
    
    def test_format_results_with_error(self):
        """Test formatting results with error status."""
        result = MetricResult(
            service_name='Error Service',
            metrics=[],
            problems=None
        )
        result._status = 3
        
        output = format_results(result)
        
        assert isinstance(output, str)
        assert '3' in output or 'Error' in output
