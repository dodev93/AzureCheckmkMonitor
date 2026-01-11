#!/usr/bin/env python3
"""
Configuration Validator Module

Validates JSON configuration files against JSON schemas.
Supports ISO 8601 duration format validation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from jsonschema import validate, ValidationError

from utils import MonitorUtils


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    pass


class ConfigValidator:
    """
    Configuration Validator class.
    
    Provides methods for validating JSON configuration files against JSON schemas.
    Supports ISO 8601 duration format validation.
    """
    
    @staticmethod
    def validate_iso8601_duration(duration_str: str) -> bool:
        """
        Validate ISO 8601 duration format.
        
        Args:
            duration_str: Duration string to validate
            
        Returns:
            True if valid, False otherwise
        """
        return MonitorUtils.parse_iso8601_duration(duration_str) is not None
    
    @staticmethod
    def load_schema(resource_type: str) -> Dict[str, Any]:
        """
        Load JSON schema for a resource type.
        
        Args:
            resource_type: Resource type (e.g., 'apim')
            
        Returns:
            Schema dictionary
            
        Raises:
            ConfigValidationError: If schema file not found or invalid
        """
        # Get the directory of this file
        current_dir = Path(__file__).parent.parent.parent
        schema_path = current_dir / "configs" / "schemas" / f"{resource_type}_schema.json"
        
        if not schema_path.exists():
            raise ConfigValidationError(
                f"Schema file not found: {schema_path}"
            )
        
        try:
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            return schema
        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                f"Invalid JSON in schema file {schema_path}: {str(e)}"
            )
        except Exception as e:
            raise ConfigValidationError(
                f"Error loading schema file {schema_path}: {str(e)}"
            )
    
    @staticmethod
    def validate_config(config: Dict[str, Any], resource_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate configuration against JSON schema.
        
        Args:
            config: Configuration dictionary
            resource_type: Resource type (if None, extracted from config)
            
        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is None
        """
        
        # Extract resource type from config if not provided
        if resource_type is None:
            resource_type = config.get('resource_type')
            if not resource_type:
                return False, "Missing 'resource_type' in configuration"
        
        # Load schema
        try:
            schema = ConfigValidator.load_schema(resource_type)
        except ConfigValidationError as e:
            return False, str(e)
        
        # Validate against schema
        try:
            validate(instance=config, schema=schema)
        except ValidationError as e:
            # Format a user-friendly error message
            error_path = " -> ".join(str(p) for p in e.absolute_path)
            error_msg = f"Validation error at '{error_path}': {e.message}"
            if e.absolute_path:
                error_msg = f"Validation error at '{error_path}': {e.message}"
            else:
                error_msg = f"Validation error: {e.message}"
            return False, error_msg
        
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
                    return False, (
                        f"Invalid time_range format in metric '{metric_name}': "
                        f"'{time_range}'. Expected format: PT<N>[MHD] (e.g., PT1H, PT5M)"
                    )
                
                # Validate granularity
                granularity = metric_config.get('granularity')
                if granularity and not ConfigValidator.validate_iso8601_duration(granularity):
                    return False, (
                        f"Invalid granularity format in metric '{metric_name}': "
                        f"'{granularity}'. Expected format: PT<N>[MHD] (e.g., PT1H, PT5M)"
                    )
        
        return True, None
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        Load configuration file without validation.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigValidationError: If file not found or invalid JSON
        """
        if not os.path.exists(config_path):
            raise ConfigValidationError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                f"Invalid JSON in configuration file {config_path}: {str(e)}"
            )
        except Exception as e:
            raise ConfigValidationError(
                f"Error reading configuration file {config_path}: {str(e)}"
            )
        
        return config
    
    @staticmethod
    def load_and_validate_config(config_path: str) -> Dict[str, Any]:
        """
        Load and validate configuration file.
        
        Note: resource_id is not built here. It should be built in generic_check.py
        after loading the configuration to ensure consistency across all resource types.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ConfigValidationError: If file not found, invalid JSON, or validation fails
        """
        config = ConfigValidator.load_config(config_path)
        
        # Validate configuration
        is_valid, error_msg = ConfigValidator.validate_config(config)
        if not is_valid:
            raise ConfigValidationError(error_msg)
        
        # Note: resource_id building is now done in generic_check.py
        # to ensure consistency across all resource types (apim, storage_account, storage_blob, storage_table)
        
        return config

