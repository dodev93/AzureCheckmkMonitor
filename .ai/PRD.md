# Product Requirements Document: Azure Checkmk Monitoring Scripts

## 1. Executive Summary

This document outlines the requirements for developing a comprehensive Python-based solution that integrates Azure resource monitoring with Checkmk local checks. The solution will monitor multiple Azure resource types including:
* Azure API Management (APIM) - request counts, requests by response code categories (2xx, 4xx, 5xx), and requests by specific response codes (all metrics may be filtered for specific APIS)
* Azure Storage Accounts - capacity, transactions (all metrics may be splitted by storage account service type - blob, table, queue, file) 
* Azure Storage Blobs - file existence checks, file modification date checks (capacity and transactions monitored via Storage Account with scope="Blob")
* Azure Storage Tables - table existence checks (capacity and transactions monitored via Storage Account with scope="Table")
* Azure Container Apps - restarts count, CPU percentage, memory percentage, response time
* Azure Virtual Machine Scale Sets - available memory percentage, CPU percentage
* Azure Service Bus Namespaces - incoming requests per queue, server errors, deadletter messages, active messages
* Azure App Registrations - secrets and certificates expiration monitoring
* Azure Kubernetes Service (AKS) - node CPU percentage, node memory percentage, node disk usage

The solution provides a generic, configuration-driven architecture using JSON configuration files, a web-based GUI for configuration generation, and comprehensive testing capabilities. All monitoring data is delivered in Checkmk-compatible format with support for multiple metrics in single service.

## 2. Objectives

- Enable Checkmk to monitor Azure resources using Azure Python SDK
- Provide generic, configuration-driven architecture using JSON configuration files
- Support modular, maintainable scripts separated by concern (Azure logic vs. Checkmk integration)
- Support independent dependency management through virtual environments
- Deliver actionable monitoring data for all supported Azure resource types
- Provide web-based GUI for easy configuration generation and management
- Enable unit and integration testing with mocked and real Azure responses
- Support multiple metrics in output per local check script

## 2.1 Technology Stack

### 2.1.1 Python SDKs
- **azure-monitor-querymetrics** - Primary SDK for querying Azure Monitor metrics
- **azure-identity** - Azure authentication and credential management
- **azure-mgmt-resourcegraph** - Azure Resource Graph queries for resource discovery
- **azure-storage-blob** - Azure Blob Storage operations
- **azure-mgmt-containerinstance** - Container Apps operations
- **azure-mgmt-compute** - Virtual Machine Scale Sets operations
- **azure-servicebus** - Service Bus operations
- **msal** - Microsoft Authentication Library for Graph API access

### 2.1.2 Web GUI
- **Flutter** - Cross-platform framework for web-based configuration GUI
- **Azure AD Authentication** - User authentication using Azure Active Directory

### 2.1.3 Testing
- **pytest** - Python testing framework
- **unittest.mock** - Mocking Azure SDK responses for unit tests
- **pytest-azure** or similar - Integration testing with real Azure resources

### 2.1.4 Configuration
- **JSON** - Configuration file format
- **JSON Schema** - Configuration validation schemas

## 3. Scope

### 3.1 In Scope
- **Azure API Management (APIM)**: Request counts, requests by response code categories (2xx, 4xx, 5xx), and requests filtered by specific response codes, all with API ID filtering support
- **Azure Storage Accounts**: Capacity monitoring, transaction monitoring. Support for splitting by service type (blob, table, queue, file) 
- **Azure Storage Blobs**: 
  - File existence checks (single or multiple files)
  - File modification date checks (verify if file was modified within specified time period)
  - Note: Capacity and transaction metrics for blob storage are monitored via Storage Account monitor with scope="Blob"
- **Azure Storage Tables**: Table existence checks (verify if specified tables exist in storage account)
  - Note: Capacity and transaction metrics for table storage are monitored via Storage Account monitor with scope="Table"
- **Azure Container Apps**: Restarts count, CPU percentage, memory percentage, average response time
- **Azure Virtual Machine Scale Sets**: Available memory percentage, CPU percentage
- **Azure Service Bus Namespaces**: Incoming requests per queue, server errors, deadletter messages, active messages (support for all queues or specific queues)
- **Azure App Registration**: Secrets and certificates expiration monitoring
- **Azure Kubernetes Service (AKS)**: Node count (ready, not ready), node CPU percentage, node memory percentage, node disk usage
- **JSON-based Configuration**: Generic configuration system using JSON files
- **Configuration Templates**: Pre-defined templates for each Azure resource type
- **Web GUI**: Flutter-based web application for configuration generation and management
- **Configuration Generator Tool**: CLI and web-based tool for generating and validating configurations
- **Resource Discovery**: Azure Resource Graph integration for discovering available resources
- **Service Principal and Azure AD Authentication**: Support for both authentication methods
- **Checkmk Local Check Integration**: Generic script architecture supporting multiple service outputs
- **Unit and Integration Testing**: Comprehensive testing with mocked and real Azure responses
- **Virtual Environment Setup**: Dependency isolation

### 3.2 Out of Scope
- Azure Active Directory user management
- Azure Resource Manager resource provisioning
- Multi-cloud support (AWS, GCP)
- Historical data storage or trending beyond Checkmk's native capabilities
- Alerting beyond Checkmk's native capabilities
- Service Bus Topics and Subscriptions (only Queues supported in initial version)
- Web GUI testing (unit and integration tests focus on Python scripts only)

## 4. Architecture

### 4.1 Directory Structure

```
AzureCheckmkMonitor/                  # Project root directory
├── src/                               # Python source code
│   ├── azurechecks/                   # Azure monitoring package
│   │   ├── generic_check.py           # Generic script that routes to resource-specific modules
│   │   ├── azure_auth.py              # Azure authentication utilities
│   │   └── monitors/                  # Resource-specific monitoring modules
│   │       ├── base_monitor.py        # Base class for all monitors
│   │       ├── apim_monitor.py        # APIM monitoring
│   │       ├── storage_account_monitor.py
│   │       ├── storage_blob_monitor.py
│   │       ├── storage_table_monitor.py
│   │       ├── servicebus_monitor.py
│   │       ├── secrets_monitor.py
│   │       ├── container_apps_monitor.py
│   │       └── aks_monitor.py
│   ├── checkmk/                       # Checkmk integration
│   │   └── checkmk_formatter.py       # Checkmk output formatting
│   ├── validation/                    # Configuration validation
│   │   ├── config_validator.py        # Configuration validator
│   │   └── validate_config.py         # Standalone validation script
│   ├── utils.py                       # Utility functions
│   └── exceptions.py                  # Custom exceptions
│
├── configs/                           # Configuration files directory
│   ├── templates/                     # Configuration template files
│   └── schemas/                       # JSON schemas for validation
│
├── tools/                             # Configuration tools
│   ├── azure_check                    # Generic local check script
│   └── config_validation              # Configuration validation script
│
├── examples/                          # Example configurations and scripts
│   ├── configs/                       # Example configuration files
│   └── local_checks/                  # Example local check scripts
│
├── tests/                             # Test suite
│   ├── unit/                          # Unit tests with mocked responses
│   └── integration/                   # Integration tests with real Azure
│
├── venv/                              # Python virtual environment
├── requirements.txt                   # Python dependencies
└── LICENSE                            # License file
```

### 4.2 Component Overview

#### 4.2.1 Generic Check Script (`generic_check.py`)
- **Purpose**: Main entry point that routes to resource-specific monitoring modules based on JSON configuration
- **Location**: `src/azurechecks/generic_check.py`
- **Input**: JSON configuration file path
- **Execution**: Reads configuration, validates it, calls appropriate resource monitor
- **Output**: Single line in Checkmk format (with single or multiple metrics)

#### 4.2.2 Resource-Specific Monitor Modules
- **Purpose**: Contains all Azure SDK interaction logic for specific resource types
- **Location**: `src/azurechecks/monitors/`
- **Architecture**: Each module contains separate functions for different metrics/features. All modules has to return result as MetricResult class from `checkmk_formatter.py`
- **Execution**: Functions are called based on configuration file content
- **Dependencies**: Managed via virtual environment
- **Sync Architecture**: Modules use synchronous calls for execution.

#### 4.2.3 Configuration System
- **Purpose**: JSON-based configuration files define what metrics to monitor and how
- **Location**: `configs/`
- **Structure**: One JSON file per local check. Some options are defined in root level and may be overwritten in specific metric definition (for example time_range)
- **Templates**: Pre-defined templates in `configs/templates/` directory
- **Validation**: JSON schemas in `configs/schemas/` directory

#### 4.2.4 Local Check Scripts
- **Purpose**: Shell scripts that invoke generic Python script with configuration file
- **Location**: `tools/azure_check` (to be copied to `/usr/lib/check_mk_agent/local/`)
- **Execution**: Calls `src/azurechecks/generic_check.py` with JSON configuration file path
- **Output**: Checkmk-compatible format (status, service name, metrics, message). When WARN or CRIT threshold is defined in metric then status has to be returned with value 'P' instead of 0,1,2. Only 3 may be returned in case of error.

#### 4.2.5 Configuration Generator Tool
- **Purpose**: CLI tool for validating JSON configurations
- **Location**: `tools/config_validation` and `src/validation/validate_config.py`
- **Features**: Validate existing configs using JSON schemas

#### 4.2.6 Web GUI (Flutter)
- **Purpose**: Web-based interface for generating and managing configurations
- **Location**: Not implemented (out of scope for current version)
- **Status**: Future enhancement - see section 10 (Future Enhancements)
- **Planned Features**: 
  - Azure AD authentication
  - Resource discovery via Azure Resource Graph
  - Interactive configuration builder
  - Configuration validation
  - Download generated configurations
  - Edit configurations by uploading files
  - Resource list caching with refresh capability

### 4.3 Data Flow

#### 4.3.1 Checkmk Local Check Execution Flow

