# Test Requirements Document: Azure Checkmk Monitoring Scripts

## 1. Executive Summary

This document outlines comprehensive testing requirements for the Azure Checkmk Monitoring solution. It defines test use cases, mock response structures, edge cases, and validation criteria for all monitoring modules. The document serves as a reference for implementing unit and integration tests.

## 2. Test Structure

### 2.1 Directory Organization

```
tests/
├── unit/                          # Unit tests with mocked responses
│   ├── test_apim_monitor.py
│   ├── test_storage_account_monitor.py
│   ├── test_storage_blob_monitor.py
│   ├── test_storage_table_monitor.py
│   ├── test_servicebus_monitor.py
│   ├── test_secrets_monitor.py
│   ├── test_container_apps_monitor.py
│   ├── test_generic_check.py
│   ├── test_checkmk_formatter.py
│   └── test_config_validator.py   # Config validation tests
├── integration/                   # Integration tests with real Azure
│   ├── test_apim_integration.py
│   └── (additional integration tests)
└── fixtures/                      # Test fixtures and mock builders
    ├── azure_sdk_mocks.py         # Azure SDK response builders
    ├── config_generators.py        # Sample configuration generators
    └── checkmk_assertions.py       # Checkmk format assertion helpers
```

### 2.2 Test Types

- **Unit Tests**: Fast, isolated tests using mocked Azure SDK responses
- **Integration Tests**: End-to-end tests with real Azure resources (optional, requires credentials)

## 3. Test Use Cases by Monitor Type

### 3.1 APIM Monitor Tests

#### 3.1.1 Request Count Monitoring

**Test Cases:**
- Monitor request count for all APIs (empty `api_ids` array)
- Monitor request count for specific APIs (filtered by `api_ids`)
- Request count with thresholds (WARN, CRIT)
- Request count without thresholds
- Multiple APIs with problematic API identification
- API breakdown extraction from metadata_values
- Checkmk message format with problematic APIs: `"Problems: ApiId: api1 (150) ; api2 (200)"`

**Expected Behaviors:**
- When `api_ids` is empty, monitor all APIs
- When `api_ids` contains values, filter to only those APIs
- Problematic APIs are identified from breakdown_dict
- Status message includes problematic API IDs and their values
- Status is "P" when thresholds are present
- None values from query default to 0.0

#### 3.1.2 Requests by Status Code Categories

**Test Cases:**
- Requests 2xx monitoring (all APIs, specific APIs)
- Requests 4xx monitoring (all APIs, specific APIs)
- Requests 5xx monitoring (all APIs, specific APIs)
- Status code category filtering in Azure Monitor query
- Threshold evaluation for each category
- Problematic API identification per category

**Expected Behaviors:**
- Filter string includes `GatewayResponseCodeCategory eq '2xx'` (or 4xx/5xx)
- API filtering works correctly with status code filtering
- Problematic APIs are identified correctly

#### 3.1.3 Requests by Specific Status Codes

**Test Cases:**
- Monitor multiple specific status codes (e.g., ["200", "404", "500"])
- Each status code becomes a separate metric
- API breakdown per status code
- Aggregation of problematic APIs across status codes
- Checkmk message format with multiple status codes

**Expected Behaviors:**
- Each status code in `response_codes` array creates a metric
- API breakdown is extracted for each status code
- Problematic APIs are aggregated across all status codes
- Message format: `"Problems: ApiId: api1 (value1) ; api2 (value2)"`

### 3.2 Storage Account Monitor Tests

#### 3.2.1 Capacity Monitoring

**Test Cases:**
- Capacity at account scope (aggregated across all services)
- Capacity at Blob scope
- Capacity at Table scope
- Capacity at Queue scope
- Capacity at File scope
- Capacity with thresholds (WARN, CRIT)
- Capacity with metadata grouping (OperationName, Tier)
- Capacity with metadata filtering

**Expected Behaviors:**
- Correct namespace construction for each scope
- Resource ID modification for service-level scopes (e.g., `/blobServices/default`)
- Metadata grouping extracts problematic values correctly

