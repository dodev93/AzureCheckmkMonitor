#!/usr/bin/env python3
"""
Integration tests for APIM monitoring.

These tests require real Azure credentials and resources.
They are optional and should be run manually with proper setup.
Tests match PRD section 2.2 requirements.
"""

import pytest
import os
import sys
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.apim_monitor import APIMMonitor
from checkmk.checkmk_formatter import MetricResult
from validation.config_validator import ConfigValidator
from azurechecks.generic_check import route_to_monitor

# Skip all tests if credentials are not available
pytestmark = pytest.mark.skipif(
    not all([
        os.getenv('AZURE_CLIENT_ID'),
        os.getenv('AZURE_CLIENT_SECRET'),
        os.getenv('AZURE_TENANT_ID'),
        os.getenv('AZURE_SUBSCRIPTION_ID')
    ]),
    reason="Azure credentials not available"
)


class TestAPIMIntegration:
    """Integration tests for APIM monitoring."""
    
    @pytest.fixture
    def sample_config(self):
        """Sample APIM configuration for testing."""
        return {
            'resource_type': 'apim',
            'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID', ''),
            'resource_group': os.getenv('AZURE_RESOURCE_GROUP', ''),
            'resource_name': os.getenv('AZURE_APIM_NAME', ''),
            'location': os.getenv('AZURE_LOCATION', 'westeurope'),
            'time_range': 'PT24H',
            'aggregation': 'sum',
            'service_name': 'Azure APIM - Test',
            'metrics': {
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'api_ids': [],
                    'warn_threshold': None,
                    'crit_threshold': None
                }
            }
        }
    
    def test_monitor_request_count_real(self, sample_config):
        """Test monitoring request count with real Azure resource."""
        if not sample_config.get('subscription_id') or not sample_config.get('resource_group') or not sample_config.get('resource_name'):
            pytest.skip("Azure resource identifiers not set")
        
        monitor = APIMMonitor(sample_config)
        result = monitor.monitor(sample_config)
        
        assert isinstance(result, MetricResult)
        assert len(result.metrics) > 0
        assert result.metrics[0].name == 'request_count'
        assert isinstance(result.metrics[0].value, (int, float))
        assert result.metrics[0].value >= 0
    
    def test_monitor_requests_2xx_real(self, sample_config):
        """Test monitoring 2xx requests with real Azure resource."""
        if not sample_config.get('subscription_id') or not sample_config.get('resource_group') or not sample_config.get('resource_name'):
            pytest.skip("Azure resource identifiers not set")
        
        sample_config['metrics'] = {
            'requests_2xx': {
                'enabled': True,
                'type': 'requests_2xx',
                'api_ids': [],
                'warn_threshold': None,
                'crit_threshold': None
            }
        }
        
        monitor = APIMMonitor(sample_config)
        result = monitor.monitor(sample_config)
        
        assert isinstance(result, MetricResult)
        assert len(result.metrics) > 0
        assert result.metrics[0].name == 'requests_2xx'
        assert isinstance(result.metrics[0].value, (int, float))
        assert result.metrics[0].value >= 0
    
    def test_monitor_apim_end_to_end(self, sample_config):
        """Test end-to-end APIM monitoring."""
        if not sample_config.get('subscription_id') or not sample_config.get('resource_group') or not sample_config.get('resource_name'):
            pytest.skip("Azure resource identifiers not set")
        
        result = route_to_monitor('apim', sample_config)
        
        assert isinstance(result, MetricResult)
        assert len(result.metrics) > 0
        for metric in result.metrics:
            assert hasattr(metric, 'name')
            assert hasattr(metric, 'value')
    
    def test_format_results_real(self, sample_config):
        """Test formatting results with real data."""
        if not sample_config.get('subscription_id') or not sample_config.get('resource_group') or not sample_config.get('resource_name'):
            pytest.skip("Azure resource identifiers not set")
        
        from azurechecks.generic_check import format_results
        
        result = route_to_monitor('apim', sample_config)
        output = format_results(result)
        
        assert isinstance(output, str)
        assert len(output) > 0
        # Check for Checkmk format
        lines = output.split('\n')
        for line in lines:
            if line.strip():  # Skip empty lines
                # Should start with status code
                assert line[0] in ['0', '1', '2', '3', 'P']
                # Should contain quoted service name
                assert '"' in line


class TestGenericCheckIntegration:
    """Integration tests for generic check script."""
    
    @pytest.fixture
    def sample_config_file(self, tmp_path):
        """Create a sample configuration file."""
        config = {
            'resource_type': 'apim',
            'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID', ''),
            'resource_group': os.getenv('AZURE_RESOURCE_GROUP', ''),
            'resource_name': os.getenv('AZURE_APIM_NAME', ''),
            'location': os.getenv('AZURE_LOCATION', 'westeurope'),
            'time_range': 'PT1H',
            'aggregation': 'sum',
            'service_name': 'Azure APIM - Test',
            'metrics': {
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'api_ids': []
                }
            }
        }
        
        config_file = tmp_path / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        return str(config_file)
    
    def test_route_to_monitor_real(self, sample_config_file):
        """Test routing to monitor with real configuration."""
        config = ConfigValidator.load_config(sample_config_file)
        
        if not config.get('subscription_id') or not config.get('resource_group') or not config.get('resource_name'):
            pytest.skip("Azure resource identifiers not set")
        
        result = route_to_monitor(config['resource_type'], config)
        
        assert isinstance(result, MetricResult)
        # Results may be empty if no metrics are enabled or if there's no data
        # but the function should not raise an exception