```
Checkmk Agent
    ↓
Local Check Script (azure_check with config.json)
    ↓
Generic Check Script (generic_check.py)
    ↓
Configuration Loader (load JSON config)
    ↓
Resource-Specific Monitor Module (e.g., apim_monitor.py)
    ↓
Azure SDK (e.g. azure-monitor-querymetrics)
    ↓
Azure REST APIs
    ↓
Response Data
    ↓
Checkmk Formatter (formats service output with single or multiple metrics)
    ↓
Single Checkmk Service Line
    ↓
Checkmk Server
```

#### 4.3.2 Web GUI Configuration Generation Flow

```
User (Azure AD Authenticated)
    ↓
Web GUI (Flutter)
    ↓
Azure Resource Graph API (discover resources)
    ↓
Resource List (cached)
    ↓
User Selects Resource & Configures Metrics
    ↓
Configuration Generator
    ↓
JSON Configuration File
    ↓
Validation
    ↓
Download/Display Configuration
```

## 5. Functional Requirements

### 5.1 Authentication (FR-AUTH)

**FR-AUTH-1**: The system shall authenticate to Azure using Service Principal credentials.

**FR-AUTH-2**: Service Principal credentials shall be provided via environment variables:
- `AZURE_CLIENT_ID` - Service Principal application (client) ID
- `AZURE_CLIENT_SECRET` - Service Principal secret value
- `AZURE_TENANT_ID` - Azure Active Directory tenant ID
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

**FR-AUTH-3**: Authentication shall support all Azure services required for monitoring (APIM, Storage, Key Vault/Graph API).

**FR-AUTH-4**: Authentication failures shall return UNKNOWN status (3) with descriptive error message.

### 5.2 APIM Monitoring (FR-APIM)

**FR-APIM-1**: The system shall monitor Azure API Management services.

**FR-APIM-2**: The system shall collect the following metrics:
- **Request Count**: Total number of requests (all response codes)
- **Requests 2xx**: Total number of successful requests (2xx response codes)
- **Requests 4xx**: Total number of client error requests (4xx response codes)
- **Requests 5xx**: Total number of server error requests (5xx response codes)
- **Requests by Codes**: Total number of requests filtered by specific response codes (configurable list)

**FR-APIM-3**: All metrics shall support API ID filtering:
- API ID(s) shall be specified in configuration via `api_ids` array
- Empty `api_ids` array means all APIs are monitored
- When API IDs are specified, metrics are filtered to only those APIs
- **API IDs must be provided directly**: Users must provide the actual API IDs as they appear in Azure Monitor metrics (ApiId dimension)
- API IDs are the actual identifiers used in Azure Monitor metrics filters (ApiId eq '<api_id>')
- API IDs can be found in Azure Portal or via APIM Management API

**FR-APIM-4**: The system shall support monitoring multiple APIs in a single check:
- Multiple API IDs shall be specified in JSON configuration via `api_ids` array
- Metrics are aggregated for all APIs and information about problematic APIs has to be putted in status message
- When thresholds are exceeded, the system shall identify which specific APIs are problematic
- API breakdown data shall be retrieved for each metric to enable per-API threshold evaluation
- Problematic APIs shall be reported in status messages with format: `"Problems: ApiId: api1 (value1) ; api2 (value2)"` (metadata key prefix is included in the message)

**FR-APIM-5**: APIM resource shall be identified by:
- Subscription ID, Resource Group name, and APIM service name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading
- All three fields (subscription_id, resource_group, resource_name) are required

**FR-APIM-6**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.
- Location has to be given in JSON configuration file
- Metrics endpoint format: `https://<region>.metrics.monitor.azure.com`

**FR-APIM-7**: Metrics shall be retrieved for a configurable time period (default: last 1 hour).
Granularity is initially set to the same value as timespan. When querying Azure Monitor, granularity is automatically capped at 1 day (PT1D) by the base monitor class, as Azure Monitor does not support granularity longer than 1 day.

**FR-APIM-8**: Output shall include metrics data in Checkmk format with thresholds:
`<metric_1>=<value>;warn;crit;min;max|<metric_2>=<value>;warn;crit;min;max`

**FR-APIM-9**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file
- When multiple APIs are monitored and thresholds are exceeded, status messages shall identify problematic APIs
- Message format for problematic APIs: `"Problems: ApiId: api1 (value1) ; api2 (value2)"` (metadata key prefix is included)
- Overall status shall be determined by the worst status across all metrics (CRIT > WARN > OK)

### 5.3 Storage Account Monitoring (FR-STORAGE)

**FR-STORAGE-1**: The system shall monitor Azure Storage Accounts for capacity and transactions.

**FR-STORAGE-2**: The system shall collect the following metrics:
- **Capacity**: Total storage capacity used (in bytes)
- **Transactions**: Total number of transactions

**FR-STORAGE-3**: Storage account shall be identified by:
- Subscription ID, Resource Group name, and Storage account name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-STORAGE-4**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.

**FR-STORAGE-5**: Metrics scope shall be configurable:
- Account-level metrics (aggregated across all services)
- Service-level metrics (Blob, Table, Queue, File)
- Scope is specified via `scope` field in metric configuration (default: "account")

**FR-STORAGE-5a**: Metrics shall support metadata grouping and filtering:
- `group_by_metadata`: Optional metadata key for grouping (e.g., "ApiName", "OperationName", "Tier")
- `filter_metadata_values`: Optional list of metadata values to filter by
- When grouping is enabled, problematic metadata values are reported as `MetricProblem` instances
- Supports both root-level and per-metric configuration

**FR-STORAGE-6**: Output shall include performance data in Checkmk format with thresholds (metric name can be overwriten by JSON configuration file):
- `storage_capacity=<value>;warn;crit;min;max`
- `storage_transactions=<value>;warn;crit;min;max`

**FR-STORAGE-7**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file

### 5.4 Storage Blob Monitoring (FR-STORAGE-BLOB)

**FR-STORAGE-BLOB-1**: The system shall monitor Azure Storage Blob containers for file operations.

**Note**: Capacity and transaction metrics for blob storage are monitored using the Storage Account monitor (section 5.3) with `scope: "Blob"` configuration. The Storage Blob monitor focuses exclusively on file-level operations.

**FR-STORAGE-BLOB-2**: The system shall support file existence checks:
- Check if specific file(s) exist in a container
- Support for single file or multiple files (list in configuration via `files` array)
- Returns a single metric representing the count of missing files (0 = all exist, >0 = some missing)
- Missing files are reported as `MetricProblem` instances in the result
- Status determination:
  - OK: All files exist (value = 0)
  - CRIT: One or more files are missing (value >= 1, crit_threshold = 1.0)

**FR-STORAGE-BLOB-3**: The system shall support file modification date checks:
- Check if file(s) were modified within specified time period
- Time period shall be configurable in JSON via `max_hours_since_modification` (default: 24 hours)
- Returns a single metric representing the maximum hours since modification across all files
- Files that are missing or exceed the threshold are reported as `MetricProblem` instances
- Status determination:
  - OK: All files modified within time period
  - WARN: File(s) exceed time period (if `exceeded_status: "WARN"` is configured)
  - CRIT: File(s) missing or exceed time period (if `exceeded_status: "CRIT"` is configured, default)

**FR-STORAGE-BLOB-4**: Storage blob shall be identified by:
- Subscription ID, Resource Group name, and Storage account name (resource_name) - **preferred method**
- Container name is specified separately via `container_name` field (required)
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-STORAGE-BLOB-5**: File operations shall use `azure-storage-blob` SDK via `get_blob_service_client()` function.

**FR-STORAGE-BLOB-6**: Output shall include metrics data in Checkmk format:
- `file_existence=<missing_count>;warn;crit;min;max` (missing_count = 0 if all exist, >0 if any missing)
- `file_modification=<max_hours>h;warn;crit;min;max` (max_hours = maximum hours since modification)

**FR-STORAGE-BLOB-7**: All thresholds and configurations shall be defined in JSON configuration file:
- `files`: Array of file paths to check (required)
- `max_hours_since_modification`: Maximum hours since modification (default: 24)
- `exceeded_status`: Status when threshold exceeded ("WARN" or "CRIT", default: "CRIT")
- `warn_threshold`, `crit_threshold`: Optional thresholds
- `min`, `max`: Optional min/max values

### 5.5 Storage Table Monitoring (FR-STORAGE-TABLE)

**FR-STORAGE-TABLE-1**: The system shall monitor Azure Storage Tables for table existence.

**Note**: Capacity and transaction metrics for table storage are monitored using the Storage Account monitor (section 5.3) with `scope: "Table"` configuration. The Storage Table monitor focuses exclusively on table existence checks.

**FR-STORAGE-TABLE-2**: The system shall support table existence checks:
- Check if specific table(s) exist in the storage account
- Tables to check are specified via `filtered_tables` array in configuration (required, must not be empty)
- Returns a single metric representing the count of missing tables (0 = all exist, >0 = some missing)
- Missing tables are reported as `MetricProblem` instances in the result
- Status determination:
  - OK: All tables exist (value = 0)
  - CRIT: One or more tables are missing (value >= 1, crit_threshold = 1.0)

**FR-STORAGE-TABLE-3**: Storage table shall be identified by:
- Subscription ID, Resource Group name, and Storage account name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-STORAGE-TABLE-4**: Table operations shall use `azure-storage-table` SDK via `get_table_service_client()` function to list tables.

**FR-STORAGE-TABLE-5**: Output shall include performance data in Checkmk format:
- `table_existence=<missing_count>;warn;crit;min;max` (missing_count = 0 if all exist, >0 if any missing)

**FR-STORAGE-TABLE-6**: All thresholds and configurations shall be defined in JSON configuration file:
- `filtered_tables`: Array of table names to check (required, must not be empty)
- `warn_threshold`: Optional warning threshold
- `crit_threshold`: Automatically set to 1.0 (CRIT if any table is missing)
- `min`, `max`: Optional min/max values

