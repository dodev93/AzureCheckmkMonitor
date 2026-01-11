# Product Requirements Document: Monitoring Module Architecture

## 1. Overview

This document defines the requirements and architecture for all Azure resource monitoring modules in the AzureCheckmkMonitor project. All monitoring modules must follow a consistent pattern to ensure maintainability, testability, and extensibility.

## 2. Objectives

- Provide a unified architecture for all monitoring modules
- Ensure consistent error handling and configuration management
- Optimize Azure SDK calls to minimize API usage
- Support metadata-based grouping for detailed problem identification
- Enable per-metric execution timing for performance analysis
- Use type-safe enums instead of magic strings
- Provide clear error messages for unsupported configurations

## 3. Architecture Components

### 3.1 Base Monitor Class

All monitoring modules must inherit from a common base class that provides shared functionality.

#### 3.1.1 Location and Structure

- **File**: `src/azurechecks/monitors/base_monitor.py`
- **Class Name**: `BaseMonitor`
- **Type**: Abstract base class (can use ABC or regular class)
- **Exception Class**: `AzureAuthError` - Custom exception for authentication errors (defined in same file)

#### 3.1.2 Required Methods

##### `__init__(self)`

Constructor that initializes base monitor with lazy-loaded clients and credentials.

**Implementation:**
- Initializes `self._metrics_client = None`
- Initializes `self._credentials = None`
- These are lazy-loaded and created on first use

##### `get_credentials(self) -> ClientSecretCredential`

Get Azure Service Principal credentials from environment variables.

**Returns:**
- `ClientSecretCredential`: Authenticated credential object

**Raises:**
- `AzureAuthError`: If required environment variables are missing

**Implementation:**
- Reads `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` from environment
- Creates and returns `ClientSecretCredential` instance
- Raises `AzureAuthError` with descriptive message if variables are missing

##### `_get_metrics_client(self, location: str) -> MetricsClient`

Get or create metrics client (lazy initialization).

**Parameters:**
- `location: str` - Azure resource location (e.g., 'westeurope', 'eastus')

**Returns:**
- `MetricsClient`: Authenticated metrics client

**Implementation:**
- Uses lazy initialization - creates client only once
- If `self._credentials` is None, calls `self.get_credentials()`
- Uses `MonitorUtils.get_metrics_endpoint(location)` to get endpoint
- Creates `MetricsClient(endpoint, self._credentials)`
- Returns cached client on subsequent calls

##### `build_resource_id(config: Dict[str, Any]) -> str`

Static method that builds Azure resource ID from configuration.

**Parameters:**
- `config`: Configuration dictionary containing:
  - `resource_type: str` - Resource type (e.g., 'apim', 'storage_account')
  - `subscription_id: str` - Azure subscription ID
  - `resource_group: str` - Resource group name
  - `resource_name: str` - Resource name

**Returns:**
- Full Azure resource ID string (e.g., `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ApiManagement/service/{name}`)

**Implementation:**
- Should delegate to `config_validator.build_resource_id()` or implement similar logic
- Must validate that all required fields are present
- Must raise `ConfigValidationError` if resource_type is unsupported

##### `_extract_problems(self, breakdown_dict: Dict[str, float], metadata_key: str, warn_threshold: Optional[float], crit_threshold: Optional[float]) -> List[MetricProblem]`

Group metrics by metadata field and identify problematic values.

**Parameters:**
- `breakdown_dict`: Dictionary mapping metadata values to metric values
  - Example: `{'api-id-1': 150.0, 'api-id-2': 50.0}`
- `metadata_key`: The metadata key used for grouping (e.g., 'ApiId', 'OperationName')
- `warn_threshold`: Warning threshold (None if not set)
- `crit_threshold`: Critical threshold (None if not set)

**Returns:**
- List of `MetricProblem` instances for values that exceed thresholds