#### 3.2.2 Transaction Monitoring

**Test Cases:**
- Transactions at account scope
- Transactions at service scopes (Blob, Table, Queue, File)
- Transactions with different aggregation types
- Transactions with metadata grouping (OperationName, ApiName)
- Transactions with metadata filtering
- Granularity capping (1 day for Transactions metric)

**Expected Behaviors:**
- Granularity is capped at 1 day for Transactions metric
- Metadata breakdown works correctly
- Problematic operations are identified

#### 3.2.3 Metadata Grouping and Filtering

**Test Cases:**
- Group by OperationName (e.g., "PutBlob", "GetBlob")
- Group by Tier (e.g., "Hot", "Cool", "Archive")
- Filter by metadata values (e.g., `filter_metadata_values: ["PutBlob", "GetBlob"]`)
- Multiple problematic metadata values
- Message format: `"Problems: OperationName: PutBlob (150) ; GetBlob (200)"`

**Expected Behaviors:**
- Filter string construction: `"OperationName eq 'PutBlob' or OperationName eq 'GetBlob'"`
- Breakdown dictionary contains metadata values as keys
- Problematic values exceed thresholds are identified

### 3.3 Storage Blob Monitor Tests

#### 3.3.1 File Existence Checks

**Test Cases:**
- Check single file existence
- Check multiple files existence
- Missing file detection
- MetricProblem generation for missing files
- Status determination (OK when all exist, CRIT when any missing)
- Checkmk message format with missing files
- Missing status configuration (WARN vs CRIT)

**Expected Behaviors:**
- Returns metric with value = count of missing files (0 = all exist, >0 = some missing)
- Missing files are reported as MetricProblem instances
- Status is "P" when thresholds are present (crit_threshold = 1.0 is set implicitly, or warn_threshold based on `missing_status`)
- Missing files are included in message

#### 3.3.2 File Modification Date Checks

**Test Cases:**
- Check file modification within time period
- Multiple files with different modification dates
- Missing files in modification check
- Exceeded time period detection
- Status determination (OK, WARN, CRIT based on `exceeded_status`)
- MetricProblem generation for missing/exceeded files

**Expected Behaviors:**
- Returns metric with value = maximum hours since modification
- Files missing or exceeding threshold are reported as MetricProblem
- Status is "P" when thresholds are present (warn_threshold/crit_threshold set based on `exceeded_status`)
- Status determined by `exceeded_status` config (default: "CRIT")

### 3.4 Storage Table Monitor Tests

#### 3.4.1 Table Existence Checks

**Test Cases:**
- Check single table existence
- Check multiple tables existence
- Missing table detection
- MetricProblem generation for missing tables
- Status determination (OK when all exist, CRIT when any missing)
- List all tables mode (list_all=True)

**Expected Behaviors:**
- Returns metric with value = count of missing tables (0 = all exist, >0 = some missing)
- Missing tables are reported as MetricProblem instances
- Status is "P" when thresholds are present (crit_threshold = 1.0 is set implicitly)
- When list_all=True, status is 0 (OK) with no thresholds - just counts tables

### 3.5 Service Bus Monitor Tests

#### 3.5.1 Queue Monitoring

**Test Cases:**
- Monitor all queues (empty or "*" in configuration)
- Monitor specific queues (list of queue names)
- Incoming requests per queue
- Server errors per queue
- Deadletter messages per queue
- Active messages per queue
- Queue name in service name or metric name
- Problematic queue identification

**Expected Behaviors:**
- Queue name is included in service name or metric name for identification
- Problematic queues are identified and reported in message
- All four metrics (incoming, errors, deadletter, active) are monitored

### 3.6 Container Apps Monitor Tests

#### 3.6.1 Container Metrics

**Test Cases:**
- Restarts count monitoring
- CPU percentage monitoring
- Memory percentage monitoring
- Response time monitoring
- Threshold evaluation for each metric
- Multiple metrics in single service line
- Status determination by worst metric status