### 5.6 Container Apps Monitoring (FR-CONTAINER-APPS)

**FR-CONTAINER-APPS-1**: The system shall monitor Azure Container Apps.

**FR-CONTAINER-APPS-2**: The system shall collect the following metrics:
- **Restarts Count**: Number of container restarts
- **CPU Percentage**: Average CPU usage percentage
- **Memory Percentage**: Average memory usage percentage
- **Response Time**: Average response time in milliseconds

**FR-CONTAINER-APPS-3**: Container app shall be identified by:
- Subscription ID, Resource Group name, and Container App name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-CONTAINER-APPS-4**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.

**FR-CONTAINER-APPS-5**: Monitoring shall be for specific container app (not aggregated across multiple apps).

**FR-CONTAINER-APPS-6**: Output shall include performance data in Checkmk format with thresholds (metric name can be overwriten by JSON configuration file):
- `container_restarts=<value>;warn;crit;min;max|container_cpu_percent=<value>;warn;crit;0;100|container_memory_percent=<value>;warn;crit;0;100|container_response_time=<value>ms;warn;crit;min;max`

**FR-CONTAINER-APPS-7**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file

### 5.7 Virtual Machine Scale Sets Monitoring (FR-VMSS)

**FR-VMSS-1**: The system shall monitor Azure Virtual Machine Scale Sets.

**FR-VMSS-2**: The system shall collect the following metrics:
- **Available Memory Percentage**: Percentage of available memory
- **CPU Percentage**: Average CPU usage percentage

**FR-VMSS-3**: VM Scale Set shall be identified by:
- Subscription ID, Resource Group name, and VM Scale Set name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-VMSS-4**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.

**FR-VMSS-5**: Metrics may be aggregated across all instances or reported per instance (configurable).

**FR-VMSS-6**: Output shall include performance data in Checkmk format with thresholds (metric name can be overwriten by JSON configuration file):
- `vmss_available_memory_percent=<value>;warn;crit;0;100|vmss_cpu_percent=<value>;warn;crit;0;100`

**FR-VMSS-7**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file

### 5.8 Service Bus Namespace Monitoring (FR-SERVICEBUS)

**FR-SERVICEBUS-1**: The system shall monitor Azure Service Bus Namespaces.

**FR-SERVICEBUS-2**: The system shall collect the following metrics per queue:
- **Incoming Requests**: Number of incoming messages/requests
- **Server Errors**: Number of server errors (5xx)
- **Deadletter Messages**: Number of messages in deadletter queue
- **Active Messages**: Number of active messages in queue
- **Size**: Size of messages in queue (in bytes)

**FR-SERVICEBUS-3**: Service Bus namespace shall be identified by:
- Subscription ID, Resource Group name, and Service Bus namespace name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components

**FR-SERVICEBUS-4**: Queue selection shall be configurable:
- Monitor all queues (empty value "" in configuration)
- Monitor specific queue(s) (list queue names in configuration)
- Queues with problems are listed in message in response

**FR-SERVICEBUS-5**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.

**FR-SERVICEBUS-6**: Output shall include performance data in Checkmk format with thresholds (metric name can be overwriten by JSON configuration file):
- `servicebus_incoming_requests=<value>;warn;crit;min;max|servicebus_server_errors=<value>;warn;crit;min;max|servicebus_deadletter_messages=<value>;warn;crit;min;max|servicebus_active_messages=<value>;warn;crit;min;max|servicebus_size=<value>;warn;crit;min;max`

**FR-SERVICEBUS-7**: Queue name shall be included in service name or metric name for identification.

**FR-SERVICEBUS-8**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file

**FR-SERVICEBUS-9**: Topics and Subscriptions are out of scope for initial version (only Queues supported).

### 5.9 Secrets and Certificates Monitoring (FR-SECRETS)

**FR-SECRETS-1**: The system shall monitor expiration dates of secrets and certificates for Azure App Registrations.

**FR-SECRETS-2**: The system shall check:
- Application secrets (client secrets)
- Application certificates

**FR-SECRETS-3**: App Registration shall be identified by:
- Application (client) ID or
- Application display name

**FR-SECRETS-4**: The system shall calculate days until expiration for each secret/certificate.

**FR-SECRETS-5**: Configuration shall include:
- `expiration_threshold`: Number of days until expiration threshold (required field)
- This threshold is used to determine if secrets/certificates are expiring soon

**FR-SECRETS-6**: Status determination:
- The system shall count the number of applications that have secrets/certificates with expiration time lower than the configured `expiration_threshold`
- **OK**: Zero or one application has expiring secrets/certificates
- **CRIT**: More than one application has expiring secrets/certificates (count > 1)

**FR-SECRETS-7**: Output message shall include:
- Names of applications that have expiring secrets/certificates
- Number of days until expiration for each application
- Format: "app_name1 (X days) ; app_name2 (Y days)"

**FR-SECRETS-8**: The system shall support monitoring multiple App Registrations in a single check.

**FR-SECRETS-9**: Performance data shall include:
- `secret_expiration_days=<count>;0;1;0;max|certificate_expiration_days=<count>;0;1;0;max`
- Where `<count>` is the number of applications with expiring secrets/certificates
- Thresholds: warn=0, crit=1 (CRIT if count > 1)

### 5.10 Azure Kubernetes Service (AKS) Monitoring (FR-AKS)

**FR-AKS-1**: The system shall monitor Azure Kubernetes Service (AKS) clusters for node metrics.

**FR-AKS-2**: The system shall collect the following metrics:
- **Not Ready Nodes**: Number of nodes in NotReady state
- **Node CPU Percentage**: Average CPU usage percentage across all nodes
- **Node Memory Percentage**: Average memory usage percentage across all nodes
- **Node Disk Usage**: Average disk usage percentage across all nodes

**FR-AKS-3**: AKS cluster shall be identified by:
- Subscription ID, Resource Group name, and AKS cluster name (resource_name) - **preferred method**
- The system automatically constructs the full Azure resource ID from these components during configuration loading

**FR-AKS-4**: Metrics shall be retrieved using `azure-monitor-querymetrics` SDK.
- Location has to be given in JSON configuration file
- Metrics endpoint format: `https://<region>.metrics.monitor.azure.com`

**FR-AKS-5**: Metrics shall be retrieved for a configurable time period (default: last 1 hour).
- Granularity is initially set to the same value as timespan. When querying Azure Monitor, granularity is automatically capped at 1 day (PT1D) by the base monitor class, as Azure Monitor does not support granularity longer than 1 day.

**FR-AKS-6**: Node-level metrics may be aggregated across all nodes or reported per node (configurable via `group_by_metadata` option).
- When `group_by_metadata` is enabled, metrics are grouped by node name
- Problematic nodes are reported as `MetricProblem` instances in the result
- Status messages include problematic node names when thresholds are exceeded

**FR-AKS-7**: Output shall include performance data in Checkmk format with thresholds (metric name can be overwritten by JSON configuration file):
- `aks_not_ready_nodes=<value>;warn;crit;min;max|aks_node_cpu_percent=<value>;warn;crit;0;100|aks_node_memory_percent=<value>;warn;crit;0;100|aks_node_disk_percent=<value>;warn;crit;0;100`

**FR-AKS-8**: Status determination:
When threshold is not configured:
- "0" - OK: All metrics within normal ranges
- "1" - WARN: Metrics exceed warning threshold
- "2" - CRIT: Metrics exceed critical threshold
- "3" - UNKNOWN: Error occurred
When threshold is configured:
- "P" - status will be calculated dynamically by checkmk (if any metric has thresholds defined)
- "3" - UNKNOWN: Error occurred
Always:
- Thresholds shall be configurable in JSON configuration file
- When multiple nodes are monitored and thresholds are exceeded, status messages shall identify problematic nodes
- Message format for problematic nodes: `"Problems: Node: node1 (value1) ; node2 (value2)"` (metadata key prefix is included in the message)
- Overall status shall be determined by the worst status across all metrics (CRIT > WARN > OK)

**FR-AKS-9**: The system shall support monitoring node pool filtering:
- `node_pools`: Optional array of node pool names to filter by
- Empty array or missing field means all node pools are monitored
- When node pools are specified, metrics are filtered to only those node pools

### 5.11 JSON Configuration System (FR-CONFIG)

**FR-CONFIG-1**: All monitoring checks shall be configured using JSON configuration files.

**FR-CONFIG-2**: Each local check shall have one JSON configuration file.

**FR-CONFIG-3**: Configuration file structure shall include:
- Resource type identifier
- Resource identification (subscription_id, resource_group, resource_name) - **preferred method**
  - The system automatically constructs the full Azure resource ID from these components based on resource type during configuration loading
- Common configuration (applies to all metrics unless overridden):
  - Time range (required: ISO 8601 duration format, e.g., PT1H, PT5M, PT1D) - used for both time range and granularity
  - Aggregation type (required: average, sum, count, min, max)
  - API IDs (for APIM resources, optional: empty array means all APIs)
- Metrics to monitor (object where keys are Checkmk metric names):
  - Each metric entry must have a "type" field (required) identifying the metric type
  - Metric type determines which monitoring function is called
  - Multiple metrics can use the same type with different names
  - Metric name (key) is used directly in Checkmk output
- Metric-specific configurations (can override common settings):
  - Type (required: identifies metric type, e.g., "request_count", "capacity", "transactions")
  - Thresholds (warn, crit, min, max values)
  - Time range (optional: overrides common time_range)
  - Aggregation type (optional: overrides common aggregation)
  - API IDs (optional: overrides common api_ids for APIM)
  - Filters (queue names, file names, response codes, etc.)
- Output configuration (service names, aggregation options)

**FR-CONFIG-4**: Configuration files shall be validated against JSON schemas before execution.

**FR-CONFIG-5**: Configuration templates shall be provided for each Azure resource type in `configs/templates/` directory.

**FR-CONFIG-6**: JSON schemas shall be provided for validation in `configs/schemas/` directory.

