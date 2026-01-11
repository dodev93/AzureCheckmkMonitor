#!/usr/bin/env python3
"""
Unit tests for Storage Account monitor module.

Tests match PRD section 3.2 requirements.
"""

import pytest
import sys
from datetime import timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.storage_account_monitor import StorageAccountMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_storage_account_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message,
    assert_problems_with_metadata
)


class TestCapacityMonitoring:
    """Test capacity monitoring per PRD section 3.2.1."""
    
    def test_monitor_capacity_account_scope(self):
        """Test capacity at account scope (aggregated across all services)."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 214748364800,  # 200 GB
                    'crit_threshold': 429496729600   # 400 GB
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(107374182400, {})):  # 100 GB
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            assert result.metrics[0].name == 'capacity'
            assert result.metrics[0].value == 107374182400
            assert result.status == "P"  # P when thresholds are present
            assert_ok_message(result)
    
    def test_monitor_capacity_blob_scope(self):
        """Test capacity at Blob scope."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'Blob',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 107374182400,
                    'crit_threshold': 214748364800
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(53687091200, {})) as mock_query:  # 50 GB
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 53687091200
            # Verify namespace was constructed correctly
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs['scope'] == 'Blob'
    
    def test_monitor_capacity_table_scope(self):
        """Test capacity at Table scope."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'Table',
                    'time_range': 'PT1H',
                    'aggregation': 'average'
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(10737418240, {})):  # 10 GB
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 10737418240
    
    def test_monitor_capacity_with_thresholds(self):
        """Test capacity with thresholds (WARN, CRIT)."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 214748364800,  # 200 GB
                    'crit_threshold': 429496729600   # 400 GB
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        # Test WARN
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(268435456000, {})):  # 250 GB
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 268435456000
            # Status should be "P" when thresholds are present
            assert result.status == "P"
        
        # Test CRIT
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(536870912000, {})):  # 500 GB
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 536870912000
            assert result.status == "P"
    
    def test_monitor_capacity_with_metadata_grouping(self):
        """Test capacity with metadata grouping (OperationName, Tier)."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'group_by_metadata': 'OperationName',
                    'warn_threshold': 100000000,
                    'crit_threshold': 200000000
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        breakdown_dict = {'PutBlob': 150000000, 'GetBlob': 200000000}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350000000, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 2
            problem_names = [p.problem_name for p in result.problems]
            assert 'PutBlob' in problem_names
            assert 'GetBlob' in problem_names
            assert 'OperationName:' in result.message


class TestTransactionMonitoring:
    """Test transaction monitoring per PRD section 3.2.2."""
    
    def test_monitor_transactions_account_scope(self):
        """Test transactions at account scope."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 1000,
                    'crit_threshold': 5000
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(500, {})):
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            assert result.metrics[0].name == 'transactions'
            assert result.metrics[0].value == 500
            assert result.status == "P"  # P when thresholds are present
            assert_ok_message(result)
    
    def test_monitor_transactions_table_scope(self):
        """Test transactions at Table scope."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'Table',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 500,
                    'crit_threshold': 1000
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(200, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 200
            assert result.status == "P"  # P when thresholds are present
    
    def test_monitor_transactions_with_metadata_grouping(self):
        """Test transactions with metadata grouping (OperationName, ApiName)."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'group_by_metadata': 'OperationName',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        breakdown_dict = {'PutBlob': 150, 'GetBlob': 200}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 2
            assert 'OperationName:' in result.message
    
    def test_monitor_transactions_granularity_capping(self):
        """Test granularity capping (1 day for Transactions metric)."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT2D',  # 2 days
                    'aggregation': 'sum'
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(1000, {})) as mock_query:
            monitor.monitor(config)
            
            # Granularity should be capped at 1 day
            call_kwargs = mock_query.call_args[1]
            granularity = call_kwargs['granularity']
            assert granularity <= timedelta(days=1)


class TestMetadataGroupingAndFiltering:
    """Test metadata grouping and filtering per PRD section 3.2.3."""
    
    def test_group_by_operationname(self):
        """Test group by OperationName (e.g., 'PutBlob', 'GetBlob')."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'group_by_metadata': 'OperationName',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        breakdown_dict = {'PutBlob': 150, 'GetBlob': 200}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 2
            assert 'OperationName:' in result.message
            assert 'PutBlob' in result.message
            assert 'GetBlob' in result.message
    
    def test_group_by_tier(self):
        """Test group by Tier (e.g., 'Hot', 'Cool', 'Archive')."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'group_by_metadata': 'Tier',
                    'warn_threshold': 100000000,
                    'crit_threshold': 200000000
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        breakdown_dict = {'Hot': 150000000, 'Cool': 200000000}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350000000, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert 'Tier:' in result.message or 'Hot' in result.message
    
    def test_filter_by_metadata_values(self):
        """Test filter by metadata values."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'filter_metadata_values': ['PutBlob', 'GetBlob'],
                    'group_by_metadata': 'OperationName'
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350, {})) as mock_query:
            monitor.monitor(config)
            
            # Verify filter string construction
            call_kwargs = mock_query.call_args[1]
            filter_str = call_kwargs.get('filter_str', '')
            assert "OperationName eq 'PutBlob'" in filter_str or "OperationName eq 'GetBlob'" in filter_str
    
    def test_multiple_problematic_metadata_values(self):
        """Test multiple problematic metadata values."""
        config = generate_storage_account_config(
            metrics={
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'group_by_metadata': 'OperationName',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        breakdown_dict = {'PutBlob': 150, 'GetBlob': 200, 'DeleteBlob': 300}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(650, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 3
            # Values should be sorted alphabetically in message
            message = result.message
            # Check that all problematic operations are in message
            assert 'PutBlob' in message
            assert 'GetBlob' in message
            assert 'DeleteBlob' in message


class TestMultipleMetrics:
    """Test monitoring multiple metrics."""
    
    def test_multiple_metrics(self):
        """Test monitoring multiple metrics in single service line."""
        config = generate_storage_account_config(
            metrics={
                'capacity': {
                    'enabled': True,
                    'type': 'capacity',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'average'
                },
                'transactions': {
                    'enabled': True,
                    'type': 'transactions',
                    'scope': 'account',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                }
            }
        )
        
        monitor = StorageAccountMonitor(config)
        
        call_count = {'count': 0}
        def mock_query_side_effect(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return (107374182400, {})  # capacity
            else:
                return (500, {})  # transactions
        
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=mock_query_side_effect):
            result = monitor.monitor(config)
            
            assert len(result.metrics) == 2
            assert result.metrics[0].name == 'capacity'
            assert result.metrics[1].name == 'transactions'
            assert_ok_message(result)
