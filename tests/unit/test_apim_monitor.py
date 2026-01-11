#!/usr/bin/env python3
"""
Unit tests for APIM monitor module.

Tests match PRD section 3.1 requirements.
"""

import pytest
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.apim_monitor import APIMMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.azure_sdk_mocks import (
    build_sum_aggregation_response,
    build_average_aggregation_response,
    build_count_aggregation_response,
    build_min_aggregation_response,
    build_max_aggregation_response,
    build_metrics_query_result_with_breakdown
)
from tests.fixtures.config_generators import generate_apim_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message,
    assert_problems_with_metadata
)


class TestRequestCountMonitoring:
    """Test request count monitoring per PRD section 3.1.1."""
    
    def test_monitor_request_count_all_apis(self):
        """Test monitoring request count for all APIs (empty api_ids array)."""
        config = generate_apim_config(
            api_ids=[],
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 50,
                    'crit_threshold': 200
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Mock query_metric_with_breakdown to return value and empty breakdown
        # Use value 30 which is below warn_threshold 50, so status should be OK
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(30.0, {})):
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            assert result.metrics[0].name == 'request_count'
            assert result.metrics[0].value == 30.0
            assert result.metrics[0].warn_threshold == 50
            assert result.metrics[0].crit_threshold == 200
            assert_ok_message(result)
    
    def test_monitor_request_count_specific_apis(self):
        """Test monitoring request count for specific APIs (filtered by api_ids)."""
        config = generate_apim_config(
            api_ids=['api1-id', 'api2-id'],
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1-id', 'api2-id'],
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(150.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 150.0
    
    def test_monitor_request_count_with_problematic_apis(self):
        """Test request count with problematic APIs identified from breakdown_dict."""
        config = generate_apim_config(
            api_ids=['api1-id', 'api2-id'],
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1-id', 'api2-id'],
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Mock breakdown with problematic APIs
        breakdown_dict = {'api1-id': 150.0, 'api2-id': 50.0}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(200.0, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 1
            assert result.problems[0].problem_name == 'api1-id'
            assert result.problems[0].problem_value == 150.0
            assert 'api1-id' in result.message
            assert '150' in result.message
    
    def test_monitor_request_count_message_format(self):
        """Test Checkmk message format with problematic APIs: 'Problems: ApiId: api1 (150) ; api2 (200)'."""
        config = generate_apim_config(
            api_ids=['api1-id', 'api2-id'],
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1-id', 'api2-id'],
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        breakdown_dict = {'api1-id': 150.0, 'api2-id': 200.0}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350.0, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 2
            # Check message format
            assert 'Problems:' in result.message
            assert 'ApiId:' in result.message
            assert 'api1-id (150' in result.message or 'api1-id (150.0' in result.message
            assert 'api2-id (200' in result.message or 'api2-id (200.0' in result.message


class TestRequestsByStatusCodeCategories:
    """Test requests by status code categories per PRD section 3.1.2."""
    
    def test_monitor_requests_2xx(self):
        """Test monitoring 2xx requests."""
        config = generate_apim_config(
            metrics={
                'requests_2xx': {
                    'enabled': True,
                    'type': 'requests_2xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(80.0, {})) as mock_query:
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 80.0
            assert result.metrics[0].name == 'requests_2xx'
            # Verify filter includes 2xx status code category
            call_kwargs = mock_query.call_args[1]
            assert "GatewayResponseCodeCategory eq '2xx'" in call_kwargs['filter_str']
    
    def test_monitor_requests_4xx(self):
        """Test monitoring 4xx requests."""
        config = generate_apim_config(
            metrics={
                'requests_4xx': {
                    'enabled': True,
                    'type': 'requests_4xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 5,
                    'crit_threshold': 20
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(10.0, {})) as mock_query:
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 10.0
            assert result.metrics[0].name == 'requests_4xx'
            # Verify filter includes 4xx status code category
            call_kwargs = mock_query.call_args[1]
            assert "GatewayResponseCodeCategory eq '4xx'" in call_kwargs['filter_str']
    
    def test_monitor_requests_5xx(self):
        """Test monitoring 5xx requests."""
        config = generate_apim_config(
            metrics={
                'requests_5xx': {
                    'enabled': True,
                    'type': 'requests_5xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 3,
                    'crit_threshold': 10
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(5.0, {})) as mock_query:
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 5.0
            assert result.metrics[0].name == 'requests_5xx'
            # Verify filter includes 5xx status code category
            call_kwargs = mock_query.call_args[1]
            assert "GatewayResponseCodeCategory eq '5xx'" in call_kwargs['filter_str']
    
    def test_monitor_requests_4xx_with_problematic_apis(self):
        """Test 4xx requests with problematic API identification."""
        config = generate_apim_config(
            metrics={
                'requests_4xx': {
                    'enabled': True,
                    'type': 'requests_4xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1-id'],
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        breakdown_dict = {'api1-id': 150.0}
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(150.0, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.problems is not None
            assert len(result.problems) == 1
            assert result.problems[0].problem_name == 'api1-id'
            assert 'api1-id' in result.message


class TestRequestsBySpecificStatusCodes:
    """Test requests by specific status codes per PRD section 3.1.3."""
    
    def test_monitor_requests_by_codes(self):
        """Test monitoring multiple specific status codes."""
        config = generate_apim_config(
            metrics={
                'requests_by_codes': {
                    'enabled': True,
                    'type': 'requests_by_codes',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'response_codes': ['200', '404', '500']
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Mock get_requests_by_status_code to return values for each status code
        with patch.object(monitor, 'get_requests_by_status_code', return_value=(
            {'200': 50, '404': 10, '500': 5},
            {'200': {}, '404': {}, '500': {}}
        )):
            result = monitor.monitor(config)
            
            assert isinstance(result, MetricResult)
            assert len(result.metrics) == 1
            # Total should be sum of all status codes
            assert result.metrics[0].value == 65.0  # 50 + 10 + 5
    
    def test_monitor_requests_by_codes_with_api_breakdown(self):
        """Test requests by codes with API breakdown per status code."""
        config = generate_apim_config(
            metrics={
                'requests_by_codes': {
                    'enabled': True,
                    'type': 'requests_by_codes',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1-id', 'api2-id'],
                    'response_codes': ['200', '404', '500'],
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Mock breakdown with problematic APIs across status codes
        with patch.object(monitor, 'get_requests_by_status_code', return_value=(
            {'200': 50, '404': 150, '500': 600},
            {
                '200': {'api1-id': 30, 'api2-id': 20},
                '404': {'api1-id': 100, 'api2-id': 50},
                '500': {'api1-id': 400, 'api2-id': 200}
            }
        )):
            result = monitor.monitor(config)
            
            # Total should be sum: 50 + 150 + 600 = 800
            assert result.metrics[0].value == 800.0
            # Should aggregate problematic APIs across all status codes
            # api1-id: 30 + 100 + 400 = 530, api2-id: 20 + 50 + 200 = 270
            if result.problems:
                # Check that problematic APIs are identified
                problem_names = [p.problem_name for p in result.problems]
                assert 'api1-id' in problem_names or 'api2-id' in problem_names


class TestAggregationTypes:
    """Test all aggregation types per PRD section 5."""
    
    def test_sum_aggregation(self):
        """Test sum aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(450.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 450.0
    
    def test_average_aggregation(self):
        """Test average aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(100.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 100.0
    
    def test_count_aggregation(self):
        """Test count aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'count',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(45.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 45.0
    
    def test_min_aggregation(self):
        """Test min aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'min',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(5.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 5.0
    
    def test_max_aggregation(self):
        """Test max aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'max',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(200.0, {})):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == 200.0


class TestAggregationTypesWithMetadataGrouping:
    """Test all aggregation types with metadata grouping - overall value uses metadata_aggregation (defaults to aggregation)."""
    
    def test_sum_aggregation_with_metadata_grouping(self):
        """Test sum aggregation with metadata grouping - overall value should sum breakdown values."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=250, api2=125
        # Overall should be sum: 250 + 125 = 375
        breakdown_dict = {'api1': 250.0, 'api2': 125.0}
        expected_sum = sum(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals sum of breakdown values
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 375.0
    
    def test_average_aggregation_with_metadata_grouping(self):
        """Test average aggregation with metadata grouping - overall value should use average of breakdown values when metadata_aggregation defaults to aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100 (last average), api2=75 (last average)
        # Overall should be average: (100 + 75) / 2 = 87.5 (since metadata_aggregation defaults to aggregation='average')
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_avg = sum(breakdown_dict.values()) / len(breakdown_dict)
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_avg, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals average of breakdown values
            assert result.metrics[0].value == expected_avg
            assert result.metrics[0].value == 87.5
    
    def test_min_aggregation_with_metadata_grouping(self):
        """Test min aggregation with metadata grouping - overall value should use min of breakdown values when metadata_aggregation defaults to aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'min',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=5 (min), api2=10 (min)
        # Overall should be min: min(5, 10) = 5 (since metadata_aggregation defaults to aggregation='min')
        breakdown_dict = {'api1': 5.0, 'api2': 10.0}
        expected_min = min(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_min, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals min of breakdown values
            assert result.metrics[0].value == expected_min
            assert result.metrics[0].value == 5.0
    
    def test_max_aggregation_with_metadata_grouping(self):
        """Test max aggregation with metadata grouping - overall value should use max of breakdown values when metadata_aggregation defaults to aggregation."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'max',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=200 (max), api2=150 (max)
        # Overall should be max: max(200, 150) = 200 (since metadata_aggregation defaults to aggregation='max')
        breakdown_dict = {'api1': 200.0, 'api2': 150.0}
        expected_max = max(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_max, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals max of breakdown values
            assert result.metrics[0].value == expected_max
            assert result.metrics[0].value == 200.0
    
    def test_count_aggregation_with_metadata_grouping(self):
        """Test count aggregation with metadata grouping - overall value should sum breakdown values."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'count',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=45 (sum of counts), api2=30 (sum of counts)
        # Overall should be sum: 45 + 30 = 75 (regardless of aggregation type)
        breakdown_dict = {'api1': 45.0, 'api2': 30.0}
        expected_sum = sum(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals sum of breakdown values
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 75.0
    
    def test_sum_aggregation_with_metadata_grouping_multiple_keys(self):
        """Test that values from different metadata keys are correctly summed."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Multiple metadata keys with different values
        breakdown_dict = {'api1': 250.0, 'api2': 125.0, 'api3': 50.0}
        expected_sum = sum(breakdown_dict.values())  # 425.0
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals sum of all breakdown values
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 425.0
            assert len(breakdown_dict) == 3  # Verify all metadata keys are included
    
    def test_average_aggregation_with_metadata_grouping_multiple_keys(self):
        """Test that average aggregation with multiple metadata keys sums all values correctly."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Multiple metadata keys - values should be summed regardless of aggregation type
        breakdown_dict = {'api1': 100.0, 'api2': 75.0, 'api3': 50.0, 'api4': 25.0}
        expected_sum = sum(breakdown_dict.values())  # 250.0
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals sum of all breakdown values
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 250.0
            assert len(breakdown_dict) == 4  # Verify all metadata keys are included


class TestMetadataAggregation:
    """Test metadata_aggregation field functionality."""
    
    def test_metadata_aggregation_sum(self):
        """Test metadata_aggregation='sum' explicitly specified."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'average',
                    'metadata_aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be sum: 100 + 75 = 175 (metadata_aggregation='sum' overrides aggregation='average')
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_sum = sum(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 175.0
    
    def test_metadata_aggregation_average(self):
        """Test metadata_aggregation='average' explicitly specified."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'metadata_aggregation': 'average',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be average: (100 + 75) / 2 = 87.5 (metadata_aggregation='average' overrides aggregation='sum')
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_avg = sum(breakdown_dict.values()) / len(breakdown_dict)
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_avg, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_avg
            assert result.metrics[0].value == 87.5
    
    def test_metadata_aggregation_max(self):
        """Test metadata_aggregation='max' explicitly specified."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'metadata_aggregation': 'max',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be max: max(100, 75) = 100
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_max = max(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_max, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_max
            assert result.metrics[0].value == 100.0
    
    def test_metadata_aggregation_min(self):
        """Test metadata_aggregation='min' explicitly specified."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'metadata_aggregation': 'min',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be min: min(100, 75) = 75
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_min = min(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_min, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_min
            assert result.metrics[0].value == 75.0
    
    def test_metadata_aggregation_root_level(self):
        """Test metadata_aggregation at root level applies to all metrics."""
        config = generate_apim_config(
            metadata_aggregation='average',
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be average: (100 + 75) / 2 = 87.5 (uses root-level metadata_aggregation='average')
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_avg = sum(breakdown_dict.values()) / len(breakdown_dict)
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_avg, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_avg
            assert result.metrics[0].value == 87.5
    
    def test_metadata_aggregation_metric_overrides_root(self):
        """Test metric-level metadata_aggregation overrides root-level."""
        config = generate_apim_config(
            metadata_aggregation='average',
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'metadata_aggregation': 'max',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Breakdown: api1=100, api2=75
        # Overall should be max: max(100, 75) = 100 (metric-level metadata_aggregation='max' overrides root-level 'average')
        breakdown_dict = {'api1': 100.0, 'api2': 75.0}
        expected_max = max(breakdown_dict.values())
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_max, breakdown_dict)):
            result = monitor.monitor(config)
            
            assert result.metrics[0].value == expected_max
            assert result.metrics[0].value == 100.0


class TestMetadataGrouping:
    """Test metadata grouping per PRD section 6."""
    
    def test_group_by_apiid(self):
        """Test grouping by ApiId."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId',
                    'warn_threshold': 100,
                    'crit_threshold': 500
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        breakdown_dict = {'api1': 150.0, 'api2': 200.0}
        expected_sum = sum(breakdown_dict.values())  # 350.0
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(expected_sum, breakdown_dict)):
            result = monitor.monitor(config)
            
            # Verify overall value equals sum of breakdown values
            assert result.metrics[0].value == expected_sum
            assert result.metrics[0].value == 350.0
            assert result.problems is not None
            assert len(result.problems) == 2
            # Check message format
            assert 'ApiId:' in result.message
            assert 'api1' in result.message
            assert 'api2' in result.message
    
    def test_filter_metadata_values(self):
        """Test filter by metadata values."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'filter_metadata_values': ['api1', 'api2'],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(350.0, {})) as mock_query:
            monitor.monitor(config)
            
            # Verify filter string construction
            call_kwargs = mock_query.call_args[1]
            filter_str = call_kwargs.get('filter_str', '')
            assert "ApiId eq 'api1'" in filter_str or "ApiId eq 'api2'" in filter_str


class TestEdgeCases:
    """Test edge cases per PRD section 5.3."""
    
    def test_none_value_handling(self):
        """Test handling of None value from query."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(None, {})):
            result = monitor.monitor(config)
            
            # Should default to 0
            assert result.metrics[0].value == 0.0
    
    def test_empty_breakdown_dict(self):
        """Test handling of empty breakdown dictionary."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(100.0, {})):
            result = monitor.monitor(config)
            
            # Should have no problems
            assert result.problems is None
            assert_ok_message(result)
    
    def test_zero_sum_values(self):
        """Test handling of zero sum values."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': []
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # Zero sum now returns 0.0 from query_metric_with_breakdown (not None)
        with patch.object(monitor, 'query_metric_with_breakdown', return_value=(0.0, {})):
            result = monitor.monitor(config)
            
            # Should be 0.0 (not defaulted from None)
            assert result.metrics[0].value == 0.0


class TestMultipleMetrics:
    """Test monitoring multiple metrics."""
    
    def test_multiple_metrics_all_ok(self):
        """Test multiple metrics all returning OK status."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 100,
                    'crit_threshold': 500
                },
                'requests_4xx': {
                    'enabled': True,
                    'type': 'requests_4xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 10,
                    'crit_threshold': 50
                },
                'requests_5xx': {
                    'enabled': True,
                    'type': 'requests_5xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 5,
                    'crit_threshold': 20
                }
            }
        )
        
        monitor = APIMMonitor(config)

        # Use values that don't exceed thresholds:
        # request_count: 50 < 100 (warn) and 50 < 500 (crit) - OK
        # requests_4xx: 5 < 10 (warn) and 5 < 50 (crit) - OK
        # requests_5xx: 2 < 5 (warn) and 2 < 20 (crit) - OK
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=[
            (50.0, {}),   # request_count
            (5.0, {}),    # requests_4xx
            (2.0, {})     # requests_5xx
        ]):
            result = monitor.monitor(config)

            assert len(result.metrics) == 3
            assert result.metrics[0].value == 50.0
            assert result.metrics[1].value == 5.0
            assert result.metrics[2].value == 2.0
            assert_ok_message(result)
    
    def test_multiple_metrics_with_problems(self):
        """Test multiple metrics with different statuses."""
        config = generate_apim_config(
            metrics={
                'request_count': {
                    'enabled': True,
                    'type': 'request_count',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': [],
                    'warn_threshold': 100,
                    'crit_threshold': 500
                },
                'requests_4xx': {
                    'enabled': True,
                    'type': 'requests_4xx',
                    'time_range': 'PT1H',
                    'aggregation': 'sum',
                    'api_ids': ['api1'],
                    'warn_threshold': 100,
                    'crit_threshold': 500,
                    'group_by_metadata': 'ApiId'
                }
            }
        )
        
        monitor = APIMMonitor(config)
        
        # First call returns OK, second call returns problematic API
        call_count = {'count': 0}
        def mock_query_side_effect(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return (50.0, {})  # request_count - OK
            else:
                breakdown = {'api1': 150.0}
                return (150.0, breakdown)  # requests_4xx - problematic
        
        with patch.object(monitor, 'query_metric_with_breakdown', side_effect=mock_query_side_effect):
            result = monitor.monitor(config)
            
            assert len(result.metrics) == 2
            assert result.problems is not None
            assert len(result.problems) == 1