**FR-CONFIG-7**: Configuration shall support all configurable options for each resource type:
- Metric selection (enable/disable specific metrics)
- Common configuration at top level:
  - Time range (required: ISO 8601 duration format, used for both time range and granularity)
  - Aggregation type (required: average, sum, count, min, max)
  - API IDs (for APIM resources, optional: empty array means all APIs)
- Metrics object structure:
  - Keys are Checkmk metric names (required, used directly in output)
  - Each metric must have a "type" field (required) identifying the metric type
  - Supported types vary by resource type (e.g., APIM: "request_count", "requests_2xx", "requests_4xx", "requests_5xx", "requests_by_codes")
  - Multiple metrics can share the same type but have different names
- Metric-specific overrides:
  - Type (required: identifies metric type)
  - Thresholds (warn, crit, min, max values)
  - Time range (optional: overrides common time_range)
  - Aggregation type (optional: overrides common aggregation)
  - API IDs (optional: overrides common api_ids for APIM)
  - Filters (queue names, file names, response codes, etc.) 

**FR-CONFIG-8**: If a metric is not configured in JSON or does not exist, it shall not be called/executed.

**FR-CONFIG-9**: Configuration validation errors shall return UNKNOWN status (3) with descriptive error message.

**FR-CONFIG-10**: Some options may be defined in two levels - in root level and then in specific metric definition (for example time_range). Value defined in metric definition has always bigger priority.

### 5.12 Generic Check Script (FR-GENERIC)

**FR-GENERIC-1**: A generic check script (`generic_check.py`) shall be the main entry point for all local checks.

**FR-GENERIC-2**: The generic script shall accept JSON configuration file path as command-line argument.

**FR-GENERIC-3**: The generic script shall:
- Read JSON configuration without validation
- Identify resource type from configuration
- Route to appropriate resource-specific monitor module (module has to return result as MetricResult class from `checkmk_formatter.py`)
- Call only functions/metrics specified in configuration
- Format and output results in Checkmk format

**FR-GENERIC-4**: Resource-specific monitor modules shall contain separate functions for each metric/feature and return result as MetricResult class.

**FR-GENERIC-5**: Functions shall be called dynamically based on configuration file content.

**FR-GENERIC-6**: The generic script support returning single Checkmk service line with single or multiple metrics:
- Metric name is the key in the `metrics` object in the configuration file (e.g., `"apim_request_count"` is the metric name used in Checkmk output)
- When any threshold is defined for metrics then status always has value "P" or "3" (only for errors)

### 5.13 Configuration Generator Tool (FR-GENERATOR)

**FR-GENERATOR-1**: A configuration generator tool shall be provided in both CLI and web-based forms.

**FR-GENERATOR-2**: CLI tool (`config_generator.py`) shall support:
- Interactive configuration building
- Template-based configuration generation
- Configuration validation
- Command-line arguments for non-interactive generation

**FR-GENERATOR-3**: Web-based generator (part of Web GUI) shall support:
- Interactive form-based configuration
- Template selection and customization
- Real-time validation feedback
- Configuration download

**FR-GENERATOR-4**: Generator shall use templates from `configs/templates/` directory.

**FR-GENERATOR-5**: Generator shall validate configurations using JSON schemas.

**FR-GENERATOR-6**: Generator shall support editing existing configurations by uploading JSON files.

### 5.14 Web GUI (FR-WEBGUI)

**FR-WEBGUI-1**: A web-based GUI shall be developed using Flutter framework.

**FR-WEBGUI-2**: Web GUI shall be a standalone service with Azure AD authentication.

**FR-WEBGUI-3**: Authentication:
- Users shall authenticate using Azure AD
- Application shall use authenticated user's Azure permissions for resource discovery
- Session management for authenticated users

**FR-WEBGUI-4**: Resource Discovery:
- Discover Azure resources using Azure Resource Graph API
- Cache resource list for performance
- Provide refresh option to clear cache and reload resources
- Filter resources by type, subscription, resource group

**FR-WEBGUI-5**: Configuration Generation:
- Interactive form for each resource type
- Load resource names from Azure based on user permissions
- Select metrics to monitor
- Configure thresholds, filters, and options
- Real-time validation feedback

**FR-WEBGUI-6**: Configuration Management:
- Generate new configurations
- Upload and edit existing configuration files
- Validate uploaded configurations
- Display configuration in formatted view
- Copy configuration to clipboard
- Download configuration as JSON file

**FR-WEBGUI-7**: User Interface:
- Modern, responsive design
- Resource type selection
- Step-by-step configuration wizard
- Clear error messages and validation feedback
- Help text and tooltips for configuration options

**FR-WEBGUI-8**: Web GUI shall not require unit or integration testing (focus on Python scripts only).

### 5.15 Checkmk Integration (FR-CHECKMK)

**FR-CHECKMK-1**: All local check scripts shall output in Checkmk-compatible format:
```
<status> <check_name> <metrics> <message>
```

Where:
- `<status>`: P=Calculated dynamically (when any threshold is defined), 0=OK, 1=WARN, 2=CRIT, 3=UNKNOWN
- `<check_name>`: Descriptive check name
- `<message>`: Human-readable status message
- `<metrics>`: Pipe-separated (`|`) key=value pairs with optional thresholds (for example requests=40;10;50;0;100)

**FR-CHECKMK-2**: Metrics data format:
```
metric_name=value;warn;crit;min;max
```

**FR-CHECKMK-3**: Scripts shall support single output line:
- Lines may contain single or multiple metrics
- Example: `0 "APIM - API1" requests=100 | apim_requests=100;50;100`
- Example: `P "APIM - API2" requests=200;100;300 | apim_requests=200;50;100;0;1000`

**FR-CHECKMK-4**: Local check scripts shall be executable shell scripts.

**FR-CHECKMK-5**: Local check scripts shall use the Python interpreter from virtual environment.

**FR-CHECKMK-6**: Local check scripts shall handle errors gracefully and return appropriate Checkmk status codes.

**FR-CHECKMK-7**: Local check scripts shall accept JSON configuration file path as parameter:
```bash
#!/bin/bash
/opt/scripts/venv/bin/python /opt/scripts/generic_check.py /path/to/config.json
```

**FR-CHECKMK-8**: Thresholds (warn, crit, min, max) shall be included in performance data when configured.

**FR-CHECKMK-9**: When any threshold is configured then status always has value "P" and is calculated automatically by checkmk.

## 6. Non-Functional Requirements

### 6.1 Performance (NFR-PERF)

**NFR-PERF-1**: Each check execution shall complete within 30 seconds under normal conditions.

**NFR-PERF-2**: Scripts shall handle Azure API rate limiting gracefully.

**NFR-PERF-3**: Scripts shall implement appropriate timeouts for Azure API calls (default: 30 seconds).

**NFR-PERF-4**: Metrics shall be executed synchronous operations.

### 6.2 Reliability (NFR-REL)

**NFR-REL-1**: Scripts shall handle network failures gracefully and return UNKNOWN status.

**NFR-REL-2**: Scripts shall validate input parameters and return appropriate error messages.

**NFR-REL-3**: Authentication errors shall be logged with sufficient detail for troubleshooting.

**NFR-REL-4**: Error handling shall be implemented to ensure proper error reporting:
- Exceptions should propagate from the `monitor()` method to the caller (`generic_check.py`)
- Do not catch exceptions in metric execution - let them propagate naturally
- The `generic_check.py` script handles all exceptions and outputs status 3 (UNKNOWN) with generic error messages
- **Exception Logging vs. Checkmk Output:**
  - Exception details (including stack traces, error messages, and context) are logged to files via `ExceptionLogger.log_exception()` for troubleshooting
  - Exception details are NOT included in Checkmk output to keep output clean and avoid exposing sensitive information
  - Checkmk output contains only generic error messages (e.g., "Configuration validation error", "Authentication error")
  - Full exception details are available in log files located in `logs/` directory, organized by service name
- Traceback information may be printed to stderr for debugging purposes when `debug=True`

### 6.3 Security (NFR-SEC)

**NFR-SEC-1**: Service Principal credentials shall never be logged or exposed in output.

**NFR-SEC-2**: Scripts shall use secure methods for credential storage (environment variables).

**NFR-SEC-3**: Virtual environment shall be properly isolated from system Python.

**NFR-SEC-4**: Scripts shall follow principle of least privilege (request only necessary Azure permissions).

### 6.4 Maintainability (NFR-MAIN)

**NFR-MAIN-1**: Code shall be modular and well-documented.

**NFR-MAIN-2**: Dependencies shall be clearly specified in `requirements.txt`.

**NFR-MAIN-3**: Setup process shall be automated via `setup.sh` script.

**NFR-MAIN-4**: Error messages shall be descriptive and actionable.

### 6.5 Compatibility (NFR-COMP)

**NFR-COMP-1**: Scripts shall support Python 3.9 or higher.

**NFR-COMP-2**: Scripts shall use Azure SDK libraries compatible with current Azure API versions.

**NFR-COMP-3**: Local check scripts shall be compatible with standard Checkmk agent (Linux/Unix).

## 7. Technical Specifications

### 7.1 Python Dependencies

Required Python packages:
- `azure-identity>=1.15.0` - Azure authentication
- `azure-monitor-querymetrics>=1.0.0` - **Primary SDK for querying Azure Monitor metrics**
- `azure-mgmt-resourcegraph>=10.0.0` - Azure Resource Graph queries for resource discovery
- `azure-mgmt-storage>=21.0.0` - Storage account management
- `azure-storage-blob>=12.19.0` - Blob storage operations
- `azure-mgmt-containerinstance>=9.0.0` - Container Apps operations
- `azure-mgmt-compute>=30.0.0` - Virtual Machine Scale Sets operations
- `azure-servicebus>=7.11.0` - Service Bus operations
- `azure-mgmt-graph>=0.1.0` or `azure-graphrbac>=0.61.1` - App Registration access
- `msal>=1.24.0` - Microsoft Authentication Library (for Graph API)
- `jsonschema>=4.0.0` - JSON schema validation
- `pytest>=7.0.0` - Testing framework (for development)
- `pytest-mock>=3.10.0` - Mocking support for tests

