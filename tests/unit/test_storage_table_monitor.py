#!/usr/bin/env python3
"""
Unit tests for Storage Table monitor module.

Tests match PRD section 3.4 requirements.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.storage_table_monitor import StorageTableMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_storage_table_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message
)


class TestTableExistenceChecks:
    """Test table existence checks per PRD section 3.4.1."""
    
    @patch('azurechecks.monitors.storage_table_monitor.get_table_service_client')
    def test_table_existence_single_table(self, mock_get_table_client):
        """Test check single table existence."""
        config = generate_storage_table_config(
            metrics={
                'table_existence': {
                    'enabled': True,
                    'type': 'table_existence',
                    'list_all': False,
                    'filtered_tables': ['UserData']
                }
            }
        )
        
        # Setup mocks
        mock_table_service = MagicMock()
        mock_get_table_client.return_value = mock_table_service
        
        # Create mock tables
        table1 = MagicMock()
        table1.name = 'UserData'
        
        mock_table_service.list_tables.return_value = [table1]
        
        monitor = StorageTableMonitor(config)
        result = monitor.monitor(config)
        
        assert isinstance(result, MetricResult)
        assert result.status == "P"  # P when thresholds are present (crit_threshold=1.0 is set implicitly)
        assert_ok_message(result)
        assert len(result.metrics) == 1
        # Value should be 0 (all tables exist)
        assert result.metrics[0].value == 0.0
    
    @patch('azurechecks.monitors.storage_table_monitor.get_table_service_client')
    def test_table_existence_multiple_tables(self, mock_get_table_client):
        """Test check multiple tables existence."""
        config = generate_storage_table_config(
            metrics={
                'table_existence': {
                    'enabled': True,
                    'type': 'table_existence',
                    'list_all': False,
                    'filtered_tables': ['UserData', 'Sessions', 'Logs']
                }
            }
        )
        
        # Setup mocks
        mock_table_service = MagicMock()
        mock_get_table_client.return_value = mock_table_service
        
        # Create mock tables
        table1 = MagicMock()
        table1.name = 'UserData'
        table2 = MagicMock()
        table2.name = 'Sessions'
        table3 = MagicMock()
        table3.name = 'Logs'
        
        mock_table_service.list_tables.return_value = [table1, table2, table3]
        
        monitor = StorageTableMonitor(config)
        result = monitor.monitor(config)
        
        assert result.status == "P"  # P when thresholds are present (crit_threshold=1.0 is set implicitly)
        assert result.metrics[0].value == 0.0  # All tables exist
    
    @patch('azurechecks.monitors.storage_table_monitor.get_table_service_client')
    def test_table_existence_missing_table(self, mock_get_table_client):
        """Test missing table detection."""
        config = generate_storage_table_config(
            metrics={
                'table_existence': {
                    'enabled': True,
                    'type': 'table_existence',
                    'list_all': False,
                    'filtered_tables': ['UserData', 'Sessions', 'Logs']
                }
            }
        )
        
        # Setup mocks
        mock_table_service = MagicMock()
        mock_get_table_client.return_value = mock_table_service
        
        # Only UserData exists, Sessions and Logs are missing
        table1 = MagicMock()
        table1.name = 'UserData'
        
        mock_table_service.list_tables.return_value = [table1]
        
        monitor = StorageTableMonitor(config)
        result = monitor.monitor(config)

        assert result.status == "P"  # P when thresholds are present (crit_threshold=1.0 is set implicitly)
        assert result.metrics[0].value == 2.0  # 2 missing tables
        assert result.problems is not None
        assert len(result.problems) == 2
        # Check that missing tables are in message
        message = result.message.lower()
        assert 'sessions' in message or 'logs' in message
    
    @patch('azurechecks.monitors.storage_table_monitor.get_table_service_client')
    def test_table_existence_list_all(self, mock_get_table_client):
        """Test listing all tables."""
        config = generate_storage_table_config(
            metrics={
                'table_existence': {
                    'enabled': True,
                    'type': 'table_existence',
                    'list_all': True
                }
            }
        )
        
        # Setup mocks
        mock_table_service = MagicMock()
        mock_get_table_client.return_value = mock_table_service
        
        # Create mock tables
        table1 = MagicMock()
        table1.name = 'UserData'
        table2 = MagicMock()
        table2.name = 'Sessions'
        table3 = MagicMock()
        table3.name = 'Logs'
        
        mock_table_service.list_tables.return_value = [table1, table2, table3]
        
        monitor = StorageTableMonitor(config)
        result = monitor.monitor(config)

        assert result.status == 0  # OK - no thresholds when list_all=True
        # When list_all is True, it just counts tables
        assert '3' in result.message or result.metrics[0].value == 3.0
    
    @patch('azurechecks.monitors.storage_table_monitor.get_table_service_client')
    def test_table_existence_no_tables(self, mock_get_table_client):
        """Test when no tables exist."""
        config = generate_storage_table_config(
            metrics={
                'table_existence': {
                    'enabled': True,
                    'type': 'table_existence',
                    'list_all': True
                }
            }
        )
        
        # Setup mocks
        mock_table_service = MagicMock()
        mock_get_table_client.return_value = mock_table_service
        
        mock_table_service.list_tables.return_value = []
        
        monitor = StorageTableMonitor(config)
        result = monitor.monitor(config)

        assert result.status == 0  # OK - no thresholds when list_all=True
        assert '0' in result.message or result.metrics[0].value == 0.0