**Logic:**
1. If `breakdown_dict` is empty, return an empty list
2. For each `(metadata_value, metric_value)` in `breakdown_dict.items()`:
   - Use `CheckmkFormatter.evaluate_status(metric_value, warn_threshold, crit_threshold)` to calculate the status
   - If status > 0 (i.e., WARN or CRIT), create a `MetricProblem` with:
     - `problem_name = metadata_value`
     - `problem_value = metric_value`
     - `metadata_key = metadata_key`
3. Return the list of problematic values

**Note:** This method only identifies problematic values, not their status in the overall metric result.
    
##### (Additional required methods implemented in base_monitor.py)

###### `query_metric_with_breakdown(...)`

Queries metrics using the azure-monitor-querymetrics SDK and returns both the aggregated value and breakdown by metadata, if requested.

**Parameters:**  
- `resource_id`, `location`, `metric_name`, `metric_namespace`, `timespan`, `aggregation`, `granularity`, `filter_str`, `metadata_key`, `metadata_aggregation`, `debug`

**Returns:**  
- Tuple of (aggregated_value, breakdown_dict)

**Implementation:**  
- Uses MetricsClient to fetch metric data from Azure
- Handles sum, count, average, min, max aggregations
- Groups results by metadata_key if provided
- When metadata breakdown exists, the aggregated value is calculated using `metadata_aggregation` parameter:
  - **Precedence order**: If `metadata_aggregation` is specified, it uses that aggregation type. If `metadata_aggregation` is None, it defaults to the `aggregation` parameter value.
  - Valid values: 'sum', 'average', 'count', 'min', 'max' (same as aggregation types)
  - For 'sum' and 'count': sums all breakdown_dict values
  - For 'average': calculates average of breakdown_dict values (sum of all values divided by count)
  - For 'min': finds minimum value in breakdown_dict
  - For 'max': finds maximum value in breakdown_dict
- **Zero value handling**: 
  - For 'sum' and 'count' aggregations: Always returns 0.0 (never None), even when there are no data points. This represents zero sum/count (e.g., 0 requests, 0 transactions) and ensures zero values are properly represented in metrics.
  - For 'average', 'min', and 'max' aggregations: Returns None when no data points exist (cannot calculate average/min/max of no data).
  - This behavior is consistent: sum/count of zero or no data points = 0.0, while average/min/max of no data = None.
- Returns both the aggregated value and a dictionary of breakdown results

###### (Other shared error handling and helper methods may be added to BaseMonitor for use by derived modules.)

### 3.2 Module-Specific Monitor Classes

**Important:** Modules that use `azure-monitor-querymetrics` SDK must inherit from `BaseMonitor`. Modules that use other Azure SDKs (e.g., Microsoft Graph API, Azure Storage SDK) do not need to inherit from `BaseMonitor` and can implement their own authentication and client management.

**Examples:**
- **Must inherit from BaseMonitor:** APIM, Storage Account, Container Apps, VMSS, Service Bus, AKS (all use azure-monitor-querymetrics)
- **Do not inherit from BaseMonitor:** Secrets Monitor (uses Microsoft Graph API), Storage Blob Monitor (uses azure-storage-blob SDK), Storage Table Monitor (uses azure-storage-table SDK)

Each resource type that uses `azure-monitor-querymetrics` has its own monitor class that inherits from `BaseMonitor`.

#### 3.2.1 Constructor Requirements

**For modules inheriting from BaseMonitor:**

**Signature:**
```python
def __init__(self, config: Dict[str, Any]):
```

**Requirements:**
1. **Must call `super().__init__()`** - This initializes `_metrics_client` and `_credentials` in base class
2. Build `resource_id`:
   ```python
   self.resource_id = self.build_resource_id(config)
   ```
3. Extract resource-specific required fields (e.g., `location`, `container_name`)

**For modules NOT inheriting from BaseMonitor:**

**Signature:**
```python
def __init__(self, config: Dict[str, Any]):
```

**Requirements:**
1. **Do NOT call `super().__init__()`** - These modules implement their own authentication and client management
2. If resource ID is needed, use the static method:
   ```python
   from .base_monitor import BaseMonitor  # For build_resource_id static method
   
   self.resource_id = BaseMonitor.build_resource_id(config)
   ```
