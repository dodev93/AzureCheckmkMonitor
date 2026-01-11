#!/usr/bin/env python3
"""
Standalone Configuration Validation Script

Validates a JSON configuration file against a JSON schema file.
This script is separate from the monitoring flow to avoid validation overhead on every check.

Usage:
    python validate_config.py <config_file_path> <schema_file_path>
    
Example:
    python validate_config.py ../configs/examples/apim_all_apis.json ../configs/schemas/apim_schema.json
"""

import sys
import json
import os
from pathlib import Path

# Add src directory to path to enable package imports
# This allows the script to be run directly while still importing from the package structure
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import using absolute imports (works when run as script)
from validation.config_validator import ConfigValidator, ConfigValidationError


def load_json_file(file_path: str) -> dict:
    """
    Load JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ConfigValidationError: If file not found or invalid JSON
    """
    if not os.path.exists(file_path):
        raise ConfigValidationError(f"File not found: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(
            f"Invalid JSON in file {file_path}: {str(e)}"
        )
    except Exception as e:
        raise ConfigValidationError(
            f"Error reading file {file_path}: {str(e)}"
        )


def extract_resource_type_from_config(config: dict) -> str:
    """
    Extract resource_type from configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Resource type string
        
    Raises:
        ConfigValidationError: If resource_type is missing
    """
    resource_type = config.get('resource_type')
    if not resource_type:
        raise ConfigValidationError("Missing 'resource_type' in configuration")
    return resource_type


def extract_resource_type_from_schema_path(schema_path: str) -> str:
    """
    Extract resource type from schema file path.
    
    Expected format: .../<resource_type>_schema.json
    
    Args:
        schema_path: Path to schema file
        
    Returns:
        Resource type string
        
    Raises:
        ConfigValidationError: If path format is invalid
    """
    schema_file = Path(schema_path).name
    if not schema_file.endswith('_schema.json'):
        raise ConfigValidationError(
            f"Schema file name must end with '_schema.json': {schema_file}"
        )
    
    resource_type = schema_file[:-12]  # Remove '_schema.json'
    if not resource_type:
        raise ConfigValidationError(
            f"Could not extract resource type from schema path: {schema_path}"
        )
    
    return resource_type


def main():
    """
    Main entry point for configuration validation script.
    
    Usage: python validate_config.py <config_file_path> <schema_file_path>
    """
    if len(sys.argv) < 3:
        print("Error: Configuration file path and schema file path required")
        print("Usage: python validate_config.py <config_file_path> <schema_file_path>")
        print("\nExample:")
        print("  python validate_config.py ../configs/examples/apim_all_apis.json ../configs/schemas/apim_schema.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    schema_path = sys.argv[2]
    
    try:
        # Load configuration file
        config = load_json_file(config_path)
        
        # Load schema file
        schema = load_json_file(schema_path)
        
        # Extract resource type from config or schema path
        try:
            resource_type = extract_resource_type_from_config(config)
        except ConfigValidationError:
            # If not in config, try to extract from schema path
            resource_type = extract_resource_type_from_schema_path(schema_path)
        
        # Validate configuration against schema
        # Note: validate_config() will load the schema from the standard location
        # if resource_type is provided, but we want to use the provided schema_path.
        # So we'll use jsonschema directly for this script.
        try:
            import jsonschema
            from jsonschema import validate, ValidationError
        except ImportError:
            print("Error: jsonschema library is not installed. Install with: pip install jsonschema")
            sys.exit(1)
        
        try:
            validate(instance=config, schema=schema)
        except ValidationError as e:
            # Format a user-friendly error message
            error_path = " -> ".join(str(p) for p in e.absolute_path)
            if error_path:
                error_msg = f"Validation error at '{error_path}': {e.message}"
            else:
                error_msg = f"Validation error: {e.message}"
            print(f"Validation failed in '{config_path}': {error_msg}")
            sys.exit(1)
        
        # Additional validation: Check ISO 8601 duration formats
        if 'metrics' in config:
            for metric_name, metric_config in config['metrics'].items():
                if not isinstance(metric_config, dict):
                    continue
                
                if not metric_config.get('enabled', False):
                    continue
                
                # Validate time_range
                time_range = metric_config.get('time_range')
                if time_range and not ConfigValidator.validate_iso8601_duration(time_range):
                    print(
                        f"Validation failed in '{config_path}': Invalid time_range format in metric '{metric_name}': "
                        f"'{time_range}'. Expected format: PT<N>[MHD] (e.g., PT1H, PT5M)"
                    )
                    sys.exit(1)
                
                # Validate granularity
                granularity = metric_config.get('granularity')
                if granularity and not ConfigValidator.validate_iso8601_duration(granularity):
                    print(
                        f"Validation failed in '{config_path}': Invalid granularity format in metric '{metric_name}': "
                        f"'{granularity}'. Expected format: PT<N>[MHD] (e.g., PT1H, PT5M)"
                    )
                    sys.exit(1)
        
        # Validation successful
        print(f"✓ Configuration file '{config_path}' is valid against schema '{schema_path}'")
        sys.exit(0)
        
    except ConfigValidationError as e:
        print(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()

