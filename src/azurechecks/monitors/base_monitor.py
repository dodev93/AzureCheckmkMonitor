#!/usr/bin/env python3
"""
Base Monitor Module

Provides base class for all Azure resource monitoring modules with common functionality.
"""

import os
import sys
from datetime import timedelta
from typing import Dict, Any, List, Optional, Tuple

from azure.identity import ClientSecretCredential
from azure.monitor.querymetrics import MetricsClient, MetricAggregationType

from validation.config_validator import ConfigValidationError
from checkmk.checkmk_formatter import CheckmkFormatter, MetricProblem
from utils import MonitorUtils
from exceptions import AzureAuthError


class BaseMonitor:
    """Base class for all Azure resource monitoring modules."""
    
    def __init__(self):
        """Initialize base monitor with lazy-loaded clients and credentials."""
        # Lazy-loaded clients and credentials
        self._metrics_client = None
        self._credentials = None
    
    def get_credentials(self):
        """
        Get Azure Service Principal credentials from environment variables.
        
        Returns:
            ClientSecretCredential: Authenticated credential object
            
        Raises:
            AzureAuthError: If required environment variables are missing
        """
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        tenant_id = os.getenv('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            missing = []
            if not client_id:
                missing.append('AZURE_CLIENT_ID')
            if not client_secret:
                missing.append('AZURE_CLIENT_SECRET')
            if not tenant_id:
                missing.append('AZURE_TENANT_ID')
            raise AzureAuthError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        
        try:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            return credential
        except Exception as e:
            raise AzureAuthError(f"Failed to create credentials: {str(e)}")
    
    def _get_metrics_client(self, location: str):
        """
        Get or create metrics client (lazy initialization).
        
        Args:
            location: Azure resource location (e.g., 'westeurope', 'eastus')
            
        Returns:
            MetricsClient: Authenticated metrics client
        """
        if self._metrics_client is None:
            if self._credentials is None:
                self._credentials = self.get_credentials()
            
            endpoint = MonitorUtils.get_metrics_endpoint(location)
            
            self._metrics_client = MetricsClient(endpoint, self._credentials)
        return self._metrics_client
    
    def query_metric_with_breakdown(
        self,
        resource_id: str,
        location: str,
        metric_name: str,
        metric_namespace: str,
        timespan: timedelta,
        aggregation: str,
        granularity: timedelta,
        filter_str: Optional[str] = None,
        metadata_key: Optional[str] = None,
        metadata_aggregation: Optional[str] = None,
        debug: bool = False
    ) -> Tuple[Optional[float], Dict[str, float]]:
        """
        Query metrics using azure-monitor-querymetrics SDK and return both aggregated value and metadata breakdown.
        
        This is a generic method that can be used by all monitoring modules to query Azure Monitor metrics
        with optional metadata-based breakdown (e.g., by ApiId, OperationName, etc.).

        Args:
            resource_id: Full Azure resource ID
            location: Azure resource location (e.g., 'westeurope', 'eastus')
            metric_name: Azure metric name to query (e.g., 'Requests', 'Transactions')
            metric_namespace: Azure Monitor metric namespace (e.g., 'Microsoft.ApiManagement/service')
            timespan: Time span as timedelta
            aggregation: Aggregation type ('sum', 'average', 'count', 'min', 'max')
            granularity: Time granularity as timedelta
            filter_str: Optional filter string for Azure Monitor query
            metadata_key: Optional metadata key to extract for breakdown (e.g., 'ApiId', 'OperationName').
                         If None, no breakdown will be extracted.
            metadata_aggregation: Optional aggregation type for combining grouped metadata values.
                                If None, defaults to 'aggregation' parameter. Valid values: 'sum', 'average', 'count', 'min', 'max'.

        Returns:
            Tuple of (aggregated_value, breakdown_dict) where:
            - aggregated_value: Optional[float] - Aggregated metric value
            - breakdown_dict: Dict[str, float] - Dictionary mapping metadata values to metric values
                            (empty dict if metadata_key is None or no metadata found)
        """
        try:
            client = self._get_metrics_client(location)

            # Convert aggregation to MetricAggregationType enum
            aggregation_map = {
                'sum': MetricAggregationType.TOTAL,
                'average': MetricAggregationType.AVERAGE,
                'count': MetricAggregationType.COUNT,
                'min': MetricAggregationType.MINIMUM,
                'max': MetricAggregationType.MAXIMUM
            }
            azure_aggregation = aggregation_map.get(aggregation.lower(), MetricAggregationType.AVERAGE)

            # Cap granularity at PT1D (maximum supported by Azure Monitor)
            capped_granularity = MonitorUtils.cap_granularity(granularity, timedelta(days=1))

            # Query metrics using query_resources
            response = client.query_resources(
                resource_ids=[resource_id],
                metric_namespace=metric_namespace,
                metric_names=[metric_name],
                timespan=timespan,
                granularity=capped_granularity,
                aggregations=[azure_aggregation],
                filter=filter_str
            )

            if debug:
                print(f"query metric filter: {filter_str}")

                import json

                def to_serializable(obj):
                    """
                    Recursively convert nested fields to their values for JSON serialization.
                    """
                    if isinstance(obj, dict):
                        return {k: to_serializable(v) for k, v in obj.items()}
                    elif hasattr(obj, "__dict__"):
                        # Convert objects with __dict__ (custom classes)
                        return to_serializable(obj.__dict__)
                    elif isinstance(obj, (list, tuple)):
                        return [to_serializable(item) for item in obj]
                    else:
                        return obj

                for item in response:
                    print(json.dumps(to_serializable(item), default=str, indent=2))

            aggregated_value = None
            breakdown_dict = {}
            has_metadata_breakdown = False
            
            # Extract value from response (response is an iterator)
            for metrics_query_result in response:
                if hasattr(metrics_query_result, 'metrics') and metrics_query_result.metrics:
                    for metric in metrics_query_result.metrics:
                        if hasattr(metric, 'timeseries') and metric.timeseries:
                            for series in metric.timeseries:
                                if hasattr(series, 'data') and series.data:
                                    data_points = series.data
                                    # Remove any data_point if all its fields are None
                                    filtered_data_points = []
                                    for point in data_points:
                                        fields = [v for k, v in vars(point).items() if not k.startswith("_")]
                                        if any(f is not None for f in fields):
                                            filtered_data_points.append(point)
                                    data_points = filtered_data_points
                                    # Extract value based on aggregation type
                                    value = None
                                    if aggregation.lower() == 'sum':
                                        total_sum = 0.0
                                        for point in data_points:
                                            if hasattr(point, 'total') and point.total is not None:
                                                total_sum += point.total
                                        # For sum aggregation: always return 0.0 (even if no data points)
                                        # This represents zero sum (0 requests, 0 transactions, etc.)
                                        value = total_sum
                                    elif aggregation.lower() == 'count':
                                        count_sum = 0.0
                                        for point in data_points:
                                            if hasattr(point, 'count') and point.count is not None:
                                                count_sum += point.count
                                        # For count aggregation: always return 0.0 (even if no data points)
                                        # This represents zero count (0 data points counted)
                                        value = count_sum
                                    elif aggregation.lower() == 'average':
                                        if data_points:
                                            latest_point = data_points[-1]
                                            if hasattr(latest_point, 'average') and latest_point.average is not None:
                                                value = latest_point.average
                                        # If no data points or average is None, value remains None
                                    elif aggregation.lower() == 'min':
                                        min_value = None
                                        for point in data_points:
                                            if hasattr(point, 'minimum') and point.minimum is not None:
                                                if min_value is None or point.minimum < min_value:
                                                    min_value = point.minimum
                                        value = min_value
                                    elif aggregation.lower() == 'max':
                                        max_value = None
                                        for point in data_points:
                                            if hasattr(point, 'maximum') and point.maximum is not None:
                                                if max_value is None or point.maximum > max_value:
                                                    max_value = point.maximum
                                        value = max_value
                                    else:
                                        if data_points:
                                            latest_point = data_points[-1]
                                            if hasattr(latest_point, 'total') and latest_point.total is not None:
                                                value = latest_point.total
                                            elif hasattr(latest_point, 'average') and latest_point.average is not None:
                                                value = latest_point.average
                                        # If no data points, value remains None
                                    
                                    # Extract metadata value if metadata_key is provided
                                    metadata_value = None
                                    if metadata_key and hasattr(series, 'metadata_values') and series.metadata_values:
                                        if isinstance(series.metadata_values, dict):
                                            metadata_value = series.metadata_values.get(metadata_key)
                                        elif hasattr(series.metadata_values, 'get'):
                                            metadata_value = series.metadata_values.get(metadata_key)
                                        elif hasattr(series.metadata_values, '__getitem__'):
                                            try:
                                                metadata_value = series.metadata_values[metadata_key]
                                            except (KeyError, TypeError):
                                                pass
                                    

                                    if debug:
                                        print(f"metadata_value: {metadata_value}")
                                        print(f"metadata_key: {metadata_key}")
                                    
                                    if value is not None:
                                        # If we have metadata breakdown, store it
                                        if metadata_value:
                                            has_metadata_breakdown = True
                                            if aggregation.lower() == 'sum':
                                                breakdown_dict[metadata_value] = breakdown_dict.get(metadata_value, 0) + (value or 0)
                                            else:
                                                # For non-sum aggregations, use the latest value if multiple series exist
                                                # This handles cases where the same metadata value appears in multiple series
                                                if metadata_value not in breakdown_dict:
                                                    breakdown_dict[metadata_value] = value
                                                elif aggregation.lower() == 'max':
                                                    breakdown_dict[metadata_value] = max(breakdown_dict[metadata_value], value)
                                                elif aggregation.lower() == 'min':
                                                    breakdown_dict[metadata_value] = min(breakdown_dict[metadata_value], value)
                                        else:
                                            # No metadata, aggregate directly
                                            if aggregation.lower() == 'sum':
                                                if aggregated_value is None:
                                                    aggregated_value = 0.0
                                                aggregated_value += (value or 0)
                                            else:
                                                if aggregated_value is None:
                                                    aggregated_value = value
            
            # Calculate aggregated value from breakdown_dict if we have metadata breakdown
            if has_metadata_breakdown and breakdown_dict:
                # Default to aggregation parameter if metadata_aggregation is not specified
                effective_metadata_aggregation = (metadata_aggregation or aggregation).lower()
                
                if effective_metadata_aggregation == 'sum':
                    aggregated_value = sum(breakdown_dict.values())
                elif effective_metadata_aggregation == 'count':
                    aggregated_value = sum(breakdown_dict.values())
                elif effective_metadata_aggregation == 'average':
                    aggregated_value = sum(breakdown_dict.values()) / len(breakdown_dict)
                elif effective_metadata_aggregation == 'max':
                    aggregated_value = max(breakdown_dict.values())
                elif effective_metadata_aggregation == 'min':
                    aggregated_value = min(breakdown_dict.values())
                else:
                    # Fallback to sum for unknown aggregation types
                    aggregated_value = sum(breakdown_dict.values())
            
            # Zero value handling for sum and count aggregations:
            # - If aggregated_value is None and aggregation is 'sum' or 'count', return 0.0
            # - This ensures zero values are properly represented in metrics (e.g., 0 requests, 0 transactions)
            # - For other aggregation types (average, min, max), None is returned when no data points exist
            # - This behavior is consistent: sum/count of zero data points = 0.0, while average/min/max of no data = None
            if aggregated_value is None and aggregation.lower() in ('sum', 'count'):
                aggregated_value = 0.0
            
            return aggregated_value, breakdown_dict
        except Exception as e:
            # Re-raise exception instead of silently returning None
            # This allows calling code to handle errors appropriately
            # print(f"Exception in query_metric_with_breakdown: {e}", file=sys.stderr)
            raise
    
    @staticmethod
    def build_resource_id(config: Dict[str, Any]) -> str:
        """
        Build Azure resource ID from configuration.
        
        This method always builds the resource_id from component fields (subscription_id,
        resource_group, resource_name). It does not use resource_id from config if provided.
        
        Args:
            config: Configuration dictionary containing:
                - resource_type: str (required)
                - subscription_id: str (required)
                - resource_group: str (required)
                - resource_name: str (required)
        
        Returns:
            Full Azure resource ID string
        
        Raises:
            ConfigValidationError: If resource_type is unsupported or required fields are missing
        """
        resource_type = config.get('resource_type')
        subscription_id = config.get('subscription_id')
        resource_group = config.get('resource_group')
        resource_name = config.get('resource_name')
        
        if not resource_type:
            raise ConfigValidationError("Missing 'resource_type' in configuration")
        if not subscription_id:
            raise ConfigValidationError("Missing 'subscription_id' in configuration")
        if not resource_group:
            raise ConfigValidationError("Missing 'resource_group' in configuration")
        if not resource_name:
            raise ConfigValidationError("Missing 'resource_name' in configuration")
        
        resource_id_templates = {
            'apim': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.ApiManagement/service/{resource_name}',
            'storage_account': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{resource_name}',
            'storage_blob': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{resource_name}',
            'storage_table': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{resource_name}',
            'container_apps': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.App/containerApps/{resource_name}',
            'vmss': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachineScaleSets/{resource_name}',
            'servicebus': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.ServiceBus/namespaces/{resource_name}',
            'aks': '/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.ContainerService/managedClusters/{resource_name}',
            'secrets': None  # Secrets don't use resource_id format
        }
        
        if resource_type not in resource_id_templates:
            raise ConfigValidationError(f"Unsupported resource type: {resource_type}")
        
        template = resource_id_templates[resource_type]
        if template is None:
            raise ConfigValidationError(f"Resource type '{resource_type}' does not use resource_id format")
        
        return template.format(
            subscription_id=subscription_id,
            resource_group=resource_group,
            resource_name=resource_name
        )

    def _extract_problems(
        self,
        breakdown_dict: Dict[str, float],
        metadata_key: str,
        warn_threshold: Optional[float],
        crit_threshold: Optional[float]
    ) -> List[MetricProblem]:
        """
        Group metrics by metadata field and identify problematic values.
        
        This is a common method used by all monitoring modules to identify
        problematic metadata values (e.g., ApiId, OperationName) that exceed thresholds.
        
        Args:
            breakdown_dict: Dictionary mapping metadata values to metric values
            metadata_key: The metadata key used for grouping (e.g., 'ApiId', 'OperationName')
            warn_threshold: Warning threshold
            crit_threshold: Critical threshold
        
        Returns:
            List of MetricProblem instances for values that exceed thresholds
        """
        problems_values = []
        
        if not breakdown_dict:
            return problems_values
        
        # Check each metadata value in the breakdown
        for metadata_value, metric_value in breakdown_dict.items():
            # Evaluate if this value exceeds thresholds
            status = CheckmkFormatter.evaluate_status(metric_value, warn_threshold, crit_threshold)
            
            # If status > 0, it's problematic (WARN or CRIT)
            if status > 0:
                problems_values.append(MetricProblem(
                    problem_name=metadata_value,
                    problem_value=metric_value,
                    metadata_key=metadata_key
                ))
        
        return problems_values

