#!/usr/bin/env python3
"""
Unit tests for Storage Blob monitor module.

Tests match PRD section 3.3 requirements.
"""

import pytest
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.storage_blob_monitor import StorageBlobMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_storage_blob_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message
)


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

@pytest.fixture
def mock_blob_service_hierarchy():
    """
    Create a mock blob service client hierarchy.
    
    Returns:
        Tuple of (mock_blob_service, mock_container_client)
    """
    mock_blob_service = MagicMock()
    mock_container_client = MagicMock()
    mock_blob_service.get_container_client.return_value = mock_container_client
    return mock_blob_service, mock_container_client


def create_blob_client_mock(exists=True, last_modified_hours_ago=None):
    """
    Create a mock blob client with specified behavior.
    
    Args:
        exists: Whether the blob exists
        last_modified_hours_ago: Hours ago the blob was modified (None = don't set)
    
    Returns:
        Mock blob client
    """
    mock_blob = MagicMock()
    mock_blob.exists.return_value = exists
    
    if last_modified_hours_ago is not None:
        mock_properties = MagicMock()
        modified_time = datetime.now(timezone.utc) - timedelta(hours=last_modified_hours_ago)
        mock_properties.last_modified = modified_time
        mock_blob.get_blob_properties.return_value = mock_properties
    
    return mock_blob


def setup_blob_clients(mock_container_client, file_configs):
    """
    Setup blob clients for multiple files.
    
    Args:
        mock_container_client: Mock container client
        file_configs: List of dicts with 'exists' and optionally 'hours_ago' keys
    
    Returns:
        List of created blob client mocks
    """
    blob_clients = []
    for config in file_configs:
        exists = config.get('exists', True)
        hours_ago = config.get('hours_ago')
        blob_client = create_blob_client_mock(exists=exists, last_modified_hours_ago=hours_ago)
        blob_clients.append(blob_client)
    
    mock_container_client.get_blob_client.side_effect = blob_clients
    return blob_clients


class TestFileExistenceChecks:
    """Test file existence checks per PRD section 3.3.1."""
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_existence_all_exist(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file existence when all files exist."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_existence': {
                    'enabled': True,
                    'type': 'file_existence',
                    'files': ['file1.txt', 'file2.csv'],
                    'missing_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': True}, {'exists': True}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)
        
        assert isinstance(result, MetricResult)
        assert result.status == "P"  # P when thresholds are present (crit_threshold=1 is set implicitly)
        assert_ok_message(result)
        assert len(result.metrics) == 1
        assert result.metrics[0].value == 0.0
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_existence_some_missing(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file existence when some files are missing."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_existence': {
                    'enabled': True,
                    'type': 'file_existence',
                    'files': ['file1.txt', 'file2.txt', 'file3.txt'],
                    'missing_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [
            {'exists': True},   # file1.txt
            {'exists': False},  # file2.txt is missing
            {'exists': True}    # file3.txt
        ])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)
        
        assert result.status == "P"  # P when thresholds are present (crit_threshold=1 is set implicitly)
        assert result.metrics[0].value == 1.0
        assert result.problems is not None
        assert len(result.problems) == 1
        assert 'file2.txt' in result.message
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_existence_missing_warn(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file existence with WARN status for missing files."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_existence': {
                    'enabled': True,
                    'type': 'file_existence',
                    'files': ['missing.txt'],
                    'missing_status': 'WARN'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': False}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)

        assert result.status == "P"  # P when thresholds are present (warn_threshold is set based on exceeded_status)
        assert 'missing.txt' in result.message
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_existence_no_container(self, mock_get_blob_client):
        """Test file existence fails without container_name."""
        config = generate_storage_blob_config(
            container_name=None,
            metrics={
                'file_existence': {
                    'enabled': True,
                    'type': 'file_existence',
                    'files': ['file1.txt'],
                    'missing_status': 'CRIT'
                }
            }
        )
        
        monitor = StorageBlobMonitor(config)
        
        with pytest.raises(ValueError, match="container_name"):
            monitor.monitor(config)


class TestFileModificationDateChecks:
    """Test file modification date checks per PRD section 3.3.2."""
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_modification_ok(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file modification when file is recent."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['backup.zip'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': True, 'hours_ago': 12}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)
        
        assert isinstance(result, MetricResult)
        assert result.status == "P"  # P when thresholds are present (crit_threshold is set based on exceeded_status)
        assert_ok_message(result)
        assert len(result.metrics) == 1
        assert result.metrics[0].value <= 12.1
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_modification_exceeded_crit(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file modification when threshold is exceeded (CRIT)."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['data.csv'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': True, 'hours_ago': 48}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)
        
        assert result.status == "P"  # P when thresholds are present (crit_threshold is set)
        assert result.metrics[0].value >= 47.0
        assert 'CRIT' in result.message or result.problems is not None
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_modification_exceeded_warn(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file modification with WARN status."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['log.txt'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'WARN'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': True, 'hours_ago': 30}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)

        assert result.status == "P"  # P when thresholds are present (warn_threshold is set based on exceeded_status)
        assert 'WARN' in result.message or result.problems is not None
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_modification_file_not_found(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file modification when file doesn't exist."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['missing.txt'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [{'exists': False}])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)

        assert result.status == "P"  # P when thresholds are present (crit_threshold is set based on exceeded_status)
        assert 'not found' in result.message.lower() or result.problems is not None
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_file_modification_multiple_files(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test file modification with multiple files."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['recent.txt', 'old.txt'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'WARN'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        setup_blob_clients(mock_container_client, [
            {'exists': True, 'hours_ago': 6},   # Recent
            {'exists': True, 'hours_ago': 48}   # Old
        ])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)

        assert result.status == "P"  # P when thresholds are present (warn_threshold is set based on exceeded_status)
        assert result.metrics[0].value >= 47.0


class TestMultipleMetrics:
    """Test monitoring multiple metrics."""
    
    @patch('azurechecks.monitors.storage_blob_monitor.get_blob_service_client')
    def test_multiple_metrics(self, mock_get_blob_client, mock_blob_service_hierarchy):
        """Test monitoring multiple metrics."""
        config = generate_storage_blob_config(
            container_name='mycontainer',
            metrics={
                'file_existence': {
                    'enabled': True,
                    'type': 'file_existence',
                    'files': ['test.txt'],
                    'missing_status': 'CRIT'
                },
                'file_modification': {
                    'enabled': True,
                    'type': 'file_modification',
                    'files': ['backup.zip'],
                    'max_hours_since_modification': 24,
                    'exceeded_status': 'CRIT'
                }
            }
        )
        
        mock_blob_service, mock_container_client = mock_blob_service_hierarchy
        mock_get_blob_client.return_value = mock_blob_service
        # File existence: file exists, File modification: file exists and is recent
        setup_blob_clients(mock_container_client, [
            {'exists': True},              # file_existence
            {'exists': True, 'hours_ago': 12}  # file_modification
        ])
        
        monitor = StorageBlobMonitor(config)
        result = monitor.monitor(config)
        
        assert len(result.metrics) == 2
        assert result.metrics[0].name == 'file_existence'
        assert result.metrics[1].name == 'file_modification'
        assert_ok_message(result)
