#!/usr/bin/env python3
"""
Azure Container Apps Monitor

Monitors Azure Container Apps using JSON-based configuration.
Supports all Container Apps metrics: restarts, cpu_percentage, memory_percentage, response_time.
"""

import sys
import time
from datetime import timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Callable

from checkmk.checkmk_formatter import CheckmkFormatter, Metric, MetricResult, MetricProblem
from .base_monitor import BaseMonitor
from exceptions import UnsupportedMetricTypeError
from utils import MonitorUtils

# ============================================================================
# Container Apps Metric Type Enum
# ============================================================================

class ContainerAppsMetricType(Enum):
    """Enumeration of supported Container Apps metric types."""
    RESTARTS = "restarts"
    CPU_PERCENTAGE = "cpu_percentage"
    MEMORY_PERCENTAGE = "memory_percentage"
    RESPONSE_TIME = "response_time"

# ============================================================================
# ContainerAppsMonitor Class
# ============================================================================

class ContainerAppsMonitor(BaseMonitor):
    """
    Azure Container Apps Monitor class.
    
    Encapsulates all Container Apps monitoring functionality with shared state management.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Container Apps monitor from configuration dictionary.
        
        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - location: str (required for Container Apps)
                - Additional resource-specific fields
        """
        # Initialize base class
        super().__init__()
        
        # Extract resource_id from config or build it
        self.resource_id = self.build_resource_id(config)
        # Extract location (required for Container Apps)
        self.location = config.get('location')
        if not self.location:
            raise ValueError("Missing 'location' in configuration (required for Container Apps)")

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
        service_name = common_config.get('service_name', 'Container Apps')
        
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
                metric_type = ContainerAppsMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in ContainerAppsMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in ContainerAppsMetricType]
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

    def _get_metric_methods(self) -> Dict[ContainerAppsMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            ContainerAppsMetricType.RESTARTS: self.monitor_restarts,
            ContainerAppsMetricType.CPU_PERCENTAGE: self.monitor_cpu_percentage,
            ContainerAppsMetricType.MEMORY_PERCENTAGE: self.monitor_memory_percentage,
            ContainerAppsMetricType.RESPONSE_TIME: self.monitor_response_time
        }
    
    def monitor_restarts(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor container restart count.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="RestartCount",
            metric_namespace="Microsoft.App/containerApps",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=None,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        value = int(value) if value is not None else 0
        
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
    
    def monitor_cpu_percentage(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor CPU usage percentage.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="CpuPercentage",
            metric_namespace="Microsoft.App/containerApps",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=None,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        value = float(value) if value is not None else 0.0
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=value,
            warn_threshold=config.get('warn_threshold'),
            crit_threshold=config.get('crit_threshold'),
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit='%'
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
    
    def monitor_memory_percentage(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor memory usage percentage.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="MemoryPercentage",
            metric_namespace="Microsoft.App/containerApps",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=None,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        value = float(value) if value is not None else 0.0
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=value,
            warn_threshold=config.get('warn_threshold'),
            crit_threshold=config.get('crit_threshold'),
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit='%'
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
    
    def monitor_response_time(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor response time in milliseconds.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Parse time_range (used for both time range and granularity)
        timespan = MonitorUtils.iso8601_to_timedelta(config['time_range'])
        granularity = timespan

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="ResponseTime",
            metric_namespace="Microsoft.App/containerApps",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=None,
            metadata_key=group_by_metadata if group_by_metadata else None,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )
        
        value = float(value) if value is not None else 0.0
        
        # Create Metric instance
        metric = Metric(
            name=metric_name,
            value=value,
            warn_threshold=config.get('warn_threshold'),
            crit_threshold=config.get('crit_threshold'),
            min_value=config.get('min'),
            max_value=config.get('max'),
            unit='ms'
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