**Expected Behaviors:**
- All four metrics are collected
- Thresholds are evaluated correctly
- Status is "P" when thresholds are present (Checkmk evaluates from perf data)
- Status is determined by worst metric status when multiple metrics present
- Units are correctly assigned (% for CPU/memory, ms for response time)

### 3.7 Secrets Monitor Tests

#### 3.7.1 Secret and Certificate Expiration

**Test Cases:**
- Secret expiration monitoring
- Certificate expiration monitoring
- Multiple app registrations monitoring
- Expiration threshold evaluation (tests marked as pass - implementation pending)
- Days until expiration calculation (tests marked as pass - implementation pending)
- Status determination (tests marked as pass - implementation pending)
- Message includes app names and days until expiration (tests marked as pass - implementation pending)

**Expected Behaviors:**
- Counts applications with expiring secrets/certificates
- Status is "P" when thresholds are present
- Message includes app names and days until expiration
- Note: Some test cases are currently marked as `pass` and need implementation

### 3.8 Generic Check Tests

#### 3.8.1 Configuration Routing

**Test Cases:**
- Route to APIM monitor
- Route to Storage Account monitor
- Route to Storage Blob monitor
- Route to Storage Table monitor
- Route to Service Bus monitor
- Route to Secrets monitor
- Route to Container Apps monitor
- Unsupported resource type error handling

**Expected Behaviors:**
- Correct monitor is called based on `resource_type`
- Unsupported resource types raise ValueError

#### 3.8.2 Error Handling

**Test Cases:**
- Configuration validation errors (status 3)
- Authentication errors (status 3)
- Network errors (status 3)
- Invalid resource IDs (status 3)
- Missing required fields (status 3)

**Expected Behaviors:**
- All errors return status 3 (UNKNOWN)
- Error messages are descriptive
- Exceptions are logged appropriately

#### 3.8.3 Status Code Determination

**Test Cases:**
- Status "P" when any metric has thresholds defined
- Status 0, 1, 2 when no thresholds defined
- Status 3 for errors (handled in generic_check.py main() function)
- Multiple metrics with mixed threshold configurations

**Expected Behaviors:**
- Status "P" is returned when any metric has thresholds (Checkmk evaluates from perf data)
- Numeric status (0, 1, 2) is returned when no thresholds
- Worst status wins when multiple metrics present
- Status 3 is set by formatter when there's an error

### 3.9 Config Validator Tests

#### 3.9.1 ISO8601 Duration Parsing

**Test Cases:**
- Parse valid minutes (PT5M)
- Parse valid hours (PT1H)
- Parse valid days (PT1D)
- Parse invalid format
- Parse empty string
- Parse non-string input
- Validate valid durations
- Validate invalid durations

**Expected Behaviors:**
- Returns dict with 'value' and 'unit' keys for valid formats
- Returns None for invalid formats
- Validation returns True/False appropriately

#### 3.9.2 Configuration Validation

**Test Cases:**
- Valid APIM configuration
- Missing resource_type
- Invalid resource ID format
- Invalid time_range format
- Invalid aggregation type
- Valid requests_by_codes configuration
- Missing response_codes for requests_by_codes

**Expected Behaviors:**
- Returns (True, None) for valid configs
- Returns (False, error_message) for invalid configs
- Error messages are descriptive

#### 3.9.3 Load and Validate Config

**Test Cases:**
- Load valid config file
- Load invalid JSON
- Load nonexistent file
- Load invalid configuration

**Expected Behaviors:**
- Returns config dict for valid files
- Raises ConfigValidationError for invalid files/configs
- Error messages are descriptive

### 3.10 Checkmk Formatter Tests

#### 3.10.1 MetricResult Creation

**Test Cases:**
- Create MetricResult with single metric
- Create MetricResult with multiple metrics
- Create MetricResult with problematic metadata
- Create MetricResult without problems
- Status calculation (worst status wins)
- Status "P" when thresholds present

