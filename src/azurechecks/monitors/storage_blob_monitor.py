#!/usr/bin/env python3
"""
Storage Blob Monitor Module

Monitors Azure Blob Storage file operations:
- File existence checks
- File modification date checks
"""

import re
import sys
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List, Callable

from azurechecks.azure_auth import get_blob_service_client
from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from .base_monitor import BaseMonitor  # For build_resource_id static method
from exceptions import UnsupportedMetricTypeError

# ============================================================================
# Storage Blob Metric Type Enum
# ============================================================================

class StorageBlobMetricType(Enum):
    """Enumeration of supported Storage Blob metric types."""
    FILE_EXISTENCE = "file_existence"
    FILE_MODIFICATION = "file_modification"

# ============================================================================
# StorageBlobMonitor Class
# ============================================================================

class StorageBlobMonitor:
    """
    Monitor for Azure Blob Storage file operations.

    Supports file existence checks and file modification checks.
    
    Note: This monitor does not inherit from BaseMonitor because it uses
    azure-storage-blob SDK instead of azure-monitor-querymetrics SDK.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Storage Blob Monitor from configuration dictionary.

        Args:
            config: Full configuration dictionary containing:
                - resource_id: str (or will be built from subscription_id, resource_group, resource_name)
                - container_name: str (required for file operations)
        """
        # Build resource_id using static method from BaseMonitor
        self.resource_id = BaseMonitor.build_resource_id(config)
        
        # Extract container_name (required for blob operations)
        self.container_name = config.get('container_name')
        
        # Parse resource ID to extract components for blob service client
        self.storage_account_name = config.get('resource_name')

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
            'metadata_aggregation': config.get('metadata_aggregation'),  # Not used for blob, but included for consistency
            'service_name': config.get('service_name', 'Blob Storage'),
            'group_by_metadata': config.get('group_by_metadata')  # Not used for blob, but included for consistency
        }

        # Get metric methods map
        metric_methods = self._get_metric_methods()

        # Collect all metrics and problematic metadata
        all_metrics = []
        all_problems = []
        service_name = common_config.get('service_name', 'Blob Storage')
        
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
                metric_type = StorageBlobMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in StorageBlobMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )

            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in StorageBlobMetricType]
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
    
    def _get_metric_methods(self) -> Dict[StorageBlobMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            StorageBlobMetricType.FILE_EXISTENCE: self.monitor_file_existence,
            StorageBlobMetricType.FILE_MODIFICATION: self.monitor_file_modification
        }

    def monitor_file_existence(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor file existence in blob container.

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        files = config.get('files', [])

        # Validate container_name
        if not self.container_name:
            raise ValueError("container_name is required for file existence checks")

        # Get BlobServiceClient
        blob_service_client = get_blob_service_client(self.storage_account_name)
        container_client = blob_service_client.get_container_client(self.container_name)

        # Track file existence status
        existing_count = 0
        total_files = len(files)
        problematic_files = []

        for file_path in files:
            blob_client = container_client.get_blob_client(file_path)

            try:
                # Check if file exists
                exists = blob_client.exists()
                
                if exists:
                    existing_count += 1
                else:
                    # File is missing - create problem with message
                    problematic_files.append(MetricProblem(
                        problem_name=file_path,
                        problem_value=None,
                        metadata_key="File",
                        problem_message="missing"
                    ))

            except Exception as e:
                # Error checking file - treat as missing with error message
                problematic_files.append(MetricProblem(
                    problem_name=file_path,
                    problem_value=None,
                    metadata_key="File",
                    problem_message=f"error checking file: {str(e)}"
                ))

        # Create single metric: count of missing files (0 = all exist, >0 = some missing)
        # Value is 0 if all exist, increases as files are missing
        missing_files_count = total_files - existing_count
        
        metric = Metric(
            name=metric_name,
            value=missing_files_count,
            warn_threshold=None,
            crit_threshold=1,
            min_value=None,
            max_value=None,
            unit=''
        )

        # Return problematic files if any
        problematic_metadata = problematic_files if problematic_files else None

        return (metric, problematic_metadata)

    def monitor_file_modification(self, config: Dict[str, Any], metric_name: str, debug: bool = False) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor file modification times (fresheness).

        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
            debug: Whether to print debug information

        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        files = config.get('files', [])
        max_hours = config.get('max_hours_since_modification', 24)
        exceeded_status_str = config.get('exceeded_status', 'CRIT')

        # Validate container_name
        if not self.container_name:
            raise ValueError("container_name is required for file modification checks")

        # Get BlobServiceClient
        blob_service_client = get_blob_service_client(self.storage_account_name)
        container_client = blob_service_client.get_container_client(self.container_name)

        # Track file modification times
        hours_since_list = []
        problematic_files = []

        for file_path in files:
            blob_client = container_client.get_blob_client(file_path)

            try:
                # Check existence first
                exists = blob_client.exists()

                if not exists:
                    # File doesn't exist - create problem with message
                    problematic_files.append(MetricProblem(
                        problem_name=file_path,
                        problem_value=None,
                        metadata_key="File",
                        problem_message="missing"
                    ))
                    continue

                # Get blob properties
                properties = blob_client.get_blob_properties()
                last_modified = properties.last_modified

                # Calculate hours since modification
                now = datetime.now(timezone.utc)
                if last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                hours_since = (now - last_modified).total_seconds() / 3600
                hours_since_list.append(hours_since)

                # Check if exceeds threshold
                if hours_since > max_hours:
                    # File exceeds freshness threshold - create problem with message
                    problematic_files.append(MetricProblem(
                        problem_name=file_path,
                        problem_value=None,
                        metadata_key="File",
                        problem_message="out of date"
                    ))

            except Exception as e:
                # Error checking file - create problem with message
                problematic_files.append(MetricProblem(
                    problem_name=file_path,
                    problem_value=None,
                    metadata_key="File",
                    problem_message=f"error checking file: {str(e)}"
                ))

        # Create single metric: maximum hours since modification across all files
        # This represents the "staleness" of the oldest file
        if hours_since_list:
            max_hours_since = max(hours_since_list)
        else:
            # If no files were successfully checked (all missing or errors), set to a high value
            # to ensure CRIT status is triggered
            max_hours_since = max_hours + 1.0 if max_hours else float('inf')

        # Set thresholds based on exceeded_status
        warn_threshold = None
        crit_threshold = None
        if exceeded_status_str == 'WARN':
            warn_threshold = max_hours
        elif exceeded_status_str == 'CRIT':
            crit_threshold = max_hours
        else:
            # Default to CRIT if any problems exist
            # Set crit_threshold to max_hours to ensure CRIT when problems are detected
            if problematic_files:
                crit_threshold = max_hours

        metric = Metric(
            name=metric_name,
            value=max_hours_since,
            warn_threshold=warn_threshold,
            crit_threshold=crit_threshold,
            min_value=0.0,
            max_value=None,
            unit='h'
        )

        # Return problematic files if any
        problematic_metadata = problematic_files if problematic_files else None

        return (metric, problematic_metadata)