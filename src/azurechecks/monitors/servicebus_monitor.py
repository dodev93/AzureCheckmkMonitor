#!/usr/bin/env python3
"""
Azure Service Bus Namespace Monitor

Monitors Azure Service Bus Namespaces using JSON-based configuration.
Supports monitoring of incoming requests, server errors, deadletter messages, active messages, and size per queue.
"""

import sys
import time
from datetime import timedelta
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List, Callable

from .base_monitor import BaseMonitor
from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from exceptions import UnsupportedMetricTypeError
from utils import MonitorUtils

# ============================================================================
# Service Bus Metric Type Enum
# ============================================================================

class ServiceBusMetricType(Enum):
    """Enumeration of supported Service Bus metric types."""
    INCOMING_REQUESTS = "incoming_requests"
    SERVER_ERRORS = "server_errors"
    DEADLETTER_MESSAGES = "deadletter_messages"
    ACTIVE_MESSAGES = "active_messages"
    SIZE = "size"

# ============================================================================
# ServiceBusMonitor Class
# ============================================================================

class ServiceBusMonitor(BaseMonitor):
    """
    Azure Service Bus Namespace Monitor class.
    
    Encapsulates all Service Bus monitoring functionality with shared state management.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Service Bus monitor from configuration dictionary.
        
        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - location: str (required for Service Bus)
        """
        # Initialize base class
        super().__init__()
        
        # Extract resource_id from config or build it
        self.resource_id = self.build_resource_id(config)
        
        # Extract location (required for Service Bus)
        self.location = config.get('location')
        if not self.location:
            raise ValueError("Missing 'location' in configuration (required for Service Bus)")
    
    def monitor(self, config: Dict[str, Any], debug: bool = False) -> MetricResult:
        """
        Main monitoring method that runs all enabled metrics sequentially.
        
        Args:
            config: Full configuration dictionary with common config and metrics
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
            'service_name': config.get('service_name'),
            'group_by_metadata': config.get('group_by_metadata', 'EntityName'),
            'filter_metadata_values': config.get('filter_metadata_values')
        }
        
        # Get metric methods map
        metric_methods = self._get_metric_methods()
        
        # Collect all metrics and problematic metadata
        all_metrics = []
        all_problematic_metadata = []
        service_name = common_config.get('service_name', 'Service Bus')
        
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
                metric_type = ServiceBusMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in ServiceBusMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in ServiceBusMetricType]
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
    
    def _get_metric_methods(self) -> Dict[ServiceBusMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            ServiceBusMetricType.INCOMING_REQUESTS: self.monitor_incoming_requests,
            ServiceBusMetricType.SERVER_ERRORS: self.monitor_server_errors,
            ServiceBusMetricType.DEADLETTER_MESSAGES: self.monitor_deadletter_messages,
            ServiceBusMetricType.ACTIVE_MESSAGES: self.monitor_active_messages,
            ServiceBusMetricType.SIZE: self.monitor_size
        }
    
    def _build_metadata_filter(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Build Azure Monitor filter string from metadata filtering configuration.
        
        Uses filter_metadata_values (list of values) and group_by_metadata (metadata key)
        to build a filter string. If group_by_metadata is not specified, defaults to "EntityName"
        for Service Bus monitoring.
        
        Args:
            config: Configuration dictionary containing:
                - filter_metadata_values: Optional list of metadata values to filter by
                - group_by_metadata: Optional metadata key (defaults to "EntityName")
        
        Returns:
            Filter string for Azure Monitor query, or None if no filtering needed
        """
        filter_values = config.get('filter_metadata_values')
        if not filter_values:
            return None
        
        metadata_key = config.get('group_by_metadata', 'EntityName')
        return " or ".join(f"{metadata_key} eq '{value}'" for value in filter_values)
    
    def _monitor_metric_with_queue_filter(
        self,
        config: Dict[str, Any],
        metric_name: str,
        azure_metric_name: str,
        unit: str = '',
        debug: bool = False
    ) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Common method for monitoring Service Bus metrics with queue filtering.
        
        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            azure_metric_name: Azure Monitor metric name (e.g., 'IncomingRequests')
            unit: Unit for the metric (e.g., 'bytes', 'count', default: '')
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan
        
        # Build metadata filter
        filter_str = self._build_metadata_filter(config)
        
        # Query metric with breakdown to get both aggregated value and queue-level data
        group_by_metadata = config.get('group_by_metadata', 'EntityName')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name=azure_metric_name,
            metric_namespace="Microsoft.ServiceBus/namespaces",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=filter_str,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        # Handle None value
        if value is None:
            value = 0.0
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=float(value),
            warn_threshold=config.get('warn_threshold'),
            crit_threshold=config.get('crit_threshold'),
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit=unit
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
    
    def monitor_incoming_requests(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor incoming requests to Service Bus queues.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_metric_with_queue_filter(
            config, metric_name, "IncomingRequests",
            debug=debug
        )
    
    def monitor_server_errors(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor server errors (5xx) in Service Bus queues.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_metric_with_queue_filter(
            config, metric_name, "ServerErrors",
            debug=debug
        )
    
    def monitor_deadletter_messages(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor deadletter messages in Service Bus queues.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_metric_with_queue_filter(
            config, metric_name, "DeadletteredMessages",
            debug=debug
        )
    
    def monitor_active_messages(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor active messages in Service Bus queues.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_metric_with_queue_filter(
            config, metric_name, "ActiveMessages",
            debug=debug
        )
    
    def monitor_size(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor size of messages in Service Bus queues.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        return self._monitor_metric_with_queue_filter(
            config, metric_name, "Size",
            unit='bytes',
            debug=debug
        )

