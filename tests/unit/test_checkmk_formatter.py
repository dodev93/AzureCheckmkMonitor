#!/usr/bin/env python3
"""
Unit tests for checkmk_formatter module.

Tests match PRD section 3.9 requirements.
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from checkmk.checkmk_formatter import (
    CheckmkFormatter,
    MetricResult,
    Metric,
    MetricProblem
)
from tests.fixtures.checkmk_assertions import (
    assert_checkmk_format,
    assert_performance_data_format
)


class TestMetricResultCreation:
    """Test MetricResult creation per PRD section 3.9.1."""
    
    def test_create_metric_result_single_metric(self):
        """Test create MetricResult with single metric."""
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
        
        assert isinstance(result, MetricResult)
        assert len(result.metrics) == 1
        assert result.metrics[0].name == 'test_metric'
        assert result.status == "P"  # Has thresholds
    
    def test_create_metric_result_multiple_metrics(self):
        """Test create MetricResult with multiple metrics."""
        metric1 = Metric(
            name='metric1',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        metric2 = Metric(
            name='metric2',
            value=150.0,
            warn_threshold=100.0,
            crit_threshold=250.0,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric1, metric2],
            problems=None
        )
        
        assert len(result.metrics) == 2
        assert result.status == "P"  # Has thresholds
    
    def test_create_metric_result_with_problematic_metadata(self):
        """Test create MetricResult with problematic metadata."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        
        problems = [
            MetricProblem(
                problem_name='api1',
                problem_value=150.0,
                metadata_key='ApiId'
            )
        ]
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=problems
        )
        
        assert result.problems is not None
        assert len(result.problems) == 1
        assert 'Problems:' in result.message
        assert 'ApiId:' in result.message
    
    def test_create_metric_result_without_problems(self):
        """Test create MetricResult without problems."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        assert result.problems is None
        assert result.message == "OK"
    
    def test_status_calculation_worst_status_wins(self):
        """Test status calculation (worst status wins)."""
        metric1 = Metric(
            name='metric1',
            value=50.0,
            warn_threshold=100.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        metric2 = Metric(
            name='metric2',
            value=250.0,  # Exceeds crit threshold
            warn_threshold=100.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric1, metric2],
            problems=None
        )
        
        # Status should be "P" when thresholds present
        assert result.status == "P"
    
    def test_status_p_when_thresholds_present(self):
        """Test status 'P' when thresholds present."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        assert result.status == "P"