3. Extract resource-specific required fields (e.g., `container_name` for Storage Blob)

#### 3.2.2 Required Class Attributes

##### Metric Type Enum

Each module must define a per-module enum:

```python
from enum import Enum

class APIMetricType(Enum):
    """Enumeration of supported APIM metric types."""
    REQUEST_COUNT = "request_count"
    REQUESTS_2XX = "requests_2xx"
    REQUESTS_4XX = "requests_4xx"
    REQUESTS_5XX = "requests_5xx"
    REQUESTS_BY_CODES = "requests_by_codes"
```

**Requirements:**
- Enum name should follow pattern: `{ResourceType}MetricType`
- Enum values must be strings matching configuration file values
- All supported metric types must be included

##### Metric Methods Map

Each class must provide a method that returns a dictionary mapping enum values to method references:

```python
def _get_metric_methods(self) -> Dict[APIMetricType, Callable]:
    """Get mapping of metric types to method references."""
    return {
        APIMetricType.REQUEST_COUNT: self.monitor_request_count,
        APIMetricType.REQUESTS_2XX: self.monitor_requests_2xx,
        # ... more mappings
    }
```

**Requirements:**
- Must return a dictionary
- Keys must be enum values (not strings)
- Values must be method references (callable objects)
- All metric types in the enum must have corresponding methods

### 3.3 Metric-Specific Methods

Each metric type has its own method that implements the monitoring logic.

#### 3.3.1 Method Signature

```python
def monitor_<metric_name>(
    self,
    config: Dict[str, Any],
    metric_name: str,
    debug: bool = False
) -> Tuple[Metric, Optional[List[MetricProblem]]]:
```

**Parameters:**
- `config`: Merged configuration dictionary (common config + metric-specific config)
- `metric_name`: Checkmk metric name (from config key)
- `debug`: Optional debug flag (default: False). When True, enables debug output for Azure SDK queries

**Returns:**
- Tuple of:
  - `Metric`: Single metric instance (always one metric, even with grouping)
  - `Optional[List[MetricProblem]]`: List of problematic metadata values, or None if no grouping or no problems

#### 3.3.2 Implementation Requirements

1. **Extract Configuration:**
   - Parse `time_range` using `MonitorUtils.iso8601_to_timedelta()`
   - Extract `aggregation`, thresholds, and other metric-specific config
   - Check for `group_by_metadata` field

2. **Build Filter Strings:**
   - Construct Azure Monitor filter strings if needed
   - Apply resource-specific filters (e.g., API IDs, operation names)

3. **Query Metrics (CRITICAL - One Call Only):**
   - Call core query method exactly once
   - Example: `value, breakdown_dict = self.query_metric_with_breakdown(...)`
   - Do not make multiple Azure SDK calls for the same metric
   - **Zero value handling**: 
     - For 'sum' and 'count' aggregations: If the query returns zero or no data points, the method returns 0.0 (not None). This ensures zero values are properly represented in metrics and can be evaluated against thresholds.
     - For 'average', 'min', and 'max' aggregations: If no data points exist, the method returns None (cannot calculate average/min/max of no data).

4. **Process Results:**
   - Extract aggregated value from query result
   - If `group_by_metadata` is specified:
     - Use `_extract_problems()` to identify problematic values
     - Pass `breakdown_dict`, `group_by_metadata` value, and thresholds
     - Store returned `List[MetricProblem]`
   - If no grouping or no problems, set problematic list to None

5. **Create Metric Instance:**
   - Create `Metric` instance with:
     - `name`: Checkmk metric name
     - `value`: Aggregated metric value
     - `warn_threshold`, `crit_threshold`: From config
     - `min_value`, `max_value`: From config (if provided)
     - `unit`: Appropriate unit string

6. **Return:**
   - Return tuple: `(Metric, Optional[List[MetricProblem]])`

### 3.4 Main Monitor Method

The `monitor()` method orchestrates execution of all enabled metrics.

#### 3.4.1 Method Signature