**Expected Behaviors:**
- Status is calculated correctly
- Status "P" when any metric has thresholds (Checkmk evaluates from perf data)
- Status 0, 1, 2 when no thresholds defined (numeric status)
- Message is generated correctly

#### 3.10.2 Message Generation

**Test Cases:**
- OK message: `"OK"`
- Problems with metadata: `"Problems: ApiId: api1 (150) ; api2 (200)"`
- Metric problems: `"Problem detected"` (when only metric problems exist, no metadata problems)
- Combined problems: Only metadata problems shown (metric problems not included in message)
- Multiple metadata keys: `"Problems: ApiId: api1 (150) . OperationName: PutBlob (200)"`

**Expected Behaviors:**
- Message format matches expected patterns
- Problematic values are sorted alphabetically
- Multiple metadata keys are separated by " | "
- Values within same metadata key are separated by " ; "
- Metric problems are not included in message (only "Problem detected" when no metadata problems)

#### 3.10.3 Performance Data Formatting

**Test Cases:**
- Format metric without thresholds: `metric=100.00;;;`
- Format metric with thresholds: `metric=100.00;50;200;0;1000`
- Format metric with unit: `metric=100.00ms;50;200;;`
- Format metric with partial thresholds: `metric=100.00;50;;0;`

**Expected Behaviors:**
- Format: `metric_name=value;warn;crit;min;max`
- Empty thresholds are represented as empty strings
- Units are appended to value

#### 3.10.4 Service Line Formatting

**Test Cases:**
- Format single metric service line
- Format multiple metrics service line
- Format service line with status "P"
- Format service line with status 0, 1, 2, 3
- Service name quoting

**Expected Behaviors:**
- Format: `<status> "Service Name" <perf_data> <message>`
- Multiple metrics separated by `|`
- Service name is always quoted

## 4. Azure SDK Mock Response Structures

### 4.1 azure-monitor-querymetrics Response Structure

The `MetricsClient.query_resources()` method returns an iterator of `MetricsQueryResult` objects.

#### 4.1.1 Basic MetricsQueryResult Structure

```python
class MetricsQueryResult:
    """Mock structure for MetricsQueryResult"""
    metrics: List[Metric]
    # Other fields...

class Metric:
    """Mock structure for Metric"""
    name: str  # e.g., "Requests", "Transactions"
    timeseries: List[TimeSeriesElement]
    # Other fields...

class TimeSeriesElement:
    """Mock structure for TimeSeriesElement"""
    data: List[MetricValue]
    metadata_values: Optional[Dict[str, str]]  # e.g., {"ApiId": "api1", "OperationName": "PutBlob"}
    # Other fields...

class MetricValue:
    """Mock structure for MetricValue (data point)"""
    time_stamp: datetime
    total: Optional[float]      # For sum aggregation
    average: Optional[float]   # For average aggregation
    count: Optional[float]      # For count aggregation
    minimum: Optional[float]   # For min aggregation
    maximum: Optional[float]   # For max aggregation
```

#### 4.1.2 Example: Sum Aggregation Response

```python
# Mock response for sum aggregation
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=100.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=150.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=200.0, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected aggregated value: 450.0 (100 + 150 + 200)
```

#### 4.1.3 Example: Average Aggregation Response

```python
# Mock response for average aggregation
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=None, average=50.0, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=75.0, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=100.0, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected aggregated value: 100.0 (uses last data point average)
```

#### 4.1.4 Example: Count Aggregation Response

```python
# Mock response for count aggregation
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=None, average=None, count=10.0, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=None, count=15.0, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=None, count=20.0, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected aggregated value: 45.0 (10 + 15 + 20)
```

#### 4.1.5 Example: Min Aggregation Response

```python
# Mock response for min aggregation
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=None, average=None, count=None, minimum=10.0, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=None, count=None, minimum=5.0, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=None, count=None, minimum=15.0, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected aggregated value: 5.0 (minimum across all data points)
```

#### 4.1.6 Example: Max Aggregation Response

