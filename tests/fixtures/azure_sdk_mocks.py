#!/usr/bin/env python3
"""
Azure SDK Mock Response Builders

Provides mock classes and builders for Azure SDK responses used in unit tests.
Matches the structure of azure-monitor-querymetrics SDK responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any


class MetricValue:
    """Mock structure for MetricValue (data point)"""
    
    def __init__(
        self,
        time_stamp: datetime,
        total: Optional[float] = None,
        average: Optional[float] = None,
        count: Optional[float] = None,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None
    ):
        self.time_stamp = time_stamp
        self.total = total
        self.average = average
        self.count = count
        self.minimum = minimum
        self.maximum = maximum


class TimeSeriesElement:
    """Mock structure for TimeSeriesElement"""
    
    def __init__(
        self,
        data: List[MetricValue],
        metadata_values: Optional[Dict[str, str]] = None
    ):
        self.data = data
        self.metadata_values = metadata_values


class Metric:
    """Mock structure for Metric"""
    
    def __init__(
        self,
        name: str,
        timeseries: List[TimeSeriesElement]
    ):
        self.name = name
        self.timeseries = timeseries


class MetricsQueryResult:
    """Mock structure for MetricsQueryResult"""
    
    def __init__(self, metrics: List[Metric]):
        self.metrics = metrics


def build_data_point(
    time_stamp: datetime,
    total: Optional[float] = None,
    average: Optional[float] = None,
    count: Optional[float] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None
) -> MetricValue:
    """Build mock MetricValue data point."""
    return MetricValue(
        time_stamp=time_stamp,
        total=total,
        average=average,
        count=count,
        minimum=minimum,
        maximum=maximum
    )


def build_metrics_query_result(
    metric_name: str,
    data_points: List[Dict[str, Any]],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """
    Build mock MetricsQueryResult with specified data points and metadata.
    
    Args:
        metric_name: Name of the metric (e.g., "Requests", "Transactions")
        data_points: List of dicts with keys: time_stamp, total, average, count, minimum, maximum
        metadata_values: Optional dict of metadata key-value pairs (e.g., {"ApiId": "api1"})
    
    Returns:
        MetricsQueryResult instance
    """
    metric_values = []
    for dp in data_points:
        metric_values.append(build_data_point(
            time_stamp=dp.get('time_stamp'),
            total=dp.get('total'),
            average=dp.get('average'),
            count=dp.get('count'),
            minimum=dp.get('minimum'),
            maximum=dp.get('maximum')
        ))
    
    timeseries = [TimeSeriesElement(data=metric_values, metadata_values=metadata_values)]
    metric = Metric(name=metric_name, timeseries=timeseries)
    return MetricsQueryResult(metrics=[metric])


def build_metrics_query_result_with_breakdown(
    metric_name: str,
    breakdown_data: List[Dict[str, Any]]
) -> MetricsQueryResult:
    """
    Build mock MetricsQueryResult with metadata breakdown (multiple timeseries).
    
    Args:
        metric_name: Name of the metric
        breakdown_data: List of dicts, each with:
            - metadata_values: Dict of metadata (e.g., {"ApiId": "api1"})
            - data_points: List of data point dicts
    
    Returns:
        MetricsQueryResult instance with multiple timeseries
    """
    timeseries_list = []
    for breakdown in breakdown_data:
        metadata_values = breakdown.get('metadata_values', {})
        data_points = breakdown.get('data_points', [])
        
        metric_values = []
        for dp in data_points:
            metric_values.append(build_data_point(
                time_stamp=dp.get('time_stamp'),
                total=dp.get('total'),
                average=dp.get('average'),
                count=dp.get('count'),
                minimum=dp.get('minimum'),
                maximum=dp.get('maximum')
            ))
        
        timeseries_list.append(TimeSeriesElement(
            data=metric_values,
            metadata_values=metadata_values
        ))
    
    metric = Metric(name=metric_name, timeseries=timeseries_list)
    return MetricsQueryResult(metrics=[metric])


def build_sum_aggregation_response(
    metric_name: str,
    values: List[float],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build response for sum aggregation with given values."""
    base_time = datetime(2024, 1, 1, 10, 0)
    data_points = []
    for i, val in enumerate(values):
        data_points.append({
            'time_stamp': base_time.replace(minute=base_time.minute + i * 5),
            'total': val,
            'average': None,
            'count': None,
            'minimum': None,
            'maximum': None
        })
    return build_metrics_query_result(metric_name, data_points, metadata_values)


def build_average_aggregation_response(
    metric_name: str,
    values: List[float],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build response for average aggregation with given values."""
    base_time = datetime(2024, 1, 1, 10, 0)
    data_points = []
    for i, val in enumerate(values):
        data_points.append({
            'time_stamp': base_time.replace(minute=base_time.minute + i * 5),
            'total': None,
            'average': val,
            'count': None,
            'minimum': None,
            'maximum': None
        })
    return build_metrics_query_result(metric_name, data_points, metadata_values)


def build_count_aggregation_response(
    metric_name: str,
    values: List[float],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build response for count aggregation with given values."""
    base_time = datetime(2024, 1, 1, 10, 0)
    data_points = []
    for i, val in enumerate(values):
        data_points.append({
            'time_stamp': base_time.replace(minute=base_time.minute + i * 5),
            'total': None,
            'average': None,
            'count': val,
            'minimum': None,
            'maximum': None
        })
    return build_metrics_query_result(metric_name, data_points, metadata_values)


def build_min_aggregation_response(
    metric_name: str,
    values: List[float],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build response for min aggregation with given values."""
    base_time = datetime(2024, 1, 1, 10, 0)
    data_points = []
    for i, val in enumerate(values):
        data_points.append({
            'time_stamp': base_time.replace(minute=base_time.minute + i * 5),
            'total': None,
            'average': None,
            'count': None,
            'minimum': val,
            'maximum': None
        })
    return build_metrics_query_result(metric_name, data_points, metadata_values)


def build_max_aggregation_response(
    metric_name: str,
    values: List[float],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build response for max aggregation with given values."""
    base_time = datetime(2024, 1, 1, 10, 0)
    data_points = []
    for i, val in enumerate(values):
        data_points.append({
            'time_stamp': base_time.replace(minute=base_time.minute + i * 5),
            'total': None,
            'average': None,
            'count': None,
            'minimum': None,
            'maximum': val
        })
    return build_metrics_query_result(metric_name, data_points, metadata_values)