```python
def monitor(self, config: Dict[str, Any], debug: bool = False) -> MetricResult:
```

#### 3.4.2 Implementation Steps

1. **Extract Configuration:**
   ```python
   metrics_config = config.get('metrics', {})
   common_config = {
       'time_range': config.get('time_range'),
       'aggregation': config.get('aggregation'),
       'metadata_aggregation': config.get('metadata_aggregation'),
       'filter_metadata_values': config.get('filter_metadata_values'),
       'service_name': config.get('service_name'),
       'group_by_metadata': config.get('group_by_metadata'),
       # ... other common fields
   }
   ```

2. **Get Metric Methods Map:**
   ```python
   metric_methods = self._get_metric_methods()
   ```

3. **Initialize Collections:**
   ```python
   all_metrics = []
   all_problems = []
   ```

4. **Iterate Over Metrics:**
   ```python
   for checkmk_metric_name, metric_config in metrics_config.items():
       # Skip if disabled
       if not metric_config.get('enabled', False):
           continue
       
       # Get metric type
       metric_type_str = metric_config.get('type')
       if not metric_type_str:
           continue  # Skip metrics without type
       
       # Convert to enum
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
       
       # Merge configs
       merged_config = {**common_config, **metric_config}
       
       # Get method
       metric_method = metric_methods[metric_type]
       
       # Time execution if requested
       start_time = time.time() if debug else None
       
       try:
           # Execute metric method
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
   ```

5. **Return Result:**
   ```python
   return MetricResult(
       service_name=common_config.get('service_name'),
       metrics=all_metrics,
       problems=all_problems if all_problems else None
   )
   ```

## 4. Data Structures

### 4.1 MetricProblem Class

**Location:** `src/checkmk/checkmk_formatter.py`

**Definition:**
```python
@dataclass
class MetricProblem:
    """Represents a problematic metadata value that exceeds thresholds."""
    problem_name: str  # The metadata value (e.g., "api-id-1", "PutBlob")
    problem_value: Optional[float] = None  # The problematic metric value (None if problem_message is used)
    metadata_key: Optional[str] = None  # The metadata key used (e.g., "ApiId", "OperationName")
    problem_message: Optional[str] = None  # Human-readable problem message (used when problem_value is None)
```

**Usage:**
- Used to identify specific metadata values that exceed thresholds
- Included in `MetricResult.problems` field

### 4.2 MetricResult Class Structure

**Location:** `src/checkmk/checkmk_formatter.py`

**Fields:**
- `service_name: Optional[str]` - Service name for Checkmk output
- `metrics: List[Metric]` - List of Metric instances
- `problems: Optional[List[MetricProblem]]` - List of problematic metadata values that exceed thresholds
- `status: Union[int, str]` - Computed status (property, 0=OK, 1=WARN, 2=CRIT, 3=UNKNOWN, "P"=calculated by Checkmk)
- `message: str` - Computed human-readable message (property)

### 4.3 UnsupportedMetricTypeError Exception

**Location:** `src/exceptions.py`

**Definition:**
```python
class UnsupportedMetricTypeError(Exception):
    """Raised when a metric type is not supported by the monitoring module."""
    
    def __init__(self, metric_name: str, metric_type: str, supported_types: List[str]):
        self.metric_name = metric_name
        self.metric_type = metric_type
        self.supported_types = supported_types
        message = (
            f"Unsupported metric type '{metric_type}' for metric '{metric_name}'. "
            f"Supported types: {', '.join(supported_types)}"
        )
        super().__init__(message)
```

**Usage:**
- Raised in `monitor()` method when metric type is not found in metric methods map
- Provides clear error message with supported types

## 5. Configuration Structure

### 5.1 Top-Level Configuration

```json
{
  "resource_type": "apim",
  "subscription_id": "<subscription-id>",
  "resource_group": "<resource-group>",
  "resource_name": "<resource-name>",
  "location": "<location>",
  "time_range": "PT1H",
  "aggregation": "sum",
  "service_name": "Azure APIM",
  "group_by_metadata": "ApiId",
  "filter_metadata_values": ["",""],
  "metadata_aggregation": "sum",
  "metrics": {
    // Metric configurations
  }
}
```

