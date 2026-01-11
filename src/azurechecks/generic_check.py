#!/usr/bin/env python3
"""
Generic Check Script for Azure Resource Monitoring

Main entry point that routes to resource-specific monitoring modules
based on JSON configuration files.
"""

import sys
import json
from pathlib import Path
import warnings

# Suppress Azure SDK warnings from printing to console
# warnings.filterwarnings('ignore')

# Suppress Python's default exception handler to prevent stack traces on console
def silent_excepthook(exc_type, exc_value, exc_traceback):
    """Silent exception hook - exceptions are logged to files, not printed to console."""
    # Do nothing - exceptions are handled in try/except blocks
    pass

# Set custom exception hook early to catch any unhandled exceptions
sys.excepthook = silent_excepthook

# Add src directory to path to enable package imports
# This allows the script to be run directly while still importing from the package structure
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import using absolute imports (works when run as script)
from validation.config_validator import ConfigValidator, ConfigValidationError
from checkmk.checkmk_formatter import CheckmkFormatter
from exceptions import AzureAuthError
from azurechecks.monitors import apim_monitor, storage_account_monitor, storage_blob_monitor, storage_table_monitor, servicebus_monitor, secrets_monitor, container_apps_monitor, aks_monitor
from utils import ExceptionLogger


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override values taking precedence.
    
    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary
        
    Returns:
        Merged configuration dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # Override the value
            result[key] = value
    
    return result


def route_to_monitor(resource_type: str, config: dict, debug: bool = False):
    """
    Route configuration to appropriate resource monitor.

    Args:
        resource_type: Resource type (e.g., 'apim', 'storage_account', 'storage_blob', 'storage_table')
        config: Configuration dictionary
        debug: Whether to print execution time for each metric

    Returns:
        MetricResult instance
    """
    if resource_type == 'apim':
        am = apim_monitor.APIMMonitor(config)
        return am.monitor(config, debug=debug)
    elif resource_type == 'storage_account':
        sam = storage_account_monitor.StorageAccountMonitor(config)
        return sam.monitor(config, debug=debug)
    elif resource_type == 'storage_blob':
        sbm = storage_blob_monitor.StorageBlobMonitor(config)
        return sbm.monitor(config, debug=debug)
    elif resource_type == 'storage_table':
        stm = storage_table_monitor.StorageTableMonitor(config)
        return stm.monitor(config, debug=debug)
    elif resource_type == 'servicebus':
        sbm = servicebus_monitor.ServiceBusMonitor(config)
        return sbm.monitor(config, debug=debug)
    elif resource_type == 'secrets':
        sm = secrets_monitor.SecretsMonitor(config)
        return sm.monitor(config, debug=debug)
    elif resource_type == 'container_apps':
        cam = container_apps_monitor.ContainerAppsMonitor(config)
        return cam.monitor(config, debug=debug)
    elif resource_type == 'aks':
        aksm = aks_monitor.AKSMonitor(config)
        return aksm.monitor(config, debug=debug)
    else:
        raise ValueError(f"Unsupported resource type: {resource_type}")


def format_results(result) -> str:
    """
    Format monitoring result as Checkmk output.
    
    Args:
        result: MetricResult instance from monitor function
        
    Returns:
        Single Checkmk-formatted service line
    """
    from checkmk.checkmk_formatter import MetricResult
    
    if isinstance(result, MetricResult):
        # Format MetricResult directly
        return CheckmkFormatter.format_single_response_line(result)
    else:
        # Fallback for unexpected types
        raise ValueError(f"Unexpected result type: {type(result)}")


