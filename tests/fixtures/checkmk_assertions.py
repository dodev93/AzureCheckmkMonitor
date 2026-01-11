#!/usr/bin/env python3
"""
Checkmk Format Assertion Helpers

Provides helper functions to assert Checkmk output format and MetricResult structure.
"""

import re
from typing import Union, Optional, List
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem


def assert_checkmk_format(output: str) -> None:
    """
    Assert output matches Checkmk format.
    
    Format: <status> "Service Name" <perf_data> <message>
    
    Args:
        output: Checkmk output string
    
    Raises:
        AssertionError: If format doesn't match
    """
    lines = output.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        
        # Should start with status code (0, 1, 2, 3, or P)
        assert re.match(r'^[0123P]', line), f"Line doesn't start with status code: {line}"
        
        # Should contain quoted service name
        assert '"' in line, f"Line doesn't contain quoted service name: {line}"


def assert_performance_data(perf_data: str, expected_format: str) -> None:
    """
    Assert performance data matches expected format.
    
    Format: metric=value;warn;crit;min;max
    
    Args:
        perf_data: Performance data string
        expected_format: Expected format pattern (can use regex)
    
    Raises:
        AssertionError: If format doesn't match
    """
    assert re.match(expected_format, perf_data), f"Performance data doesn't match expected format: {perf_data}"


def assert_metric_result(
    result: MetricResult,
    expected_status: Union[int, str],
    expected_metrics_count: int,
    expected_message: Optional[str] = None
) -> None:
    """
    Assert MetricResult matches expected values.
    
    Args:
        result: MetricResult instance
        expected_status: Expected status code (0, 1, 2, 3, or "P")
        expected_metrics_count: Expected number of metrics
        expected_message: Optional expected message (if None, not checked)
    
    Raises:
        AssertionError: If result doesn't match expectations
    """
    assert isinstance(result, MetricResult), "Result is not a MetricResult instance"
    assert result.status == expected_status, f"Status mismatch: expected {expected_status}, got {result.status}"
    assert len(result.metrics) == expected_metrics_count, f"Metrics count mismatch: expected {expected_metrics_count}, got {len(result.metrics)}"
    
    if expected_message is not None:
        assert result.message == expected_message, f"Message mismatch: expected '{expected_message}', got '{result.message}'"


def assert_ok_message(result: MetricResult) -> None:
    """Assert result has OK message."""
    assert result.message == "OK", f"Expected OK message, got: {result.message}"


def assert_problems_with_metadata(
    result: MetricResult,
    metadata_key: str,
    expected_problems: List[tuple]
) -> None:
    """
    Assert result has problems with metadata in expected format.
    
    Format: "Problems: ApiId: api1 (150) ; api2 (200)"
    
    Args:
        result: MetricResult instance
        metadata_key: Metadata key (e.g., "ApiId", "OperationName")
        expected_problems: List of (problem_name, problem_value) tuples
    
    Raises:
        AssertionError: If problems don't match
    """
    assert result.problems is not None, "Expected problems but got None"
    assert len(result.problems) == len(expected_problems), f"Problem count mismatch: expected {len(expected_problems)}, got {len(result.problems)}"
    
    # Check that message contains metadata key
    assert metadata_key in result.message, f"Message doesn't contain metadata key '{metadata_key}': {result.message}"
    
    # Check that all expected problems are in message
    for problem_name, problem_value in expected_problems:
        assert problem_name in result.message, f"Problem '{problem_name}' not found in message: {result.message}"
        assert str(problem_value) in result.message, f"Problem value '{problem_value}' not found in message: {result.message}"


def assert_metric_problems(
    result: MetricResult,
    expected_problems: List[tuple]
) -> None:
    """
    Assert result has metric problems - should show "Problem detected" when only metric problems exist.
    
    Format: "Problem detected" (when only metric problems exist, no metadata problems)
    
    Args:
        result: MetricResult instance
        expected_problems: List of (metric_name, value, status) tuples (for reference, not checked in message)
    
    Raises:
        AssertionError: If problems don't match
    """
    assert result.message == "Problem detected", f"Expected 'Problem detected' message, got: {result.message}"
    assert result.problems is None or len(result.problems) == 0, "Metric problems should only appear when no metadata problems exist"


def assert_service_line_format(service_line: str) -> None:
    """
    Assert service line matches Checkmk format.
    
    Format: <status> "Service Name" <perf_data> <message>
    
    Args:
        service_line: Service line string
    
    Raises:
        AssertionError: If format doesn't match
    """
    # Should start with status
    assert re.match(r'^[0123P]', service_line), f"Service line doesn't start with status: {service_line}"
    
    # Should contain quoted service name
    assert '"' in service_line, f"Service line doesn't contain quoted service name: {service_line}"


def assert_performance_data_format(perf_data: str) -> None:
    """
    Assert performance data matches format: metric=value;warn;crit;min;max
    
    Args:
        perf_data: Performance data string
    
    Raises:
        AssertionError: If format doesn't match
    """
    # Basic format check: metric=value;warn;crit;min;max
    pattern = r'^[^=]+=[^;]+(;[^;]*){0,4}$'
    assert re.match(pattern, perf_data), f"Performance data doesn't match format: {perf_data}"