### 7.1.1 SDK Selection Strategy

**FR-SDK-1**: The system shall use `azure-monitor-querymetrics` SDK for all metric queries.

**FR-SDK-2**: SDK usage shall be transparent to configuration files (handled internally by monitor modules).

**FR-SDK-3**: For `azure-monitor-querymetrics` SDK:
- Region is loaded from configuration file
- Endpoint format: `https://<region>.metrics.monitor.azure.com`
- API breakdown data shall be extracted from metadata_values in response timeseries

### 7.2 Azure Permissions Required

Service Principal or authenticated user shall have the following Azure RBAC roles/permissions:

**For APIM Monitoring:**
- `Reader` role on API Management service
- `Monitoring Reader` role (for metrics)

**For Storage Account Monitoring:**
- `Monitoring Reader` role on storage account (for metrics)
- `Storage Account Contributor` or `Reader` role (for account information)

**For Storage Blob Monitoring:**
- `Monitoring Reader` role on storage account (for metrics)
- `Storage Blob Data Reader` role on storage account (for file operations)

**For Storage Table Monitoring:**
- `Monitoring Reader` role on storage account (for metrics)
- `Storage Table Data Reader` role on storage account (for table operations)

**For Container Apps Monitoring:**
- `Reader` role on Container App
- `Monitoring Reader` role (for metrics)

**For Virtual Machine Scale Sets Monitoring:**
- `Reader` role on VM Scale Set
- `Monitoring Reader` role (for metrics)

**For Service Bus Monitoring:**
- `Reader` role on Service Bus namespace
- `Monitoring Reader` role (for metrics)
- `Azure Service Bus Data Receiver` role (for queue operations, if needed)

**For Secrets/Certificates Monitoring:**
- `Application.Read.All` Microsoft Graph API permission
- Or appropriate permissions to read App Registration details

**For Resource Discovery (Web GUI):**
- `Reader` role on subscriptions or resource groups to discover resources
- Azure Resource Graph query permissions

### 7.3 Checkmk Local Check Script Format

Example local check script structure (generic approach):
```bash
#!/bin/bash
# Checkmk local check for Azure resources (generic)

PYTHON_SCRIPT="/opt/scripts/src/azurechecks/generic_check.py"
PYTHON_VENV="/opt/scripts/venv/bin/python"
CONFIG_FILE="/opt/scripts/configs/my_apim_check.json"

# Execute generic Python script with configuration file
$PYTHON_VENV $PYTHON_SCRIPT "$CONFIG_FILE"
```

### 7.4 JSON Configuration File Format

Example JSON configuration file structure:
```json
{
  "resource_type": "apim",
  "location": "<location>",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<apim-name>",
  "time_range": "PT1H",
  "aggregation": "sum",
  "api_ids": ["api-id-1", "api-id-2"],
  "metrics": {
    "apim_request_count": {
      "type": "request_count",
      "enabled": true,
      "warn_threshold": 100,
      "crit_threshold": 500,
      "min": 0,
      "max": null
    },
    "apim_requests_2xx": {
      "type": "requests_2xx",
      "enabled": true,
      "warn_threshold": null,
      "crit_threshold": null,
      "min": 0,
      "max": null
    },
    "apim_requests_4xx": {
      "type": "requests_4xx",
      "enabled": true,
      "warn_threshold": 10,
      "crit_threshold": 50,
      "min": 0,
      "max": null
    },
    "apim_requests_5xx": {
      "type": "requests_5xx",
      "enabled": true,
      "warn_threshold": 5,
      "crit_threshold": 20,
      "min": 0,
      "max": null
    },
    "apim_errors": {
      "type": "requests_by_codes",
      "enabled": true,
      "response_codes": ["200", "201", "404", "500"],
      "warn_threshold": null,
      "crit_threshold": null,
      "min": 0,
      "max": null
    }
  }
}
```

**Configuration Field Definitions:**
- **location** (required): Azure metric endpoint region
- **subscription_id** (required): Azure subscription ID where the resource is located.
- **resource_group** (required): Azure resource group name containing the resource.
- **resource_name** (required): Name of the Azure resource (e.g., APIM service name, Storage account name, Container App name). The system automatically constructs the full Azure resource ID from these components based on the resource type during configuration validation.
- **time_range** (common): Defines the time period for metric queries and is also used as granularity. Format: ISO 8601 duration format (e.g., `"PT1H"` for 1 hour, `"PT5M"` for 5 minutes, `"PT1D"` for 1 day). Required at top level. Can be overridden per metric. Consistent with Azure Monitor API format.
- **aggregation** (common): Defines how metric values are aggregated. Options: `"average"`, `"sum"`, `"count"`, `"min"`, `"max"`. Required at top level. Can be overridden per metric.
- **api_ids** (common, APIM only): Array of API IDs to monitor. Empty array `[]` means all APIs are monitored. Can be overridden per metric. API IDs must be provided directly as they appear in Azure Monitor metrics (ApiId dimension).

### 7.5 Generic Script CLI Interface

The generic check script shall support:
```bash
python src/azurechecks/generic_check.py <config_file_path>
```

Where:
- `<config_file_path>`: Path to JSON configuration file

The script shall:
1. Read JSON configuration (without validation)
2. Identify resource type
3. Route to appropriate monitor module
4. Execute only enabled metrics from configuration
5. Output Checkmk format (single service line with potentially multiple metrics)

## 8. Deployment Requirements

### 8.1 Prerequisites

**For Checkmk Server:**
- Checkmk server with Linux/Unix operating system
- Python 3.9 or higher installed
- Network access to Azure APIs
- Service Principal created in Azure AD with appropriate permissions
- Checkmk agent configured to execute local checks

**For Web GUI:**
- Web server or hosting platform for Flutter web application
- Azure AD App Registration for authentication
- Network access to Azure APIs from web server
- Modern web browser for users

### 8.2 Installation Steps

**8.2.1 Checkmk Scripts Installation:**

1. Copy project root directory to `/opt/scripts/` on Checkmk server (or copy `src/`, `configs/`, `tools/`, and `requirements.txt`)
2. Create virtual environment: `python3 -m venv venv`
3. Install dependencies: `venv/bin/pip install -r requirements.txt`
4. Set environment variables for Azure authentication (Service Principal)
5. Copy configuration files to `/opt/scripts/configs/` directory (or use existing `configs/` directory)
6. Copy local check script (`tools/azure_check`) to Checkmk local checks directory (`/usr/lib/check_mk_agent/local/`)
7. Update paths in `azure_check` script if needed (defaults assume project structure is preserved)
8. Make local check script executable (`chmod +x`)
9. Create JSON configuration files for each check
10. Test each check individually with configuration files
11. Configure Checkmk to recognize new local checks

**8.2.2 Web GUI Installation:**

*Note: Web GUI is not implemented in the current version. This section is reserved for future implementation.*

When implemented, installation steps will include:
1. Build Flutter web application
2. Deploy to web server or hosting platform
3. Configure Azure AD App Registration for authentication
4. Set up environment variables for Azure authentication
5. Configure CORS if needed
6. Test authentication and resource discovery
7. Verify configuration generation and download functionality

### 8.3 Configuration

**8.3.1 Service Principal Authentication (for Checkmk scripts):**

Environment variables to set (e.g., in `/etc/environment` or service configuration):
```bash
export AZURE_CLIENT_ID="<client-id>"
export AZURE_CLIENT_SECRET="<client-secret>"
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_SUBSCRIPTION_ID="<subscription-id>"
```

**8.3.2 Azure AD Authentication (for Web GUI):**

Azure AD App Registration configuration:
- Application (client) ID
- Directory (tenant) ID
- Redirect URIs for web application
- API permissions for Azure Resource Graph and Monitor APIs

**8.3.3 JSON Configuration Files:**

- Create configuration files in `/opt/scripts/configs/` directory (or use existing `configs/` directory)
- Use templates from `configs/templates/` as starting point
- Validate configurations using JSON schemas before deployment (use `tools/config_validation` or `src/validation/validate_config.py`)
- Each local check requires one JSON configuration file

**8.3.4 Local Check Script Configuration:**

Each local check script shall reference its configuration file:
```bash
#!/bin/bash
/opt/scripts/venv/bin/python /opt/scripts/src/azurechecks/generic_check.py /opt/scripts/configs/my_check.json
```

## 9. Testing Requirements

**Note**: For comprehensive test requirements, use cases, mock response structures, and detailed test scenarios, see the [Test Requirements Document](tests-prd.md).

### 9.1 Unit Testing

**9.1.1 Mocking Strategy:**
- All Azure SDK responses shall be mocked using `unittest.mock` or `pytest-mock`
- Mock responses shall simulate real Azure SDK response structures
- Each resource monitor module shall have comprehensive unit tests

**9.1.2 Unit Test Coverage:**
- Authentication module: valid/invalid credentials, token refresh scenarios
- Each monitoring module: all metric collection functions
- Configuration validator: valid/invalid JSON configurations
- Checkmk formatter: output format correctness, threshold application
- Error handling: network failures, authentication errors, invalid responses, missing metrics

**9.1.3 Test Cases:**
- Valid metric queries with various aggregation types
- Missing or disabled metrics (should not be called)
- Invalid subscription IDs, resource groups, or resource names
- Threshold evaluation (OK, WARN, CRIT states)
- Multiple service line generation
- Performance data formatting with thresholds

**9.1.4 Mock Response Structure:**
- Mock responses shall match actual Azure SDK response structures
- Example: `MetricsQueryResult` with `metrics`, `timeseries`, `data` structures
- Mock responses shall include edge cases (empty data, null values, etc.)

### 9.2 Integration Testing