def main():
    """
    Main entry point for generic check script.
    
    Usage: python generic_check.py <config_file_path> [--debug] [--override <json_string>]
    """
    if len(sys.argv) < 2:
        print('3 "Azure Monitor" Error: Configuration file path required')
        print("Usage: python generic_check.py <config_file_path> [--debug] [--override <json_string>]")
        sys.exit(3)
    
    config_path = sys.argv[1]
    
    # Parse arguments
    debug = False
    override_json = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--debug':
            debug = True
            i += 1
        elif sys.argv[i] == '--override':
            if i + 1 >= len(sys.argv):
                print('3 "Azure Monitor" Error: --override requires a JSON string argument')
                sys.exit(3)
            override_json = sys.argv[i + 1]
            i += 2
        else:
            print(f'3 "Azure Monitor" Error: Unknown argument: {sys.argv[i]}')
            print("Usage: python generic_check.py <config_file_path> [--debug] [--override <json_string>]")
            sys.exit(3)
    
    # Initialize logger (will be reconfigured with service_name once config is loaded)
    logger = None
    config = None
    service_name = None
    
    # Calculate base path for logs (project root, 3 levels up from this file)
    base_path = Path(__file__).parent.parent.parent
    
    try:
        # Load base configuration
        config = ConfigValidator.load_config(config_path)
        
        # Parse and apply overrides if provided
        if override_json:
            try:
                override = json.loads(override_json)
                config = deep_merge(config, override)
            except json.JSONDecodeError as e:
                raise ConfigValidationError(
                    f"Invalid JSON in override string: {str(e)}"
                )
        
        # Extract service name for logging
        service_name = config.get('service_name')
        
        # Set up exception logging with service name
        logger = ExceptionLogger.setup_exception_logging(service_name, base_path=base_path)
        
        # Extract resource type
        resource_type = config.get('resource_type')
        if not resource_type:
            print('3 "Azure Monitor" Error: Missing resource_type in configuration')
            sys.exit(3)
        
        
        # Route to appropriate monitor
        result = route_to_monitor(resource_type, config, debug=debug)
        
        # Format and output result
        output = format_results(result)
        print(output)
        
        # Determine exit code based on status
        # If status is "P", exit with 0 (Checkmk will calculate)
        # If status is numeric, use it as exit code
        # Error status (3) always exits with 3
        if hasattr(result, 'status'):
            status = result.status
            if status == "P":
                exit_code = 0
            elif isinstance(status, int):
                exit_code = status
            else:
                exit_code = 0
        else:
            exit_code = 0
        
        sys.exit(exit_code)
        
    except ConfigValidationError as e:
        # Set up logger if not already set up (config loading failed)
        if logger is None:
            logger = ExceptionLogger.setup_exception_logging("Configuration", base_path=base_path)
        ExceptionLogger.log_exception(logger, e, "ConfigValidationError")
        # Exception details are logged but not printed in Checkmk output
        print(f'3 "Azure Monitor" Configuration validation error')
        sys.exit(3)
    except AzureAuthError as e:
        # Set up logger if not already set up
        if logger is None:
            logger = ExceptionLogger.setup_exception_logging(service_name or "Azure Monitor", base_path=base_path)
        ExceptionLogger.log_exception(logger, e, "AzureAuthError")
        # Exception details are logged but not printed in Checkmk output
        print(f'3 "{service_name or "Azure Monitor"}" Authentication error')
        sys.exit(3)
    except ValueError as e:
        # Set up logger if not already set up
        if logger is None:
            logger = ExceptionLogger.setup_exception_logging(service_name or "Azure Monitor", base_path=base_path)
        ExceptionLogger.log_exception(logger, e, "ValueError")
        # Exception details are logged but not printed in Checkmk output
        print(f'3 "{service_name or "Azure Monitor"}" Error')
        sys.exit(3)
    except Exception as e:
        # Set up logger if not already set up
        if logger is None:
            logger = ExceptionLogger.setup_exception_logging(service_name or "Azure Monitor", base_path=base_path)
        ExceptionLogger.log_exception(logger, e, "UnexpectedException")
        # Exception details are logged but not printed in Checkmk output
        print(f'3 "{service_name or "Azure Monitor"}" Unexpected error')
        sys.exit(3)


if __name__ == '__main__':
    main()

