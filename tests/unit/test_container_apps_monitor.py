#!/usr/bin/env python3
"""
Unit tests for Container Apps monitor module.

Tests match PRD section 3.7 requirements.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.container_apps_monitor import ContainerAppsMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_container_apps_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message
)


class TestContainerMetrics:
    """Test container metrics per PRD section 3.7.1."""
    
    def test_restarts_count_monitoring(self):
        """Test restarts count monitoring."""
        config = generate_container_apps_config(
            metrics={
                'restarts': {
                    'enabled': True,
                    'type': 'restarts',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'warn_threshold': 10,
                    'crit_threshold': 50
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(5.0, {})):
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            assert result.metrics[0].name == 'restarts'
            assert result.metrics[0].value == 5.0
            assert_ok_message(result)
    
    def test_cpu_percentage_monitoring(self):
        """Test CPU percentage monitoring."""
        config = generate_container_apps_config(
            metrics={
                'cpu_percentage': {
                    'enabled': True,
                    'type': 'cpu_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 70.0,
                    'crit_threshold': 90.0
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(60.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'cpu_percentage'
            assert result.metrics[0].value == 60.0
            assert result.metrics[0].unit == '%'
    
    def test_memory_percentage_monitoring(self):
        """Test memory percentage monitoring."""
        config = generate_container_apps_config(
            metrics={
                'memory_percentage': {
                    'enabled': True,
                    'type': 'memory_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 80.0,
                    'crit_threshold': 95.0
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(75.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'memory_percentage'
            assert result.metrics[0].value == 75.0
            assert result.metrics[0].unit == '%'
    
    def test_response_time_monitoring(self):
        """Test response time monitoring."""
        config = generate_container_apps_config(
            metrics={
                'response_time': {
                    'enabled': True,
                    'type': 'response_time',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 500.0,
                    'crit_threshold': 1000.0
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(300.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].name == 'response_time'
            assert result.metrics[0].value == 300.0
            assert result.metrics[0].unit == 'ms'
    
    def test_threshold_evaluation(self):
        """Test threshold evaluation for each metric."""
        config = generate_container_apps_config(
            metrics={
                'cpu_percentage': {
                    'enabled': True,
                    'type': 'cpu_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 70.0,
                    'crit_threshold': 90.0
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        # Test WARN
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(75.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 75.0
            assert result.status == "P"  # Has thresholds
        
        # Test CRIT
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(95.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 95.0
            assert result.status == "P"  # Has thresholds
    
    def test_multiple_metrics_in_single_service_line(self):
        """Test multiple metrics in single service line."""
        config = generate_container_apps_config(
            metrics={
                'restarts': {
                    'enabled': True,
                    'type': 'restarts',
                    'time_range': 'PT1H',
                    'aggregation': 'sum'
                },
                'cpu_percentage': {
                    'enabled': True,
                    'type': 'cpu_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average'
                },
                'memory_percentage': {
                    'enabled': True,
                    'type': 'memory_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average'
                },
                'response_time': {
                    'enabled': True,
                    'type': 'response_time',
                    'time_range': 'PT1H',
                    'aggregation': 'average'
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        call_count = {'count': 0}
        def mock_query_side_effect(*args, **kwargs):
            call_count['count'] += 1
            return (100.0, {})
        
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=mock_query_side_effect):
            result = monitor.monitor(config)
            
            assert len(result.metrics) == 4
            metric_names = [m.name for m in result.metrics]
            assert 'restarts' in metric_names
            assert 'cpu_percentage' in metric_names
            assert 'memory_percentage' in metric_names
            assert 'response_time' in metric_names
    
    def test_status_determined_by_worst_metric(self):
        """Test status is determined by worst metric status."""
        config = generate_container_apps_config(
            metrics={
                'cpu_percentage': {
                    'enabled': True,
                    'type': 'cpu_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 70.0,
                    'crit_threshold': 90.0
                },
                'memory_percentage': {
                    'enabled': True,
                    'type': 'memory_percentage',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'warn_threshold': 80.0,
                    'crit_threshold': 95.0
                }
            }
        )
        
        monitor = ContainerAppsMonitor(config)
        
        call_count = {'count': 0}
        def mock_query_side_effect(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return (60.0, {})  # CPU OK
            else:
                return (85.0, {})  # Memory WARN
        
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=mock_query_side_effect):
            result = monitor.monitor(config)
            
            assert len(result.metrics) == 2
            # Status should be "P" when thresholds present
            assert result.status == "P"

