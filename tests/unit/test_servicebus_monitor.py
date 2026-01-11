#!/usr/bin/env python3
"""
Unit tests for Service Bus monitor module.

Tests match PRD section 3.5 requirements.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.servicebus_monitor import ServiceBusMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_servicebus_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message
)


class TestQueueMonitoring:
    """Test queue monitoring per PRD section 3.5.1."""
    
    def test_monitor_all_queues(self):
        """Test monitor all queues (no filter_metadata_values in configuration)."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'incoming_requests': {
                    'enabled': True,
                    'type': 'incoming_requests',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(100.0, {})):
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            assert result.metrics[0].name == 'incoming_requests'
            assert result.metrics[0].value == 100.0
            assert_ok_message(result)
    
    def test_monitor_specific_queues(self):
        """Test monitor specific queues (filter_metadata_values list)."""
        config = generate_servicebus_config(
            filter_metadata_values=['queue1', 'queue2'],
            metrics={
                'incoming_requests': {
                    'enabled': True,
                    'type': 'incoming_requests',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(150.0, {})) as mock_query:
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 150.0
            # Verify filter was constructed
            call_kwargs = mock_query.call_args[1]
            filter_str = call_kwargs.get('filter_str', '')
            assert 'queue1' in filter_str or 'queue2' in filter_str
    
    def test_monitor_incoming_requests(self):
        """Test incoming requests per queue."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'incoming_requests': {
                    'enabled': True,
                    'type': 'incoming_requests',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(200.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'incoming_requests'
            assert result.metrics[0].value == 200.0
    
    def test_monitor_server_errors(self):
        """Test server errors per queue."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'server_errors': {
                    'enabled': True,
                    'type': 'server_errors',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 10,
                    'crit_threshold': 50
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(25.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'server_errors'
            assert result.metrics[0].value == 25.0
    
    def test_monitor_deadletter_messages(self):
        """Test deadletter messages per queue."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'deadletter_messages': {
                    'enabled': True,
                    'type': 'deadletter_messages',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 5,
                    'crit_threshold': 20
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(10.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'deadletter_messages'
            assert result.metrics[0].value == 10.0
    
    def test_monitor_active_messages(self):
        """Test active messages per queue."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'active_messages': {
                    'enabled': True,
                    'type': 'active_messages',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(250.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'active_messages'
            assert result.metrics[0].value == 250.0
    
    def test_problematic_queue_identification(self):
        """Test problematic queue identification."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'incoming_requests': {
                    'enabled': True,
                    'type': 'incoming_requests',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'EntityName'
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        breakdown_dict = {'queue1': 150.0, 'queue2': 600.0}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(750.0, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) >= 1
            problem_names = [p.problem_name for p in result.problems]
            assert 'queue1' in problem_names or 'queue2' in problem_names
            assert 'EntityName:' in result.message


class TestMultipleMetrics:
    """Test monitoring multiple metrics."""
    
    def test_multiple_metrics(self):
        """Test all four metrics in single service line."""
        config = generate_servicebus_config(
            filter_metadata_values=None,
            metrics={
                'incoming_requests': {
                    'enabled': True,
                    'type': 'incoming_requests',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                },
                'server_errors': {
                    'enabled': True,
                    'type': 'server_errors',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                },
                'deadletter_messages': {
                    'enabled': True,
                    'type': 'deadletter_messages',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                },
                'active_messages': {
                    'enabled': True,
                    'type': 'active_messages',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                }
            }
        )
        
        monitor = ServiceBusMonitor(config)
        
        call_count = {'count': 0}
        def mock_query_side_effect(*args, **kwargs):
            call_count['count'] += 1
            return (100.0, {})
        
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=mock_query_side_effect):
            result = monitor.monitor(config)
            
            assert len(result.metrics) == 4
            metric_names = [m.name for m in result.metrics]
            assert 'incoming_requests' in metric_names
            assert 'server_errors' in metric_names
            assert 'deadletter_messages' in metric_names
            assert 'active_messages' in metric_names