**9.2.1 Real Azure Resources:**
- End-to-end tests with real Azure resources in test subscription
- Test with various Azure resource configurations
- Verify actual Azure API responses are handled correctly

**9.2.2 Integration Test Coverage:**
- Authentication with real Service Principal
- Metric queries against real Azure resources
- File operations against real Storage accounts
- Resource discovery via Azure Resource Graph
- Checkmk output format validation with real data

**9.2.3 Test Environment:**
- Dedicated test Azure subscription
- Test resources for each resource type
- Test Service Principal with appropriate permissions
- Isolated test data to avoid affecting production

**9.2.4 Integration Test Scenarios:**
- Complete check execution flow (config → Azure → Checkmk output)
- Multiple resource types in sequence
- Error scenarios with real Azure (rate limiting, permissions, etc.)
- Performance validation (<30 seconds execution time)

### 9.3 Test Execution

**9.3.1 Unit Tests:**
- Shall run without Azure connectivity
- Shall use mocked responses exclusively
- Shall be fast (<1 second per test)
- Shall be runnable in CI/CD pipeline

**9.3.2 Integration Tests:**
- May require Azure connectivity and credentials
- Shall use real Azure resources
- May be slower (depends on Azure API response times)
- May be run manually or in dedicated test environment

**9.3.3 Test Organization:**
- Unit tests in `tests/unit/` directory
- Integration tests in `tests/integration/` directory
- Test fixtures and mocks in `tests/fixtures/` directory
- Test configuration separate from production configuration

### 9.4 Acceptance Criteria

- All resource monitoring types function correctly (APIM, Storage, Storage Blob, Storage Table, Container Apps, VMSS, Service Bus, Secrets)
- All unit tests pass with mocked responses
- All integration tests pass with real Azure resources (when available)
- Checkmk successfully parses output from all checks
- Scripts handle errors gracefully with appropriate status codes
- Performance meets requirements (<30 seconds execution time)
- Configuration validation works correctly
- Multiple service lines are generated correctly when configured
- Documentation is complete and accurate
- Code coverage meets minimum threshold (target: 80%+)
- All aggregation types (sum, average, count, min, max) are tested
- Edge cases are covered (empty data, None values, last data point with all None fields)
- Metadata grouping and breakdown scenarios are tested
- Checkmk message format validation passes for all scenarios

**For detailed test requirements, see [Test Requirements Document](tests-prd.md).**

## 10. Future Enhancements (Out of Scope for Initial Version)

- Support for additional Azure resources:
  - Azure Functions
  - Azure App Services
  - Azure Key Vault
  - Azure Cosmos DB
  - Azure SQL Database
  - Azure Kubernetes Service (AKS)
- Service Bus Topics and Subscriptions monitoring (currently only Queues)
- Caching mechanism to reduce API calls and improve performance
- Support for Managed Identity authentication (in addition to Service Principal)
- Multi-subscription monitoring in single configuration
- Historical trending and comparison beyond Checkmk's native capabilities
- Configuration versioning and change tracking
- Bulk configuration generation for multiple resources
- Configuration templates marketplace/sharing
- Support for Azure Government and Azure China clouds
- Advanced filtering and aggregation options
- Custom metric calculations and derivations
- Alerting integration beyond Checkmk (e.g., email, webhooks)

## 11. Dependencies and Assumptions

### 11.1 Dependencies

- Azure Python SDK availability and stability
- Checkmk local check mechanism
- Network connectivity to Azure APIs
- Valid Azure subscription and Service Principal

### 11.2 Assumptions

- Checkmk server has internet access or network path to Azure APIs
- Service Principal has been created and configured with appropriate permissions
- Azure resources (APIM, Storage, App Registrations) already exist
- Checkmk administrator has shell access to configure local checks
- Python 3.8+ is available on the system

## 12. Risk Assessment

### 12.1 Technical Risks

- **Azure API changes**: Azure SDK updates may require code changes
  - *Mitigation*: Pin dependency versions, monitor Azure SDK release notes

- **Rate limiting**: Azure APIs may throttle requests
  - *Mitigation*: Implement retry logic with exponential backoff

- **Authentication failures**: Service Principal credentials may expire
  - *Mitigation*: Clear error messages, documentation on credential rotation

### 12.2 Operational Risks

- **Dependency conflicts**: System Python packages may conflict with venv
  - *Mitigation*: Use isolated virtual environment

- **Performance degradation**: Slow Azure API responses
  - *Mitigation*: Implement timeouts, consider caching for future versions

## 13. Success Criteria

The solution is considered successful when:

1. All monitoring types are implemented and functional:
   - APIM (request counts, requests by response code categories 2xx/4xx/5xx, requests filtered by specific response codes, all with API ID filtering)
   - Storage Account (capacity, transactions with scope support for blob, table, queue, file)
   - Storage Blob (file existence, file modification date checks)
   - Storage Table (table existence checks)
   - Container Apps (restarts, CPU, memory, response time)
   - Virtual Machine Scale Sets (memory, CPU)
   - Service Bus (incoming requests, errors, deadletter, active messages per queue)
   - Secrets/Certificates (expiration monitoring)
   - AKS (not ready nodes, CPU, memory, disk usage)

2. JSON-based configuration system is fully functional:
   - All options are configurable via JSON
   - Configuration validation works correctly
   - Templates are available for all resource types
   - Generic script routes correctly based on configuration

3. Checkmk successfully receives and processes monitoring data:
   - Multiple service lines are generated correctly
   - Performance data includes thresholds (warn, crit, min, max)
   - Output format is Checkmk-compatible

4. Scripts execute reliably with <30 second execution time

5. Error handling provides actionable information with appropriate status codes

6. Unit tests pass with mocked Azure responses (80%+ code coverage)

7. Integration tests pass with real Azure resources (when available)

8. Web GUI is functional:
   - Azure AD authentication works
   - Resource discovery via Resource Graph works
   - Configuration generation and download works
   - Configuration validation works

9. Configuration generator tool (CLI) is functional:
   - Template-based generation works
   - Validation works
   - Interactive mode works

10. Documentation enables administrators to deploy and configure the solution

11. Code is maintainable, modular, and follows Python best practices

12. Solution is generic and extensible - adding new resource types or metrics is straightforward

## 14. Appendix

### 14.1 Checkmk Output Format Reference

Standard Checkmk output format:
```
<status_code> <service_name> - <plugin_output> | <performance_data>
```

Status codes:
- `0` = OK
- `1` = WARN
- `2` = CRIT
- `3` = UNKNOWN

Performance data example:
```
cpu_usage=85.5;90;95;0;100 memory=2048;4096;8192
```

### 14.2 Azure SDK Documentation References

- Azure Identity: https://learn.microsoft.com/python/api/azure-identity/
- Azure Monitor Query Metrics: https://learn.microsoft.com/python/api/azure-monitor-querymetrics/
- Azure Management Libraries: https://learn.microsoft.com/python/api/overview/azure/
- Azure Resource Graph: https://learn.microsoft.com/python/api/azure-mgmt-resourcegraph/
- Microsoft Graph API: https://learn.microsoft.com/graph/api/overview

### 14.3 Checkmk Local Checks Documentation

- Checkmk Local Checks: https://docs.checkmk.com/latest/en/localchecks.html

### 14.4 JSON Configuration Examples

**Example: APIM Configuration**
```json
{
  "resource_type": "apim",
  "location": "<location>",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<apim-name>",
  "service_name": "Azure APIM - All APIs",
  "time_range": "PT1H",
  "aggregation": "sum",
  "api_ids": ["api-id-1", "694bdcf50cc46a2f0b5005a5"],
  "metrics": {
    "apim_request_count": {
      "type": "request_count",
      "enabled": true,
      "warn_threshold": 100,
      "crit_threshold": 500,
      "min": 0,
      "max": null
    },
    "apim_requests_2xx": {
      "type": "requests_2xx",
      "enabled": true,
      "warn_threshold": null,
      "crit_threshold": null,
      "min": 0,
      "max": null
    },
    "apim_requests_4xx": {
      "type": "requests_4xx",
      "enabled": true,
      "warn_threshold": 10,
      "crit_threshold": 50,
      "min": 0,
      "max": null
    },
    "apim_requests_5xx": {
      "type": "requests_5xx",
      "enabled": true,
      "warn_threshold": 5,
      "crit_threshold": 20,
      "min": 0,
      "max": null
    },
    "apim_errors": {
      "type": "requests_by_codes",
      "enabled": true,
      "response_codes": ["200", "201", "404", "500"],
      "warn_threshold": null,
      "crit_threshold": null,
      "min": 0,
      "max": null
    }
  }
}
```

**Note on APIM Configuration:**
- The `api_ids` array contains API IDs as they appear in Azure Monitor metrics
- API IDs are the actual identifiers used in Azure Monitor filter queries: `ApiId eq '<api_id>'`
- Empty `api_ids` array `[]` monitors all APIs (no filtering)
- If thresholds are exceeded, status messages will identify problematic APIs: `"Problems: ApiId: api1 (150) ; api2 (200)"` (metadata key prefix is included in the message)
- All metrics are executed sequentially (synchronous execution)
- API IDs can be found in Azure Portal or via APIM Management API
- **Metric names**: Keys in the `metrics` object are the Checkmk metric names used in output
- **Type field**: Each metric must have a `type` field identifying the metric type (e.g., "request_count", "requests_by_codes")
- **requests_by_codes**: Aggregates all status codes in `response_codes` array into a single metric value
- **Multiple same-type metrics**: You can define multiple metrics with the same type but different names
- When thresholds are defined, status will be "P" (calculated by Checkmk)

**Example: Storage Blob Configuration**
```json
{
  "resource_type": "storage_blob",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<account-name>",
  "container_name": "my-container",
  "service_name": "Blob Storage - File Monitoring",
  "metrics": {
    "file_exists": {
      "type": "file_existence",
      "enabled": true,
      "files": ["file1.txt", "file2.txt", "important.log"]
    },
    "file_freshness": {
      "type": "file_modification",
      "enabled": true,
      "files": ["backup.zip", "data.json"],
      "max_hours_since_modification": 24,
      "exceeded_status": "CRIT"
    }
  }
}
```

