#!/usr/bin/env python3
"""
Azure Kubernetes Service (AKS) Monitor

Monitors Azure Kubernetes Service clusters using JSON-based configuration.
Supports all AKS metrics: not_ready_nodes, node_cpu_percent, node_memory_percent, node_disk_percent.
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
# AKS Metric Type Enum
# ============================================================================

class AKSMetricType(Enum):
    """Enumeration of supported AKS metric types."""
    NOT_READY_NODES = "not_ready_nodes"
    NODE_CPU_PERCENT = "node_cpu_percent"
    NODE_MEMORY_PERCENT = "node_memory_percent"
    NODE_DISK_PERCENT = "node_disk_percent"

# ============================================================================
# AKSMonitor Class
# ============================================================================

class AKSMonitor(BaseMonitor):
    """
    Azure Kubernetes Service (AKS) Monitor class.
    
    Encapsulates all AKS monitoring functionality with shared state management.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AKS monitor from configuration dictionary.
        
        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - location: str (required for AKS)
                - Additional resource-specific fields
        """
        # Initialize base class
        super().__init__()
        
        # Extract resource_id from config or build it
        self.resource_id = self.build_resource_id(config)
        # Extract location (required for AKS)
        self.location = config.get('location')
        if not self.location:
            raise ValueError("Missing 'location' in configuration (required for AKS)")

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
        service_name = common_config.get('service_name', 'AKS')
        
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
                metric_type = AKSMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in AKSMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in AKSMetricType]
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

    def _get_metric_methods(self) -> Dict[AKSMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            AKSMetricType.NOT_READY_NODES: self.monitor_not_ready_nodes,
            AKSMetricType.NODE_CPU_PERCENT: self.monitor_node_cpu_percent,
            AKSMetricType.NODE_MEMORY_PERCENT: self.monitor_node_memory_percent,
            AKSMetricType.NODE_DISK_PERCENT: self.monitor_node_disk_percent
        }
    
    def _build_metadata_filter(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Build Azure Monitor filter string from metadata filtering configuration.
        
        Uses filter_metadata_values (list of values) and group_by_metadata (metadata key)
        to build a filter string. If group_by_metadata is not specified, defaults to "node"
        for AKS monitoring.
        
        Args:
            config: Configuration dictionary containing:
                - filter_metadata_values: Optional list of metadata values to filter by
                - group_by_metadata: Optional metadata key (defaults to "node")
        
        Returns:
            Filter string for Azure Monitor query, or None if no filtering needed
        """
        filter_values = config.get('filter_metadata_values')
        if not filter_values:
            return None
        
        metadata_key = config.get('group_by_metadata', 'node')
        return " or ".join(f"{metadata_key} eq '{value}'" for value in filter_values)
    
    def monitor_not_ready_nodes(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor number of nodes in NotReady state.

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

        # Build filter for NotReady condition
        not_ready_filter = "condition eq 'NotReady'"
        
        # Build filter from metadata filtering configuration (e.g., node pool filtering)
        metadata_filter = self._build_metadata_filter(config)
        
        # Combine filters
        if metadata_filter:
            combined_filter = f"({not_ready_filter}) and ({metadata_filter})"
        else:
            combined_filter = not_ready_filter

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="kube_node_status_condition",
            metric_namespace="Microsoft.ContainerService/managedClusters",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=combined_filter,
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
    
    def monitor_node_cpu_percent(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor node CPU usage percentage.

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

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="node_cpu_usage_percentage",
            metric_namespace="Microsoft.ContainerService/managedClusters",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=filter_str,
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
    
    def monitor_node_memory_percent(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor node memory usage percentage.

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

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="node_memory_working_set_percentage",
            metric_namespace="Microsoft.ContainerService/managedClusters",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=filter_str,
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
    
    def monitor_node_disk_percent(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor node disk usage percentage.

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

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Query metric with breakdown to get both aggregated value and metadata-level data
        group_by_metadata = config.get('group_by_metadata')
        # Determine effective metadata_aggregation: metric-level > root-level > aggregation fallback
        metadata_aggregation = config.get('metadata_aggregation') or config.get('aggregation')
        value, breakdown_dict = self.query_metric_with_breakdown(
            resource_id=self.resource_id,
            location=self.location,
            metric_name="node_disk_usage_percentage",
            metric_namespace="Microsoft.ContainerService/managedClusters",
            timespan=timespan,
            aggregation=config['aggregation'],
            granularity=granularity,
            filter_str=filter_str,
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