```python
# Mock response for max aggregation
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=None, average=None, count=None, minimum=None, maximum=100.0),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=None, count=None, minimum=None, maximum=150.0),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=None, count=None, minimum=None, maximum=200.0),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected aggregated value: 200.0 (maximum across all data points)
```

#### 4.1.7 Example: Metadata Breakdown Response

```python
# Mock response with metadata breakdown (ApiId)
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=100.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=150.0, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values={"ApiId": "api1"}
                ),
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=50.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=75.0, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values={"ApiId": "api2"}
                )
            ]
        )
    ]
)
# Expected breakdown_dict: {"api1": 250.0, "api2": 125.0}
# Expected aggregated value: 375.0 (sum of breakdown_dict.values()) - REGARDLESS OF AGGREGATION TYPE
```

#### 4.1.8 Edge Case: Last Data Point with All None Fields

```python
# Mock response where last data point has all None fields
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=100.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=150.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=None, count=None, minimum=None, maximum=None),  # All None - should be filtered out
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected behavior: Last data point is filtered out (all fields are None)
# For sum aggregation: Expected aggregated value: 250.0 (100 + 150)
# For average aggregation: Should use previous valid data point or handle gracefully
```

#### 4.1.9 Edge Case: Mixed None/Valid Values

```python
# Mock response with mixed None/valid values
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=100.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=75.0, count=None, minimum=None, maximum=None),  # total is None but average is valid
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=200.0, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected behavior: Data point is NOT filtered out (has at least one non-None field)
# For sum aggregation: Expected aggregated value: 300.0 (100 + 200, ignoring the one with None total)
```

#### 4.1.10 Edge Case: Empty Data Points After Filtering

```python
# Mock response where all data points are filtered out
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=None, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=None, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 10), total=None, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected behavior: All data points filtered out, should return None
# Expected aggregated value: None
```

#### 4.1.11 Edge Case: Zero Sum Values

```python
# Mock response with zero sum values
metrics_query_result = MetricsQueryResult(
    metrics=[
        Metric(
            name="Requests",
            timeseries=[
                TimeSeriesElement(
                    data=[
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 0), total=0.0, average=None, count=None, minimum=None, maximum=None),
                        MetricValue(time_stamp=datetime(2024, 1, 1, 10, 5), total=0.0, average=None, count=None, minimum=None, maximum=None),
                    ],
                    metadata_values=None
                )
            ]
        )
    ]
)
# Expected behavior: Sum is 0.0, but code checks if total_sum > 0
# Expected aggregated value: None (because total_sum == 0)
```

### 4.2 azure-storage-blob Response Structure

```python
# Mock BlobServiceClient.get_blob_client().get_blob_properties() response
class BlobProperties:
    """Mock structure for BlobProperties"""
    name: str
    last_modified: datetime
    size: int
    # Other fields...

# Mock BlobServiceClient.list_blobs() response
class BlobItem:
    """Mock structure for BlobItem"""
    name: str
    properties: BlobProperties
    # Other fields...
```

### 4.3 azure-storage-table Response Structure

```python
# Mock TableServiceClient.list_tables() response
# Returns iterator of TableItem objects
class TableItem:
    """Mock structure for TableItem"""
    name: str
    # Other fields...
```

### 4.4 Error Responses

```python
# Authentication error
class AzureAuthError(Exception):
    """Mock authentication error"""
    pass

# Network error
class RequestException(Exception):
    """Mock network error"""
    pass

# Rate limiting error
class HttpResponseError(Exception):
    """Mock rate limiting error"""
    status_code: int  # e.g., 429
    pass
```

## 5. Aggregation Type Test Scenarios

### 5.1 All Aggregation Types

The system supports five aggregation types:
- `sum`: Sum all data point totals
- `average`: Use latest data point average value
- `count`: Sum all data point counts
- `min`: Find minimum across all data points
- `max`: Find maximum across all data points

### 5.2 Aggregation Calculation Test Cases

#### 5.2.1 Without Metadata Breakdown