**Note**: For blob capacity and transaction monitoring, use the Storage Account monitor with `scope: "Blob"`:
```json
{
  "resource_type": "storage_account",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<account-name>",
  "location": "<location>",
  "metrics": {
    "blob_capacity": {
      "type": "capacity",
      "enabled": true,
      "scope": "Blob",
      "warn_threshold": 107374182400,
      "crit_threshold": 214748364800
    },
    "blob_transactions": {
      "type": "transactions",
      "enabled": true,
      "scope": "Blob",
      "aggregation": "sum"
    }
  }
}
```

**Example: Service Bus Configuration**
```json
{
  "resource_type": "servicebus",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<namespace-name>",
  "queues": "*",
  "time_range": "PT1H",
  "aggregation": "sum",
  "metrics": {
    "incoming_requests": {
      "enabled": true,
      "warn_threshold": 100,
      "crit_threshold": 500
    },
    "server_errors": {
      "enabled": true,
      "warn_threshold": 5,
      "crit_threshold": 20
    },
    "deadletter_messages": {
      "enabled": true,
      "aggregation": "average",
      "warn_threshold": 10,
      "crit_threshold": 50
    },
    "active_messages": {
      "enabled": true,
      "aggregation": "average",
      "warn_threshold": 1000,
      "crit_threshold": 5000
    }
  }
}
```

**Example: AKS Configuration**
```json
{
  "resource_type": "aks",
  "location": "<location>",
  "subscription_id": "<sub-id>",
  "resource_group": "<rg>",
  "resource_name": "<aks-cluster-name>",
  "service_name": "Azure AKS - Node Monitoring",
  "time_range": "PT1H",
  "filter_metadata_values": [""]
  "metrics": {
    "aks_not_ready_nodes": {
      "type": "not_ready_nodes",
      "enabled": true,
      "warn_threshold": 0,
      "crit_threshold": 1,
      "min": 0,
      "max": null
    },
    "aks_node_cpu_percent": {
      "type": "node_cpu_percent",
      "enabled": true,
      "aggregation": "average",
      "group_by_metadata": "node",
      "warn_threshold": 80,
      "crit_threshold": 95,
      "min": 0,
      "max": 100
    },
    "aks_node_memory_percent": {
      "type": "node_memory_percent",
      "aggregation": "average",
      "group_by_metadata": "node",
      "enabled": true,
      "warn_threshold": 85,
      "crit_threshold": 95,
      "min": 0,
      "max": 100
    },
    "aks_node_disk_percent": {
      "type": "node_disk_percent",
      "aggregation": "average",
      "group_by_metadata": "node",
      "enabled": true,
      "warn_threshold": 80,
      "crit_threshold": 90,
      "min": 0,
      "max": 100
    }
  }
}
```

**Note on AKS Configuration:**
- **Metric types**: `not_ready_nodes`, `node_cpu_percent`, `node_memory_percent`, `node_disk_percent`
- **Metric names**: Keys in the `metrics` object are the Checkmk metric names used in output
- When thresholds are defined, status will be "P" (calculated by Checkmk)

### 14.5 Azure Monitor Metrics Reference

Common metric names used across resource types:
- **Capacity metrics**: `UsedCapacity`, `Capacity`
- **Transaction metrics**: `Transactions`, `Ingress`, `Egress`
- **Request metrics**: `Requests`, `RequestCount`, `FailedRequests`
- **Performance metrics**: `ResponseTime`, `Latency`, `Duration`
- **Resource metrics**: `CpuPercentage`, `MemoryPercentage`, `AvailableMemory`

Metric namespaces:
- `Microsoft.Storage/storageAccounts` - Storage accounts
- `Microsoft.ApiManagement/service` - API Management
- `Microsoft.App/containerApps` - Container Apps
- `Microsoft.Compute/virtualMachineScaleSets` - VM Scale Sets
- `Microsoft.ServiceBus/namespaces` - Service Bus
- `Microsoft.ContainerService/managedClusters` - Azure Kubernetes Service (AKS)

### 14.5.1 APIM Monitoring Implementation Details

**API Breakdown and Problematic API Identification:**
- Metrics queries return both aggregated values and per-API breakdown data
- API breakdown is extracted from timeseries metadata (ApiId dimension)
- When thresholds are exceeded and multiple APIs are monitored, the system identifies which specific APIs are problematic
- Problematic APIs are determined by evaluating each API's metric value against thresholds
- Status messages include problematic API names with their values: `"Problems: ApiId: api1 (value1) ; api2 (value2)"` (metadata key prefix is included in the message)

**Metrics Endpoint Determination:**
- APIM service location is retrieved from APIM Management API
- Location is used to construct metrics endpoint: `https://<location>.metrics.monitor.azure.com`
- Endpoint is required for `azure-monitor-querymetrics` SDK initialization

**Resource Identification:**
- Configuration files use separate fields: `subscription_id`, `resource_group`, `resource_name`
- The system automatically constructs the full Azure resource ID from these fields during configuration validation
- Resource ID format varies by resource type (e.g., `/subscriptions/{id}/resourceGroups/{rg}/providers/Microsoft.ApiManagement/service/{name}`)
- The `resource_id` is always built internally from subscription_id, resource_group, and resource_name
- This approach simplifies configuration and reduces errors from manual resource ID construction

**API ID Usage:**
- Users must provide API IDs directly in the `api_ids` array
- API IDs are the identifiers used in Azure Monitor metrics (ApiId dimension)
- API IDs can be found in Azure Portal or via APIM Management API
- Empty `api_ids` array `[]` means all APIs are monitored
- All API IDs are used directly in Azure Monitor filter queries: `ApiId eq '<api_id>'`

### 14.6 Configuration Field Reference

**Time Range Format (ISO 8601 Duration):**
- Format: ISO 8601 duration format `PT<N><unit>` where unit is `M` (minutes), `H` (hours), or `D` (days)
- Examples:
  - `"PT5M"` - 5 minutes
  - `"PT15M"` - 15 minutes
  - `"PT1H"` - 1 hour
  - `"PT6H"` - 6 hours
  - `"PT1D"` - 1 day
- Required at top level (common configuration)
- Used for both time range (query window) and granularity (data point interval)
- Can be overridden per metric if needed
- Not required for file operations (file_existence, file_modification) as they query blob storage directly
- Consistent with Azure Monitor API format

**Aggregation Types:**
- `"average"` - Average value across time range
- `"sum"` - Sum of all values in time range
- `"count"` - Count of data points
- `"min"` - Minimum value
- `"max"` - Maximum value
- Required at top level (common configuration)
- Can be overridden per metric if needed

**Metadata Aggregation:**
- `metadata_aggregation` - Optional aggregation type for combining grouped metadata values when `group_by_metadata` is used
- Valid values: `"average"`, `"sum"`, `"count"`, `"min"`, `"max"` (same as aggregation types)
- **Precedence order**: metric-level `metadata_aggregation` > root-level `metadata_aggregation` > `aggregation` field
- If not specified at any level, defaults to the `aggregation` field value
- Can be specified at root level (applies to all metrics) or per-metric (overrides root level)
- Use cases:
  - `"sum"` - For metrics like storage capacity where you want to sum values from all tiers/nodes
  - `"average"` - For metrics like CPU usage percentages where summing would be incorrect (e.g., 50% + 60% = 110%)
  - `"max"` - For metrics where you want the maximum value across grouped items
  - `"min"` - For metrics where you want the minimum value across grouped items

**Common Configuration:**
- Configuration supports common settings at the top level that apply to all metrics:
  - `time_range` - Required, used for both time range and granularity
  - `aggregation` - Required, aggregation type for all metrics
  - `metadata_aggregation` - Optional, aggregation type for combining grouped metadata values (defaults to `aggregation`)
  - `api_ids` - Optional (APIM only), array of API IDs (empty array = all APIs). API IDs must be provided directly as they appear in Azure Monitor metrics.
- Individual metrics can override common settings by specifying them in their metric configuration

### 14.7 Available Configuration Values by Resource Type

This section documents all available values that can be used in JSON configuration files for each monitoring module. These values are validated by JSON schemas in `configs/schemas/` directory.

#### 14.7.1 Azure API Management (APIM)

**Metric: Requests**
- **Azure Metric Name**: `Requests`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `ApiId` - Group by API identifier (default)
  - `GatewayResponseCodeCategory` - Group by response code category (2xx, 4xx, 5xx)
  - `GatewayResponseCode` - Group by specific HTTP response code (200, 404, 500, etc.)
- **Metric Types**:
  - `request_count` - Total request count (all response codes)
  - `requests_2xx` - Requests with 2xx response codes
  - `requests_4xx` - Requests with 4xx response codes
  - `requests_5xx` - Requests with 5xx response codes
  - `requests_by_codes` - Requests filtered by specific response codes (requires `response_codes` array)

#### 14.7.2 Azure Storage Account

**Metric: Capacity**
- **Azure Metric Name**: `UsedCapacity` (account-level) or `BlobCapacity`/`TableCapacity`/`QueueCapacity`/`FileCapacity` (service-level)
- **Unit**: `bytes`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `ApiName` - Group by API name
  - `OperationName` - Group by operation name
  - `Tier` - Group by storage tier (Hot, Cool, Archive)
  - Other metadata keys available in Azure Monitor metrics
- **Scope values**: `account`, `Blob`, `Table`, `Queue`, `File`
- **Metric Type**: `capacity`

**Metric: Transactions**
- **Azure Metric Name**: `Transactions`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `ApiName` - Group by API name
  - `OperationName` - Group by operation name
  - `Tier` - Group by storage tier
  - Other metadata keys available in Azure Monitor metrics
