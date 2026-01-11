#!/usr/bin/env python3
"""
Azure API Management (APIM) Monitor

Monitors APIM services using JSON-based configuration.
Supports all APIM metrics: request_count, requests_2xx, requests_4xx, requests_5xx, requests_by_codes.
"""

import sys
import time
from collections import defaultdict
from datetime import timedelta 
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Callable

from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from .base_monitor import BaseMonitor
from exceptions import UnsupportedMetricTypeError
from utils import MonitorUtils

# ============================================================================
# APIM Metric Type Enum
# ============================================================================

class APIMetricType(Enum):
    """Enumeration of supported APIM metric types."""
    REQUEST_COUNT = "request_count"
    REQUESTS_2XX = "requests_2xx"
    REQUESTS_4XX = "requests_4xx"
    REQUESTS_5XX = "requests_5xx"
    REQUESTS_BY_CODES = "requests_by_codes"

# ============================================================================
# Status Filter Constants
# ============================================================================

_STATUS_FILTERS = {
    '2xx': "GatewayResponseCodeCategory eq '2xx'",
    '4xx': "GatewayResponseCodeCategory eq '4xx'",
    '5xx': "GatewayResponseCodeCategory eq '5xx'"
}

# ============================================================================
# APIMMonitor Class
# ============================================================================