**Sum Aggregation:**
- Sum all `total` values from data points
- Example: [100, 150, 200] → 450
- Zero sum returns 0.0 (not None)

**Average Aggregation:**
- Use `average` from last data point
- Example: [50, 75, 100] → 100 (uses last)
- If last data point has None average, handle gracefully

**Count Aggregation:**
- Sum all `count` values from data points
- Example: [10, 15, 20] → 45

**Min Aggregation:**
- Find minimum `minimum` value across all data points
- Example: [10, 5, 15] → 5

**Max Aggregation:**
- Find maximum `maximum` value across all data points
- Example: [100, 150, 200] → 200

#### 5.2.2 With Metadata Breakdown

**Critical Behavior:**
When metadata breakdown exists, the aggregated value is calculated using the `metadata_aggregation` parameter:
- If `metadata_aggregation` is specified in configuration, it uses that aggregation type
- If `metadata_aggregation` is not specified, it defaults to the `aggregation` parameter value
- Valid values: 'sum', 'average', 'count', 'min', 'max'

**Test Cases:**

1. **Sum Aggregation with Metadata:**
   - Breakdown values are calculated per metadata using the specified aggregation
   - Then all breakdown values are summed for aggregate
   - Example: api1=250, api2=125 → aggregate=375 (when metadata_aggregation='sum')

2. **Average Aggregation with Metadata:**
   - Breakdown values are calculated per metadata using the specified aggregation
   - Then all breakdown values are averaged: `sum(breakdown_dict.values()) / len(breakdown_dict)`
   - Example: api1=100, api2=75 → aggregate=87.5 (when metadata_aggregation='average')

3. **Min Aggregation with Metadata:**
   - Breakdown values are calculated per metadata using the specified aggregation
   - Then minimum value is selected: `min(breakdown_dict.values())`
   - Example: api1=5, api2=10 → aggregate=5 (when metadata_aggregation='min')

4. **Max Aggregation with Metadata:**
   - Breakdown values are calculated per metadata using the specified aggregation
   - Then maximum value is selected: `max(breakdown_dict.values())`
   - Example: api1=200, api2=150 → aggregate=200 (when metadata_aggregation='max')

5. **Count Aggregation with Metadata:**
   - Breakdown values are calculated per metadata using the specified aggregation
   - Then all breakdown values are summed for aggregate
   - Example: api1=45, api2=30 → aggregate=75 (when metadata_aggregation='count' or 'sum')

### 5.3 Edge Cases for Aggregation

#### 5.3.1 Empty Data Points Array

**Test Case:**
- All data points filtered out (all None)
- Expected: Return None from query_metric_with_breakdown
- In monitor: None values default to 0.0

#### 5.3.2 Last Data Point with All None Fields

**Test Case:**
- Last data point has all fields as None
- Expected: Filtered out in aggregation logic, use previous valid data point
- For sum: Sum all valid data points
- For average: Use last valid data point's average
- For min/max: Calculate from valid data points only
- Note: This is handled in the aggregation logic, not explicitly tested in current tests

#### 5.3.3 Mixed None/Valid Values

**Test Case:**
- Data points with some None fields but at least one valid field
- Expected: Data point is NOT filtered out
- Aggregation uses appropriate field (total for sum, average for average, etc.)
- Note: Current tests mock query_metric_with_breakdown, so this is tested indirectly

#### 5.3.4 Single Data Point

**Test Case:**
- Only one data point in timeseries
- Expected: Use that data point's value
- All aggregation types work correctly
- Note: Current tests mock the aggregated result, not individual data points

#### 5.3.5 Zero Values

**Test Case:**
- Sum aggregation with all zeros
- Expected: Return 0.0 from query_metric_with_breakdown (zero values are represented as 0.0, not None)
- In monitor: 0.0 values are used directly (no defaulting needed)

#### 5.3.6 Average Aggregation with None Average

**Test Case:**
- Last data point has None average
- Expected: Handle gracefully (use previous valid average or return None)
- Note: Current tests mock the aggregated result, not individual data points

## 6. Metadata Grouping Test Scenarios