- **Scope values**: `account`, `Blob`, `Table`, `Queue`, `File`
- **Metric Type**: `transactions`

#### 14.7.3 Azure Storage Blob

**Metric: File Existence**
- **Unit**: `count` (count of missing files)
- **Metric Type**: `file_existence`
- **Configuration**: Requires `files` array with file paths to check

**Metric: File Modification**
- **Unit**: `hours` (hours since last modification)
- **Metric Type**: `file_modification`
- **Configuration**: Requires `files` array and optional `max_hours_since_modification` (default: 24)

#### 14.7.4 Azure Storage Table

**Metric: Table Existence**
- **Unit**: `count` (count of missing tables)
- **Metric Type**: `table_existence`
- **Configuration**: Requires `filtered_tables` array with table names to check

#### 14.7.5 Azure Container Apps

**Metric: Restarts**
- **Azure Metric Name**: `RestartCount`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `restarts`

**Metric: CPU Percentage**
- **Azure Metric Name**: `CpuUsage`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `cpu_percentage`

**Metric: Memory Percentage**
- **Azure Metric Name**: `MemoryWorkingSet`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `memory_percentage`

**Metric: Response Time**
- **Azure Metric Name**: `ResponseTime`
- **Unit**: `milliseconds`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `response_time`

#### 14.7.6 Azure Virtual Machine Scale Sets (VMSS)

**Metric: Available Memory Percentage**
- **Azure Metric Name**: `AvailableMemoryBytes`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `available_memory_percent`

**Metric: CPU Percentage**
- **Azure Metric Name**: `PercentageCPU`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Metric Type**: `cpu_percent`

#### 14.7.7 Azure Service Bus Namespace

**Metric: Incoming Requests**
- **Azure Metric Name**: `IncomingRequests`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `QueueName` - Group by queue name (default)
- **Metric Type**: `incoming_requests`

**Metric: Server Errors**
- **Azure Metric Name**: `ServerErrors`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `QueueName` - Group by queue name (default)
- **Metric Type**: `server_errors`

**Metric: Deadletter Messages**
- **Azure Metric Name**: `DeadletteredMessages`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `QueueName` - Group by queue name (default)
- **Metric Type**: `deadletter_messages`

**Metric: Active Messages**
- **Azure Metric Name**: `ActiveMessages`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `QueueName` - Group by queue name (default)
- **Metric Type**: `active_messages`

**Metric: Size**
- **Azure Metric Name**: `Size`
- **Unit**: `bytes`
- **Supported Aggregations**: `average`, `min`, `max`
- **Supported group_by_metadata values**:
  - `EntityName` - Group by queue name (default)
- **Metric Type**: `size`

#### 14.7.8 Azure Kubernetes Service (AKS)

**Metric: Not Ready Nodes**
- **Azure Metric Name**: `kube_node_status_condition`
- **Unit**: `count`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `node` - Group by node name
  - `nodepool` - Group by node pool name
- **Metric Type**: `not_ready_nodes`

**Metric: Node CPU Percentage**
- **Azure Metric Name**: `node_cpu_usage_percentage`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `node` - Group by node name (default)
  - `nodepool` - Group by node pool name
- **Metric Type**: `node_cpu_percent`

**Metric: Node Memory Percentage**
- **Azure Metric Name**: `node_memory_working_set_percentage`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `node` - Group by node name (default)
  - `nodepool` - Group by node pool name
- **Metric Type**: `node_memory_percent`

**Metric: Node Disk Usage**
- **Azure Metric Name**: `node_disk_usage_percentage`
- **Unit**: `percent`
- **Supported Aggregations**: `sum`, `max`, `min`, `average`, `count`
- **Supported group_by_metadata values**:
  - `node` - Group by node name (default)
  - `nodepool` - Group by node pool name
- **Metric Type**: `node_disk_percent`

#### 14.7.9 Azure App Registrations (Secrets)

**Metric: Secret Expiration**
- **Unit**: `count` (count of applications with expiring secrets)
- **Metric Type**: `secret_expiration_days`
- **Configuration**: Requires `expiration_threshold` (days until expiration)

**Metric: Certificate Expiration**
- **Unit**: `count` (count of applications with expiring certificates)
- **Metric Type**: `certificate_expiration_days`
- **Configuration**: Requires `expiration_threshold` (days until expiration)

#### 14.7.10 Common Aggregation Types

All metrics that query Azure Monitor support the following aggregation types:
- `sum` - Sum of all values in time range
- `average` - Average value across time range
- `count` - Count of data points
- `min` - Minimum value
- `max` - Maximum value

**Note**: Not all aggregation types are meaningful for all metrics. For example:
- `sum` is typically used for request counts, transactions, and capacity
- `average` is typically used for percentages (CPU, memory, disk)
- `max` is useful for identifying peak values
- `min` is useful for identifying minimum values

### 14.8 Configuration Values Reference by Resource Type

This section provides a concise reference of all available configuration values for each monitoring module, including units, supported aggregations, and metadata grouping options.

#### 14.8.1 Azure Service Bus Namespace

**Deadlettered Messages**
- **Unit**: `count`
- **Supported Aggregations**: `average`, `min`, `max`
- **Group By Metadata**: `EntityName` (queue name)
- **Metric Type**: `deadletter_messages`

**Active Messages**
- **Unit**: `count`
- **Supported Aggregations**: `sum`
- **Group By Metadata**: `EntityName` (queue name)
- **Metric Type**: `active_messages`

**Incoming Requests**
- **Unit**: `count`
- **Supported Aggregations**: `sum`
- **Group By Metadata**: `EntityName` (queue name)
- **Metric Type**: `incoming_requests`

**Server Errors**
- **Unit**: `count`
- **Supported Aggregations**: `sum`
- **Group By Metadata**: `EntityName` (queue name)
- **Metric Type**: `server_errors`

**Size**
- **Unit**: `bytes`
- **Supported Aggregations**: `average`, `min`, `max`
- **Group By Metadata**: `EntityName` (queue name)
- **Metric Type**: `size`

### 14.9 Available Metric Values for Storage Monitoring

This section documents the available metric values that can be used in JSON configuration files for storage-related monitoring modules. These values specify the unit, recommended aggregation type, and supported metadata grouping options for each metric.

#### 14.9.1 Azure Storage Account

**Metric: Capacity**
- **Metric Type**: `capacity`
- **Unit**: `bytes`
- **Recommended Aggregation**: `average`
- **Supported Aggregations**: `average`, `sum`, `count`, `min`, `max`
- **Supported group_by_metadata values**: `ApiName`, `OperationName`, `Tier`, and other metadata keys available in Azure Monitor metrics
- **Scope values**: `account`, `Blob`, `Table`, `Queue`, `File`
- **Azure Metric Names**:
  - Account-level: `UsedCapacity`
  - Service-level: `BlobCapacity`, `TableCapacity`, `QueueCapacity`, `FileCapacity`

**Metric: Transactions**
- **Metric Type**: `transactions`
- **Unit**: `count`
- **Recommended Aggregation**: `sum`
- **Supported Aggregations**: `sum`, `average`, `count`, `min`, `max`
- **Recommended group_by_metadata**: `ApiName`
- **Supported group_by_metadata values**: `ApiName`, `OperationName`, `Tier`, and other metadata keys available in Azure Monitor metrics
- **Scope values**: `account`, `Blob`, `Table`, `Queue`, `File`
- **Azure Metric Name**: `Transactions`

#### 14.9.2 Azure Storage Blob (via Storage Account Monitor)

**Note**: Blob capacity and transaction metrics are monitored using the Storage Account monitor with `scope: "Blob"`. The Storage Blob monitor (`storage_blob`) focuses exclusively on file-level operations (file existence and file modification checks).

**Metric: BlobCapacity**
- **Metric Type**: `capacity`
- **Scope**: `Blob` (required)
- **Unit**: `bytes`
- **Recommended Aggregation**: `average`
- **Supported Aggregations**: `average`, `sum`, `count`, `min`, `max`
- **Recommended group_by_metadata**: `Tier`
- **Supported group_by_metadata values**: `Tier`, `ApiName`, `OperationName`, and other metadata keys available in Azure Monitor metrics
- **Azure Metric Name**: `BlobCapacity`

**Metric: Transactions (Blob)**
- **Metric Type**: `transactions`
- **Scope**: `Blob` (required)
- **Unit**: `count`
- **Recommended Aggregation**: `sum`
- **Supported Aggregations**: `sum`, `average`, `count`, `min`, `max`
- **Recommended group_by_metadata**: `ApiName`, `Tier` (can specify multiple values)
- **Supported group_by_metadata values**: `ApiName`, `Tier`, `OperationName`, and other metadata keys available in Azure Monitor metrics
- **Azure Metric Name**: `Transactions`

#### 14.9.3 Azure Storage Table (via Storage Account Monitor)

**Note**: Table capacity and transaction metrics are monitored using the Storage Account monitor with `scope: "Table"`. The Storage Table monitor (`storage_table`) focuses exclusively on table existence checks.

**Metric: TableCapacity**
- **Metric Type**: `capacity`
- **Scope**: `Table` (required)
- **Unit**: `bytes`
- **Recommended Aggregation**: `average`
- **Supported Aggregations**: `average`, `sum`, `count`, `min`, `max`
- **Supported group_by_metadata values**: `ApiName`, `OperationName`, and other metadata keys available in Azure Monitor metrics
- **Azure Metric Name**: `TableCapacity`

**Metric: Transactions (Table)**
- **Metric Type**: `transactions`
- **Scope**: `Table` (required)
- **Unit**: `count`
- **Recommended Aggregation**: `sum`
- **Supported Aggregations**: `sum`, `average`, `count`, `min`, `max`
- **Recommended group_by_metadata**: `ApiName`
- **Supported group_by_metadata values**: `ApiName`, `OperationName`, and other metadata keys available in Azure Monitor metrics
- **Azure Metric Name**: `Transactions`