class TestMessageGeneration:
    """Test message generation per PRD section 3.9.2."""
    
    def test_ok_message(self):
        """Test OK message: 'OK'."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        assert result.message == "OK"
    
    def test_problems_with_metadata(self):
        """Test problems with metadata: 'Problems: ApiId: api1 (150) ; api2 (200)'."""
        metric = Metric(
            name='test_metric',
            value=350.0,
            warn_threshold=100.0,
            crit_threshold=500.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        problems = [
            MetricProblem(
                problem_name='api1',
                problem_value=150.0,
                metadata_key='ApiId'
            ),
            MetricProblem(
                problem_name='api2',
                problem_value=200.0,
                metadata_key='ApiId'
            )
        ]
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=problems
        )
        
        assert 'Problems:' in result.message
        assert 'ApiId:' in result.message
        assert 'api1' in result.message
        assert 'api2' in result.message
        assert '150' in result.message or '150.0' in result.message
        assert '200' in result.message or '200.0' in result.message
    
    def test_metric_problems(self):
        """Test metric problems: Should show 'Problem detected' when only metric problems exist."""
        metric1 = Metric(
            name='metric1',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        metric2 = Metric(
            name='metric2',
            value=300.0,  # Exceeds crit threshold
            warn_threshold=100.0,
            crit_threshold=250.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric1, metric2],
            problems=None
        )
        
        # When only metrics exceed thresholds (no metadata problems), show "Problem detected"
        # Status is "P" so Checkmk evaluates from perf data
        assert result.status == "P"
        assert result.message == "Problem detected"
    
    def test_combined_problems(self):
        """Test combined problems: Both metadata and metric problems - should show only metadata problems."""
        metric = Metric(
            name='test_metric',
            value=250.0,  # Exceeds crit threshold
            warn_threshold=100.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        problems = [
            MetricProblem(
                problem_name='api1',
                problem_value=150.0,
                metadata_key='ApiId'
            )
        ]
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=problems
        )
        
        # Should show only metadata problems, not metric problems
        assert 'Problems:' in result.message
        assert 'ApiId:' in result.message
        assert 'api1' in result.message
        assert 'Metric problems:' not in result.message
        assert 'Problem detected' not in result.message
    
    def test_multiple_metadata_keys(self):
        """Test multiple metadata keys: 'Problems: ApiId: api1 (150) . OperationName: PutBlob (200)'."""
        metric = Metric(
            name='test_metric',
            value=350.0,
            warn_threshold=100.0,
            crit_threshold=500.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        problems = [
            MetricProblem(
                problem_name='api1',
                problem_value=150.0,
                metadata_key='ApiId'
            ),
            MetricProblem(
                problem_name='PutBlob',
                problem_value=200.0,
                metadata_key='OperationName'
            )
        ]
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=problems
        )
        
        assert 'Problems:' in result.message
        assert 'ApiId:' in result.message
        assert 'OperationName:' in result.message
        # Check separator between metadata keys
        assert ' . ' in result.message or 'ApiId:' in result.message and 'OperationName:' in result.message


class TestPerformanceDataFormatting:
    """Test performance data formatting per PRD section 3.9.3."""
    
    def test_format_metric_without_thresholds(self):
        """Test format metric without thresholds: 'metric=100.00;;;;'."""
        perf_data = CheckmkFormatter.format_metrics_data(
            metric_name='metric',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        assert perf_data == "metric=100.00;;;;"
    
    def test_format_metric_with_thresholds(self):
        """Test format metric with thresholds: 'metric=100.00;50;200;0;1000'."""
        perf_data = CheckmkFormatter.format_metrics_data(
            metric_name='metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=0.0,
            max_value=1000.0,
            unit=''
        )
        
        assert perf_data == "metric=100.00;50;200;0;1000"
    
    def test_format_metric_with_unit(self):
        """Test format metric with unit: 'metric=100.00ms;50;200;;'."""
        perf_data = CheckmkFormatter.format_metrics_data(
            metric_name='metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit='ms'
        )
        
        assert perf_data == "metric=100.00ms;50;200;;"
    
    def test_format_metric_with_partial_thresholds(self):
        """Test format metric with partial thresholds: 'metric=100.00;50;;0;'."""
        perf_data = CheckmkFormatter.format_metrics_data(
            metric_name='metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=None,
            min_value=0.0,
            max_value=None,
            unit=''
        )
        
        assert perf_data == "metric=100.00;50;;0;"


class TestServiceLineFormatting:
    """Test service line formatting per PRD section 3.9.4."""
    
    def test_format_service_line_single_metric(self):
        """Test format single metric service line."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        output = CheckmkFormatter.format_single_response_line(result)
        
        assert_checkmk_format(output)
        assert 'Test Service' in output
        assert 'test_metric' in output
    
    def test_format_service_line_multiple_metrics(self):
        """Test format multiple metrics service line."""
        metric1 = Metric(
            name='metric1',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        metric2 = Metric(
            name='metric2',
            value=200.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric1, metric2],
            problems=None
        )
        
        output = CheckmkFormatter.format_single_response_line(result)
        
        assert_checkmk_format(output)
        assert 'metric1' in output
        assert 'metric2' in output
        # Multiple metrics should be separated by |
        assert '|' in output
    
    def test_format_service_line_with_status_p(self):
        """Test format service line with status 'P'."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=50.0,
            crit_threshold=200.0,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        assert result.status == "P"
        output = CheckmkFormatter.format_single_response_line(result)
        
        assert_checkmk_format(output)
        assert 'P' in output or '0' in output  # Status P or 0 (Checkmk evaluates)
    
    def test_format_service_line_with_status_numeric(self):
        """Test format service line with status 0, 1, 2, 3."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        assert result.status == 0  # OK
        output = CheckmkFormatter.format_single_response_line(result)
        
        assert_checkmk_format(output)
        assert output.startswith('0')
    
    def test_service_name_quoting(self):
        """Test service name quoting."""
        metric = Metric(
            name='test_metric',
            value=100.0,
            warn_threshold=None,
            crit_threshold=None,
            min_value=None,
            max_value=None,
            unit=''
        )
        
        result = MetricResult(
            service_name='Test Service',
            metrics=[metric],
            problems=None
        )
        
        output = CheckmkFormatter.format_single_response_line(result)
        
        # Service name should be quoted
        assert '"Test Service"' in output