### 6.1 Group by ApiId (APIM)

**Test Cases:**
- Multiple APIs with different request counts
- API breakdown extraction from metadata_values
- Problematic API identification (exceeds thresholds)
- Message format: `"Problems: ApiId: api1 (150) ; api2 (200)"`

**Expected Behaviors:**
- Breakdown dictionary: `{"api1": 150.0, "api2": 200.0}`
- Problematic APIs identified when values exceed thresholds
- Message includes metadata key prefix: "ApiId:"

### 6.2 Group by OperationName (Storage Account)

**Test Cases:**
- Multiple operations (PutBlob, GetBlob, DeleteBlob)
- Operation breakdown extraction
- Problematic operation identification
- Message format: `"Problems: OperationName: PutBlob (150) ; GetBlob (200)"`

**Expected Behaviors:**
- Breakdown dictionary: `{"PutBlob": 150.0, "GetBlob": 200.0}`
- Problematic operations identified
- Message includes metadata key prefix: "OperationName:"

### 6.3 Group by Tier (Storage Account)

**Test Cases:**
- Multiple tiers (Hot, Cool, Archive)
- Tier breakdown extraction
- Problematic tier identification
- Message format: `"Problems: Tier: Hot (150) ; Cool (200)"`

**Expected Behaviors:**
- Breakdown dictionary: `{"Hot": 150.0, "Cool": 200.0}`
- Problematic tiers identified

### 6.4 Filter by Metadata Values

**Test Cases:**
- Filter by specific metadata values (e.g., `filter_metadata_values: ["PutBlob", "GetBlob"]`)
- Filter string construction: `"OperationName eq 'PutBlob' or OperationName eq 'GetBlob'"`
- Only filtered values appear in breakdown
- Problematic filtered values are identified

**Expected Behaviors:**
- Filter string is constructed correctly
- Only specified values are included in breakdown
- Problematic values are identified from filtered results

### 6.5 Multiple Problematic Metadata Values

**Test Cases:**
- Multiple metadata values exceed thresholds
- Values are sorted alphabetically in message
- Message format: `"Problems: ApiId: api1 (150) ; api2 (200) ; api3 (300)"`

**Expected Behaviors:**
- All problematic values are included
- Values are sorted by problem_name
- Format: `"value1 (value1) ; value2 (value2)"`

### 6.6 Multiple Metadata Keys

**Test Cases:**
- Different metadata keys in same result
- Message format: `"Problems: ApiId: api1 (150) . OperationName: PutBlob (200)"`

**Expected Behaviors:**
- Metadata keys are separated by " . "
- Values within same key are separated by " ; "

## 7. Checkmk Result Message Validation

### 7.1 OK Message

**Test Case:**
- No problems detected
- Expected: `"OK"`

### 7.2 Problems with Metadata

**Test Case:**
- Problematic metadata values detected
- Expected: `"Problems: ApiId: api1 (150) ; api2 (200)"`
- Format: `"Problems: <metadata_key>: <value1> (<value1>) ; <value2> (<value2>)"`

### 7.3 Metric Problems

**Test Case:**
- Metrics exceed thresholds (no metadata problems)
- Expected: `"Problem detected"`
- Format: When only metric problems exist (no metadata problems), show "Problem detected"

### 7.4 Combined Problems

**Test Case:**
- Both metadata and metric problems
- Expected: `"Problems: ApiId: api1 (150) ; api2 (200)"`
- Format: Only metadata problems are shown in message (metric problems are not included)

### 7.5 Status Code Determination

**Test Cases:**
- Status "P" when any metric has thresholds defined
- Status 0 when no thresholds and all metrics OK
- Status 1 when no thresholds and worst metric is WARN
- Status 2 when no thresholds and worst metric is CRIT
- Status 3 for errors

**Expected Behaviors:**
- Status "P" takes precedence over numeric status when thresholds present
- Worst status wins when multiple metrics present

## 8. Test Coverage Requirements

### 8.1 Unit Test Coverage

