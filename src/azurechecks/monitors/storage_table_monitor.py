#!/usr/bin/env python3
"""
Storage Table Monitor Module

Monitors Azure Table Storage table operations:
- Table names listing
"""

import re
import sys
import time
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List, Callable

from .base_monitor import BaseMonitor  # For build_resource_id static method
from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from exceptions import UnsupportedMetricTypeError
from azurechecks.azure_auth import get_table_service_client

# ============================================================================
# Storage Table Metric Type Enum
# ============================================================================

class StorageTableMetricType(Enum):
    """Enumeration of supported Storage Table metric types."""
    TABLE_EXISTENCE = "table_existence"


# ============================================================================
# StorageTableMonitor Class
# ============================================================================

class StorageTableMonitor:
    """
    Monitor for Azure Table Storage table operations.

    Supports table listing.
    
    Note: This monitor does not inherit from BaseMonitor because it uses
    azure-storage-table SDK instead of azure-monitor-querymetrics SDK.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Storage Table Monitor from configuration dictionary.

        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
        """
        # Build resource_id using static method from BaseMonitor
        self.resource_id = BaseMonitor.build_resource_id(config)
        
        self.storage_account_name = config.get('resource_name')

        # Lazy-loaded clients
        self._table_service_client = None

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
            'metadata_aggregation': config.get('metadata_aggregation'),  # Not used for table, but included for consistency
            'service_name': config.get('service_name', 'Table Storage'),
            'group_by_metadata': config.get('group_by_metadata')  # Not used for table, but included for consistency
        }

        # Get metric methods map
        metric_methods = self._get_metric_methods()

        # Collect all metrics and problematic metadata
        all_metrics = []
        all_problems = []
        service_name = common_config.get('service_name', 'Table Storage')
        
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
                metric_type = StorageTableMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in StorageTableMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )

            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in StorageTableMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )

            # Merge common config with metric-specific config (metric config takes precedence)
            merged_config = {**common_config, **metric_config}
            metric_method = metric_methods[metric_type]

            # Time execution if requested
            start_time = time.time() if debug else None

            try:
                # Execute metric method - returns Tuple[Metric, Optional[List[MetricProblem]]]
                metric, problems = metric_method(merged_config, checkmk_metric_name, debug=debug)
                
                # Collect results
                all_metrics.append(metric)
                if problems:
                    all_problems.extend(problems)

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

        return MetricResult(
            service_name=service_name,
            metrics=all_metrics,
            problems=all_problems if all_problems else None
        )

    def monitor_table_existence(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Check table existence in the storage account.

        This is not a metrics query - it lists tables using TableServiceClient.
        If list_all is True, counts all tables. Otherwise, requires filtered_tables to be specified.
        Returns CRIT status if any table is missing.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        list_all = config.get('list_all', False)
        filtered_tables = config.get('filtered_tables', [])
        
        # If list_all is True, we don't need filtered_tables
        # Otherwise, validate that filtered_tables is provided and not empty
        if not list_all and not filtered_tables:
            raise ValueError("filtered_tables is required and must not be empty for table_existence metric when list_all is False")

        warn_threshold = config.get('warn_threshold')
        min_value = config.get('min', 0.0)
        max_value = config.get('max')

        # Get TableServiceClient
        table_service = get_table_service_client(self.storage_account_name)

        # List all tables in the storage account
        all_tables = []
        for table in table_service.list_tables():
            all_tables.append(table.name)

        # If list_all is True, just count tables (no missing tables to check)
        if list_all:
            missing_tables = []
            table_count = float(len(all_tables))
        else:
            # Find missing tables
            missing_tables = [t for t in filtered_tables if t not in all_tables]
            table_count = float(len(missing_tables))

        # Create MetricProblem instances for missing tables
        problematic_tables = []
        if missing_tables:
            for table_name in missing_tables:
                problematic_tables.append(MetricProblem(
                    problem_name=table_name,
                    problem_value=None,
                    metadata_key="Table",
                    problem_message="missing"
                ))

        # Metric value: 
        # - If list_all: count of all tables
        # - Otherwise: count of missing tables (0 = all exist, >0 = some missing)
        if list_all:
            # When list_all is True, value is the count of all tables
            metric_value = table_count
            # No thresholds for list_all mode (just reporting count)
            crit_threshold = config.get('crit_threshold', None)
        else:
            metric_value = table_count
            # Set crit_threshold to 1 so that if any table is missing (value >= 1), status is CRIT
            # This ensures CRIT status when any table is missing
            crit_threshold = 1.0

        # Table existence metric
        metric = Metric(
            name=metric_name,
            value=metric_value,
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_value=min_value,
            max_value=max_value,
            unit=''
        )

        # Return problematic tables if any are missing
        return (metric, problematic_tables if problematic_tables else None)
    
    def _get_metric_methods(self) -> Dict[StorageTableMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            StorageTableMetricType.TABLE_EXISTENCE: self.monitor_table_existence
        }