**Top-Level Fields:**
- `resource_type`: Required - Resource type (e.g., "apim", "storage_account")
- `subscription_id`: Required - Azure subscription ID
- `resource_group`: Required - Resource group name
- `resource_name`: Required - Resource name
- `location`: Required for some resource types (e.g., "apim")
- `time_range`: Optional - ISO 8601 duration (e.g., "PT1H") - can be overridden per metric
- `aggregation`: Optional - Aggregation type ("sum", "average", "count", "min", "max") - can be overridden per metric
- `filter_metadata_values`: Optional - List of metadata values to filter by (e.g., ["api-id-1", "api-id-2"])
- `service_name`: Optional - Service name for Checkmk output
- `group_by_metadata`: Optional - Metadata key for grouping (e.g., "ApiId", "OperationName") - applies to all metrics unless overridden per metric

### 5.2 Metric Configuration

```json
{
  "apim_request_count": {
    "enabled": true,
    "type": "request_count",
    "group_by_metadata": "ApiId",
    "warn_threshold": 100,
    "crit_threshold": 500,
    "min": 0,
    "max": null,
    "time_range": "PT1H",
    "aggregation": "sum"
  }
}
```

**Fields:**
- `enabled`: Boolean indicating if metric is enabled
- `type`: String matching enum value (e.g., "request_count")
- `group_by_metadata`: Optional string specifying metadata key for grouping (e.g., "ApiId", "OperationName") - overrides root-level `group_by_metadata` if specified
- `warn_threshold`, `crit_threshold`: Optional numeric thresholds
- `min`, `max`: Optional min/max values
- Other fields may override common config (e.g., `time_range`, `aggregation`)

## 6. Integration with generic_check.py

### 6.1 Function Call Updates

The `route_to_monitor()` function in `src/azurechecks/generic_check.py` must be updated:

**Example:**
```python
def route_to_monitor(resource_type: str, config: dict, debug: bool = False):
    if resource_type == 'apim':
        am = apim_monitor.APIMMonitor(config)
        return am.monitor(config, debug=debug)
    elif resource_type == 'storage_account':
        sam = storage_account_monitor.StorageAccountMonitor(config)
        return sam.monitor(config, debug=debug)
```

### 6.2 Exception Handling in generic_check.py

The `src/azurechecks/generic_check.py` script handles all exceptions from monitoring modules:

- **All exceptions** from `monitor()` methods are caught in the `main()` function
- Exceptions result in:
  - Status 3 (UNKNOWN) output: `3 "<service_name>" <error_message>` where `<service_name>` is:
    - The `service_name` from configuration if available
    - `"Azure Monitor"` if service_name is not available (e.g., configuration loading failed)
  - Exit code 3
- Specific exception types are handled with generic error messages (exception details are NOT included in Checkmk output):
  - `ConfigValidationError`: Configuration validation errors - uses `"Azure Monitor"` as service_name (config not yet loaded)
  - `AzureAuthError`: Authentication errors - uses service_name from config if available
  - `ValueError`: General value errors - uses service_name from config if available
  - `Exception`: Catch-all for unexpected errors (includes `UnsupportedMetricTypeError`) - uses service_name from config if available
- **Exception Logging vs. Checkmk Output:**
  - **Exception details are logged** to log files via `ExceptionLogger.log_exception()` for troubleshooting
  - **Exception details are NOT printed** in Checkmk output to keep output clean and avoid exposing sensitive information
  - Checkmk output contains only generic error messages (e.g., "Configuration validation error", "Authentication error")
  - Full exception details, stack traces, and error messages are available in log files located in `logs/` directory
- Monitoring modules should **not** catch exceptions - let them propagate to `src/azurechecks/generic_check.py`

## 7. Performance Requirements

### 7.1 Azure SDK Call Optimization

- **CRITICAL**: Each metric configuration must result in exactly one Azure SDK call
- Do not make multiple calls for the same metric
- Cache query results within a metric method if needed
- Reuse breakdown_dict from single query for grouping logic

