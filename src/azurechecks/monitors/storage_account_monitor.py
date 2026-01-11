#!/usr/bin/env python3
"""
Storage Account Monitor Module

Monitors Azure Storage Account metrics including capacity and transactions.
Supports both account-level and service-level (Blob, Table, Queue, File) metrics.
"""

import re
import sys
import time
from datetime import timedelta
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List, Callable

from azure.monitor.querymetrics import MetricsClient

from .base_monitor import BaseMonitor
from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from exceptions import UnsupportedMetricTypeError
from utils import MonitorUtils

# ============================================================================
# Storage Account Metric Type Enum
# ============================================================================

class StorageAccountMetricType(Enum):
    """Enumeration of supported Storage Account metric types."""
    CAPACITY = "capacity"
    TRANSACTIONS = "transactions"

# ============================================================================
# StorageAccountMonitor Class
# ============================================================================

class StorageAccountMonitor(BaseMonitor):
    """
    Monitor for Azure Storage Account metrics.

    Supports capacity and transaction monitoring at both account-level
    and service-level (Blob, Table, Queue, File) scopes.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Storage Account Monitor from configuration dictionary.

        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - Additional resource-specific fields
        """
        # Initialize base class
        super().__init__()
        
        # Extract resource_id from config or build it
        self.resource_id = self.build_resource_id(config)

        # Extract location (required for Storage Account)
        self.location = config.get('location')
        if not self.location:
            raise ValueError("Missing 'location' in configuration (required for Storage Account)")

    def monitor(self, config: Dict[str, Any], debug: bool = False) -> MetricResult:
        """
        Main monitoring orchestrator - executes all enabled metrics sequentially.

        Args:
            config: Full configuration dictionary
            debug: Whether to print execution times for each metric

        Returns:
            Single MetricResult instance
        """
        # Extract metrics configuration
        metrics_config = config.get('metrics', {})

        # Extract common configuration
        common_config = {
            'time_range': config.get('time_range', 'PT1H'),
            'aggregation': config.get('aggregation', 'average'),
            'metadata_aggregation': config.get('metadata_aggregation'),
            'filter_metadata_values': config.get('filter_metadata_values'),
            'service_name': config.get('service_name', 'Storage Account'),
            'group_by_metadata': config.get('group_by_metadata')
        }

        # Get metric methods map
        metric_methods = self._get_metric_methods()

        # Collect all metrics and problematic metadata
        all_metrics = []
        all_problematic_metadata = []
        service_name = common_config.get('service_name', 'Storage Account')

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
                metric_type = StorageAccountMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in StorageAccountMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )

            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in StorageAccountMetricType]
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


    def query_metric_with_breakdown(
        self,
        metric_name: str,
        timespan: timedelta,
        aggregation: str,
        granularity: timedelta,
        scope: str,
        filter_str: Optional[str] = None,
        metadata_key: Optional[str] = None,
        metadata_aggregation: Optional[str] = None,
        debug: bool = False
    ) -> Tuple[Optional[float], Dict[str, float]]:
        """
        Query Azure Monitor metrics with optional filtering and metadata breakdown.
        
        This is a wrapper around the base class method that handles storage-specific
        requirements:
        - Resource ID modification for service-level namespaces (blobServices, tableServices)
        - Granularity capping (1 hour default, 1 day for Transactions metric)

        Args:
            metric_name: Azure metric name (e.g., 'UsedCapacity', 'Transactions')
            timespan: Time span as timedelta
            aggregation: Aggregation type ('sum', 'average', 'count', 'min', 'max')
            granularity: Time granularity as timedelta
            namespace: Azure Monitor metric namespace
            filter_str: Optional filter string for metric query
            metadata_key: Optional metadata key to extract for breakdown (e.g., 'ApiName', 'OperationName')

        Returns:
            Tuple of (aggregated_value, breakdown_dict)
        """
        
        # Get namespace for scope
        namespace = self.get_namespace_for_scope(scope)
        # Handle storage-specific resource ID modification for service-level namespaces
        resource_id = self.resource_id
        if scope.lower() == 'blob':
            resource_id = self.resource_id + '/blobServices/default'
        elif scope.lower() == 'table':
            resource_id = self.resource_id + '/tableServices/default'
        
        # Handle storage-specific granularity capping
        # Default: cap at 1 hour, but for Transactions metric cap at 1 day
        if metric_name == 'Transactions':
            capped_granularity = MonitorUtils.cap_granularity(granularity, timedelta(days=1))
        else:
            capped_granularity = MonitorUtils.cap_granularity(granularity, timedelta(hours=1))
        
        # Use base class method for the actual query
        return super().query_metric_with_breakdown(
            resource_id=resource_id,
            location=self.location,
            metric_name=metric_name,
            metric_namespace=namespace,
            timespan=timespan,
            aggregation=aggregation,
            granularity=capped_granularity,
            filter_str=filter_str,
            metadata_key=metadata_key,
            metadata_aggregation=metadata_aggregation,
            debug=debug
        )

    def _get_metric_methods(self) -> Dict[StorageAccountMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            StorageAccountMetricType.CAPACITY: self.monitor_capacity,
            StorageAccountMetricType.TRANSACTIONS: self.monitor_transactions
        }

    def _build_metadata_filter(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Build Azure Monitor filter string from metadata filtering configuration.
        
        Uses filter_metadata_values (list of values) and group_by_metadata (metadata key)
        to build a filter string.
        
        Args:
            config: Configuration dictionary containing:
                - filter_metadata_values: Optional list of metadata values to filter by
                - group_by_metadata: Optional metadata key (e.g., 'ApiName', 'OperationName', 'Tier')
        
        Returns:
            Filter string for Azure Monitor query, or None if no filtering needed
        """
        filter_values = config.get('filter_metadata_values')
        if not filter_values:
            return None
        
        metadata_key = config.get('group_by_metadata')
        if not metadata_key:
            return None
        
        return " or ".join(f"{metadata_key} eq '{value}'" for value in filter_values)

    def monitor_capacity(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor storage account capacity.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Extract configuration
        time_range = config.get('time_range', 'PT1H')
        aggregation = config.get('aggregation', 'average')
        scope = config.get('scope', 'account')
        warn_threshold = config.get('warn_threshold')
        crit_threshold = config.get('crit_threshold')
        min_value = config.get('min', 0)
        max_value = config.get('max')
        group_by_metadata = config.get('group_by_metadata')

        # Convert duration to timedelta
        granularity = MonitorUtils.iso8601_to_timedelta(time_range)
        timespan = granularity  # Use granularity as timespan

        capacity_metric_name = self.get_capacity_metric_name_for_scope(scope)

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Query metric with breakdown
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
            metric_name=capacity_metric_name,
            timespan=timespan,
            aggregation=aggregation,
            granularity=granularity,
            scope=scope,
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
            value=value,
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_value=min_value,
            max_value=max_value,
            unit=''
        )

        # Extract problematic metadata if breakdown is available
        problematic_metadata = None
        if group_by_metadata and breakdown_dict:
            problematic_metadata = self._extract_problems(
                breakdown_dict=breakdown_dict,
                metadata_key=group_by_metadata,
                warn_threshold=warn_threshold,
                crit_threshold=crit_threshold
            )
            # Return None if empty list
            if not problematic_metadata:
                problematic_metadata = None

        return (metric, problematic_metadata)

    def monitor_transactions(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor storage account transactions.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        # Extract configuration
        time_range = config.get('time_range', 'PT1H')
        aggregation = config.get('aggregation', 'sum')
        scope = config.get('scope', 'account')
        warn_threshold = config.get('warn_threshold')
        crit_threshold = config.get('crit_threshold')
        min_value = config.get('min', 0)
        max_value = config.get('max')
        group_by_metadata = config.get('group_by_metadata')

        # Convert timespan to timedelta
        granularity = MonitorUtils.iso8601_to_timedelta(time_range)
        timespan = granularity

        # Cap granularity for Transactions metric at 1 day (before calling query_metric_with_breakdown)
        # This ensures the capped granularity is used even when the method is patched in tests
        capped_granularity = MonitorUtils.cap_granularity(granularity, timedelta(days=1))

        # Build filter from metadata filtering configuration
        filter_str = self._build_metadata_filter(config)

        # Query metric with breakdown
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
            metric_name='Transactions',
            timespan=timespan,
            aggregation=aggregation,
            granularity=capped_granularity,
            scope=scope,
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
            value=value,
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_value=min_value,
            max_value=max_value,
            unit=''
        )

        # Extract problematic metadata if breakdown is available
        problematic_metadata = None
        if group_by_metadata and breakdown_dict:
            problematic_metadata = self._extract_problems(
                breakdown_dict=breakdown_dict,
                metadata_key=group_by_metadata,
                warn_threshold=warn_threshold,
                crit_threshold=crit_threshold
            )
            # Return None if empty list
            if not problematic_metadata:
                problematic_metadata = None

        return (metric, problematic_metadata)

    def get_namespace_for_scope(self, scope: str) -> str:
        """
        Get Azure Monitor metric namespace based on scope parameter.

        Args:
            scope: Scope parameter from config ('account', 'Blob', 'Table', 'Queue', 'File')

        Returns:
            Azure Monitor metric namespace string

        Raises:
            ValueError: If scope is invalid
        """
        if scope.lower() == 'account':
            return 'Microsoft.Storage/storageAccounts'

        service_map = {
            'blob': 'Microsoft.Storage/storageAccounts/blobServices',
            'table': 'Microsoft.Storage/storageAccounts/tableServices',
            'queue': 'Microsoft.Storage/storageAccounts/queueServices',
            'file': 'Microsoft.Storage/storageAccounts/fileServices'
        }

        namespace = service_map.get(scope.lower())
        if not namespace:
            raise ValueError(f"Invalid scope: {scope}. Must be one of: account, Blob, Table, Queue, File")

        return namespace

    def get_capacity_metric_name_for_scope(self, scope: str) -> str:
        """
        Get Azure Monitor metric name based on scope parameter.

        Args:
            scope: Scope parameter from config ('account', 'Blob', 'Table', 'Queue', 'File')

        Returns:
            Azure Monitor metric name string

        Raises:
            ValueError: If scope is invalid
        """
        if scope.lower() == 'account':
            return 'UsedCapacity'

        service_map = {
            'blob': 'BlobCapacity',
            'table': 'TableCapacity',
            'queue': 'QueueCapacity',
            'file': 'FileCapacity'
        }

        namespace = service_map.get(scope.lower())
        if not namespace:
            raise ValueError(f"Invalid scope: {scope}. Must be one of: account, Blob, Table, Queue, File")

        return namespace