- **Target**: 80%+ code coverage
- **Coverage Areas**:
  - All metric types for each monitor
  - All threshold scenarios (OK, WARN, CRIT)
  - All metadata grouping scenarios
  - All aggregation types (sum, average, count, min, max)
  - Aggregation calculation with and without metadata breakdown
  - Edge cases (None values, empty responses, last data point with all None fields)
  - Error handling paths

### 8.2 Integration Test Coverage

- **Coverage Areas**:
  - End-to-end check execution flow
  - Real Azure resource queries
  - Authentication with real Service Principal
  - Performance validation (<30 seconds execution time)

### 8.3 Test Execution Requirements

- **Unit Tests**:
  - Run without Azure connectivity
  - Use mocked responses exclusively
  - Fast execution (<1 second per test)
  - Runnable in CI/CD pipeline

- **Integration Tests**:
  - Require Azure connectivity and credentials
  - Use real Azure resources
  - May be slower (depends on Azure API response times)
  - Run manually or in dedicated test environment

## 9. Mock Response Builders

### 9.1 MetricsQueryResult Builder

Create helper functions to build mock MetricsQueryResult objects:

```python
def build_metrics_query_result(
    metric_name: str,
    data_points: List[Dict],
    metadata_values: Optional[Dict[str, str]] = None
) -> MetricsQueryResult:
    """Build mock MetricsQueryResult with specified data points and metadata."""
    # Implementation...
```

### 9.2 Data Point Builder

Create helper functions to build mock MetricValue objects:

```python
def build_data_point(
    time_stamp: datetime,
    total: Optional[float] = None,
    average: Optional[float] = None,
    count: Optional[float] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None
) -> MetricValue:
    """Build mock MetricValue data point."""
    # Implementation...
```

### 9.3 Configuration Generators

Create helper functions to generate test configurations:

```python
def generate_apim_config(
    api_ids: List[str] = None,
    metrics: Dict[str, Dict] = None
) -> Dict:
    """Generate APIM test configuration."""
    # Implementation...
```

## 10. Test Assertion Helpers

### 10.1 Checkmk Format Assertions

Create helper functions to assert Checkmk output format:

```python
def assert_checkmk_format(output: str) -> None:
    """Assert output matches Checkmk format."""
    # Format: <status> "Service Name" <perf_data> <message>
    # Implementation...

def assert_performance_data(perf_data: str, expected_format: str) -> None:
    """Assert performance data matches expected format."""
    # Format: metric=value;warn;crit;min;max
    # Implementation...
```

### 10.2 MetricResult Assertions

Create helper functions to assert MetricResult structure:

```python
def assert_metric_result(
    result: MetricResult,
    expected_status: Union[int, str],
    expected_metrics_count: int,
    expected_message: Optional[str] = None
) -> None:
    """Assert MetricResult matches expected values."""
    # Implementation...
```

## 11. Test Data Examples

### 11.1 Sample Configurations

Include sample JSON configurations for each resource type:
- APIM configuration with multiple APIs
- Storage Account configuration with metadata grouping
- Storage Blob configuration with file checks
- Service Bus configuration with queue filtering

### 11.2 Sample Azure Responses

Include complete mock response examples:
- MetricsQueryResult with multiple timeseries
- MetricsQueryResult with metadata breakdown
- MetricsQueryResult with edge cases (None values, empty data)
- Error responses (authentication, network, rate limiting)

## 12. Notes

- Tests are implemented and match current sync architecture
- Mock responses use query_metric_with_breakdown method mocking (not direct Azure SDK mocks)
- All aggregation types are tested thoroughly
- Edge cases are covered (None values, empty breakdowns, zero values)
- Metadata breakdown aggregation behavior (sum regardless of aggregation type) is tested
- Status "P" is used when thresholds are present (Checkmk evaluates from perf data)
- Status 0, 1, 2 are used when no thresholds are defined
- Some Secrets Monitor test cases are marked as `pass` and need implementation
- Config Validator tests are implemented and cover ISO8601 parsing, validation, and file loading