### 7.2 Execution Timing

- When `debug=True`, each metric execution must be timed individually
- Timing should include entire metric method execution (including Azure SDK call)
- Execution times printed to stderr in format: `Metric '<name>' execution time: <seconds>s`
- Timing should be accurate to millisecond precision (3 decimal places)

## 8. Error Handling Requirements

### 8.1 Unsupported Metric Types

- Must raise `UnsupportedMetricTypeError` when metric type is not supported
- Do not silently skip unsupported metrics
- Error message must include:
  - Metric name
  - Unsupported type
  - List of supported types

### 8.2 Metric Execution Errors

- **Exceptions should propagate** from the `monitor()` method to the caller (`generic_check.py`)
- Do not catch exceptions in metric execution - let them propagate naturally
- Print traceback to stderr when `debug=True` before re-raising (optional, for debugging)
- The `generic_check.py` script handles all exceptions and outputs status 3 (UNKNOWN) with generic error messages
- **Exception Logging:**
  - All exception details (including stack traces and error messages) are logged to files via `ExceptionLogger.log_exception()`
  - Exception details are NOT included in Checkmk output to keep output clean and secure
  - Log files are located in `logs/` directory, organized by service name
- **Exception**: `UnsupportedMetricTypeError` should still be raised (not caught) as it indicates a configuration error - it will be caught by the generic exception handler in `generic_check.py`

### 8.3 Configuration Errors

- Validate required fields in constructor
- Raise `ConfigValidationError` for missing required fields
- Provide clear error messages

## 9. Testing Requirements

### 9.1 Unit Tests

- Test base class methods (`__init__`, `get_credentials`, `_get_metrics_client`, `build_resource_id`, `_extract_problems`)
- Test credential initialization and lazy loading
- Test metrics client initialization and caching
- Test metric type enum conversion
- Test unsupported metric type exception
- Test metadata grouping logic
- Mock Azure SDK calls

### 9.2 Integration Tests

- Test full monitor execution with real or mocked Azure responses
- Test timing functionality
- Test error handling
- Test configuration merging

## 10. Module Development Guide

### 10.1 Creating a New Monitoring Module

When creating a new monitoring module:

1. Create a monitor class that inherits from `BaseMonitor`:
   - Call `super().__init__()` in constructor
   - Extract `resource_id` using `self.build_resource_id(config)`
   - Extract resource-specific required fields (e.g., `location`)
2. Define metric type enum (e.g., `APIMetricType`, `StorageAccountMetricType`)
3. Implement `_get_metric_methods()` that returns a dictionary mapping enum values to method references
4. Implement metric-specific methods:
   - Signature: `monitor_<metric_name>(self, config: Dict[str, Any], metric_name: str) -> Tuple[Metric, Optional[List[MetricProblem]]]`
   - Some modules may also accept `debug: bool = False` parameter (e.g., Storage Account monitor)
   - Extract configuration from `config`
   - Call `query_metric_with_breakdown()` exactly once
   - Use `_extract_problems()` if `group_by_metadata` is specified
   - Return `(Metric, Optional[List[MetricProblem]])`
5. Implement `monitor()` method (or inherit common logic from base class if available):
   - Extract common config and metrics config
   - Iterate over enabled metrics
   - Validate metric types using enum
   - Call metric methods and collect results
   - Return `MetricResult`

### 10.2 Configuration Files

Configuration files follow a standard structure with resource-specific fields as needed.

## 11. Examples

### 11.1 APIM Monitor Example

See `src/azurechecks/monitors/apim_monitor.py` for reference implementation.

### 11.2 Storage Monitor Example

Storage monitors should follow the same pattern with appropriate metric types and methods.

## 12. Future Enhancements

Potential future improvements:

- Batch Azure SDK calls across multiple metrics (if supported by SDK)
- Caching of query results across metric executions
- Support for multiple metadata keys in grouping
- Metric result aggregation strategies
- Custom grouping logic per module