class APIMMonitor(BaseMonitor):
    """
    Azure API Management (APIM) Monitor class.
    
    Encapsulates all APIM monitoring functionality with shared state management.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize APIM monitor from configuration dictionary.
        
        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - location: str (required for APIM)
                - Additional resource-specific fields
        """
        # Initialize base class
        super().__init__()
        
        # Extract resource_id from config or build it
        self.resource_id = self.build_resource_id(config)
        # Extract location (required for APIM)
        self.location = config.get('location')
        if not self.location:
            raise ValueError("Missing 'location' in configuration (required for APIM)")

    def monitor(self, config: Dict[str, Any], debug: bool = False) -> MetricResult:
        """
        Main monitoring method that runs all enabled metrics sequentially.
        
        Args:
            config: Full configuration dictionary with common config, and metrics
            debug: Whether to print execution time for each metric
            
        Returns:
            Single MetricResult instance with all metrics
        """
        metrics_config = config.get('metrics', {})
        
        # Extract common configuration (can be overridden per metric)
        common_config = {
            'time_range': config.get('time_range'),
            'aggregation': config.get('aggregation'),
            'metadata_aggregation': config.get('metadata_aggregation'),
            'filter_metadata_values': config.get('filter_metadata_values'),
            'service_name': config.get('service_name'),
            'group_by_metadata': config.get('group_by_metadata')
        }
        
        # Get metric methods map
        metric_methods = self._get_metric_methods()
        
        # Collect all metrics and problematic metadata
        all_metrics = []
        all_problematic_metadata = []
        service_name = common_config.get('service_name', 'APIM')
        
        # Execute metrics sequentially
        for checkmk_metric_name, metric_config in metrics_config.items():
            # Skip if disabled
            if not metric_config.get('enabled', False):
                continue
            
            # Get metric type from config
            metric_type_str = metric_config.get('type')
            if not metric_type_str:
                continue
            
            # Convert string to enum
            try:
                metric_type = APIMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in APIMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in APIMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Merge common config with metric-specific config (metric config overrides common)
            merged_config = {**common_config, **metric_config}
            
            # Get method
            metric_method = metric_methods[metric_type]
            
            # Time execution if requested
            start_time = time.time() if debug else None
            
            try:
                # Execute metric method
                metric, problematic_metadata = metric_method(merged_config, checkmk_metric_name, debug=debug)
                
                # Collect results
                all_metrics.append(metric)
                if problematic_metadata:
                    all_problematic_metadata.extend(problematic_metadata)
            
            finally:
                # Print execution time
                if debug and start_time is not None:
                    execution_time = time.time() - start_time
                    print(
                        f"Metric '{checkmk_metric_name}' execution time: {execution_time:.3f}s",
                        file=sys.stderr
                    )
            
            # Note: Exceptions are not caught here - they propagate to generic_check.py
            # which handles them and outputs status 3 (UNKNOWN) with error message
        
        # Return result
        return MetricResult(
            service_name=service_name,
            metrics=all_metrics,
            problems=all_problematic_metadata if all_problematic_metadata else None
        )


    def get_requests_by_status_code(
        self,
        timespan: timedelta,
        aggregation: str,
        granularity: timedelta,
        status_codes: List[str],
        filter_str: Optional[str] = None,
        debug: bool = False
    ) -> Tuple[Dict[str, int], Dict[str, Dict[str, float]]]:
        """
        Get request counts filtered by status codes with API breakdown.

        Args:
            timespan: Time span as timedelta
            aggregation: Aggregation type
            granularity: Time granularity as timedelta
            status_codes: List of status codes to filter (e.g., ["200", "404"])
            filter_str: Optional additional filter string
            debug: Whether to print debug information
        Returns:
            Tuple of (status_code_to_count_dict, status_code_to_api_breakdown_dict)
            where status_code_to_api_breakdown_dict maps status_code -> {api_id: value}
        """
        requests_by_code = {}
        breakdown_by_code = {}
        
        # Execute queries sequentially
        for status_code in status_codes:
            # Build filter for this status code
            status_filter = f"GatewayResponseCode eq '{status_code}'"
            if filter_str:
                combined_filter = f"({filter_str}) and ({status_filter})"
            else:
                combined_filter = status_filter

            # Query Requests metric with status code filter and get breakdown
            value, api_breakdown = self.query_metric_with_breakdown(
                resource_id=self.resource_id,
                location=self.location,
                metric_name="Requests",
                metric_namespace="Microsoft.ApiManagement/service",
                timespan=timespan,
                aggregation=aggregation,
                granularity=granularity,
                filter_str=combined_filter,
                metadata_key='ApiId',
                metadata_aggregation=None,  # Defaults to aggregation parameter
                debug=debug
            )
            
            requests_by_code[status_code] = int(value) if value is not None else 0
            breakdown_by_code[status_code] = api_breakdown
        
        return requests_by_code, breakdown_by_code
    
    def _get_metric_methods(self) -> Dict[APIMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            APIMetricType.REQUEST_COUNT: self.monitor_request_count,
            APIMetricType.REQUESTS_2XX: self.monitor_requests_2xx,
            APIMetricType.REQUESTS_4XX: self.monitor_requests_4xx,
            APIMetricType.REQUESTS_5XX: self.monitor_requests_5xx,
            APIMetricType.REQUESTS_BY_CODES: self.monitor_requests_by_codes
        }
    
    def _build_metadata_filter(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Build Azure Monitor filter string from metadata filtering configuration.
        
        Uses filter_metadata_values (list of values) and group_by_metadata (metadata key)
        to build a filter string. If group_by_metadata is not specified, defaults to "ApiId"
        for backward compatibility.
        
        Args:
            config: Configuration dictionary containing:
                - filter_metadata_values: Optional list of metadata values to filter by
                - group_by_metadata: Optional metadata key (defaults to "ApiId")
        
        Returns:
            Filter string for Azure Monitor query, or None if no filtering needed
        """
        filter_values = config.get('filter_metadata_values')
        if not filter_values:
            return None
        
        metadata_key = config.get('group_by_metadata', 'ApiId')
        return " or ".join(f"{metadata_key} eq '{value}'" for value in filter_values)
    
    def _monitor_requests_with_status_filter(
        self,
        config: Dict[str, Any],
        metric_name: str,
        status_filter: Optional[str] = None,
        debug: bool = False
    ) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Common method for monitoring requests with optional status code filtering.
        
        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            status_filter: Optional status filter (e.g., "GatewayResponseCodeCategory eq '2xx'")
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Combine filters if status_filter is provided
        if status_filter:
            if filter_str:
                combined_filter = f"({filter_str}) and ({status_filter})"
            else:
                combined_filter = status_filter
        else:
            combined_filter = filter_str

        # Query metric with breakdown to get both aggregated value and API-level data
        group_by_metadata = config.get('group_by_metadata', 'ApiId')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        # Since config is already merged with common_config, check if metadata_aggregation exists in config
        # If not explicitly set in metric config, it will have the value from common_config due to merge
        # If explicitly None in metric config, we need to check if it was in common_config
        # For simplicity, we check config first (which includes merged common_config), then fall back to aggregation
        metadata_aggregation = config.get('metadata_aggregation')
        if metadata_aggregation is None:
            # If not set, use aggregation as fallback (common_config's metadata_aggregation would already be in config if it existed)
            metadata_aggregation = config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="Requests",
            metric_namespace="Microsoft.ApiManagement/service",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=combined_filter,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        # Preserve float precision when metadata aggregation is used (e.g., 'average' can produce floats)
        # Only convert to int if no metadata aggregation is being used
        if value is None:
            value = 0
        elif group_by_metadata:
            # Metadata aggregation can produce floats (e.g., average), preserve precision
            value = float(value)
        else:
            # No metadata aggregation, convert to int for discrete counts
            value = int(value)
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=float(value),
            warn_threshold=config.get('warn_threshold'),
            crit_threshold=config.get('crit_threshold'),
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit=''
        )
        
        # Extract problematic metadata if breakdown is available
        problematic_metadata = None
        if group_by_metadata and breakdown_dict:
            problematic_metadata = self._extract_problems(
                breakdown_dict=breakdown_dict,
                metadata_key=group_by_metadata,
                warn_threshold=config.get('warn_threshold'),
                crit_threshold=config.get('crit_threshold')
            )
            # Return None if empty list
            if not problematic_metadata:
                problematic_metadata = None
        
        return (metric, problematic_metadata)
    
    def monitor_request_count(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor total request count.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_requests_with_status_filter(config, metric_name, status_filter=None, debug=debug)
    
    def monitor_requests_2xx(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor 2xx response requests.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_requests_with_status_filter(
            config, metric_name, status_filter=_STATUS_FILTERS['2xx'], debug=debug
        )
    
    def monitor_requests_4xx(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor 4xx response requests.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_requests_with_status_filter(
            config, metric_name, status_filter=_STATUS_FILTERS['4xx'], debug=debug
        )
    
    def monitor_requests_5xx(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor 5xx response requests.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_requests_with_status_filter(
            config, metric_name, status_filter=_STATUS_FILTERS['5xx'], debug=debug
        )
    
    def monitor_requests_by_codes(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor requests filtered by specific response codes.
        Aggregates all status codes into a single metric value.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Get response codes
        response_codes = config.get('response_codes', [])

        # Get requests by status code with API breakdown
        requests_by_code, breakdown_by_code = self.get_requests_by_status_code(
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=timespan,
            status_codes=response_codes,
            filter_str=filter_str,
            debug=debug
        )
        
        # Aggregate all status codes into a single value
        total_value = sum(requests_by_code.values())
        
        # Aggregate breakdown_dict across all status codes using defaultdict
        total_breakdown = defaultdict(float)
        for api_breakdown in breakdown_by_code.values():
            for api_id, value in api_breakdown.items():
                total_breakdown[api_id] += value
        
        # Get thresholds
        warn_threshold = config.get('warn_threshold')
        crit_threshold = config.get('crit_threshold')
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=float(total_value),
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit=''
        )
        
        # Extract problematic metadata if breakdown is available
        group_by_metadata = config.get('group_by_metadata')
        problematic_metadata = None
        
        if group_by_metadata and total_breakdown:
            problematic_metadata = self._extract_problems(
                breakdown_dict=dict(total_breakdown),  # Convert defaultdict to dict
                metadata_key=group_by_metadata,
                warn_threshold=warn_threshold,
                crit_threshold=crit_threshold
            )
            # Return None if empty list
            if not problematic_metadata:
                problematic_metadata = None
        
        return (metric, problematic_metadata)