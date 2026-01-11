#!/usr/bin/env python3
"""
Unit tests for config_validator module.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

# Add src directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from validation.config_validator import (
    ConfigValidator,
    ConfigValidationError
)
from utils import MonitorUtils


class TestISO8601DurationParsing:
    """Test ISO 8601 duration parsing."""
    
    def test_parse_valid_minutes(self):
        """Test parsing minutes."""
        result = MonitorUtils.parse_iso8601_duration("PT5M")
        assert result == {'value': 5, 'unit': 'M'}
    
    def test_parse_valid_hours(self):
        """Test parsing hours."""
        result = MonitorUtils.parse_iso8601_duration("PT1H")
        assert result == {'value': 1, 'unit': 'H'}
    
    def test_parse_valid_days(self):
        """Test parsing days."""
        result = MonitorUtils.parse_iso8601_duration("PT1D")
        assert result == {'value': 1, 'unit': 'D'}
    
    def test_parse_invalid_format(self):
        """Test parsing invalid format."""
        result = MonitorUtils.parse_iso8601_duration("invalid")
        assert result is None
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = MonitorUtils.parse_iso8601_duration("")
        assert result is None
    
    def test_parse_non_string(self):
        """Test parsing non-string input."""
        result = MonitorUtils.parse_iso8601_duration(123)
        assert result is None
    
    def test_validate_valid_durations(self):
        """Test validation of valid durations."""
        assert ConfigValidator.validate_iso8601_duration("PT5M") is True
        assert ConfigValidator.validate_iso8601_duration("PT1H") is True
        assert ConfigValidator.validate_iso8601_duration("PT1D") is True
    
    def test_validate_invalid_durations(self):
        """Test validation of invalid durations."""
        assert ConfigValidator.validate_iso8601_duration("invalid") is False
        assert ConfigValidator.validate_iso8601_duration("P1D") is False  # Missing T
        assert ConfigValidator.validate_iso8601_duration("PT") is False  # Missing value and unit


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_valid_apim_config(self):
        """Test valid APIM configuration."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "request_count": {
                    "enabled": True,
                    "type": "request_count",
                    "time_range": "PT1H",
                    "aggregation": "sum",
                    "api_ids": [],
                    "warn_threshold": 100,
                    "crit_threshold": 500,
                    "min": 0,
                    "max": None
                }
            }
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is True
        assert error is None
    
    def test_missing_resource_type(self):
        """Test missing resource_type."""
        config = {
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "metrics": {}
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is False
        assert "resource_type" in error.lower()
    
    def test_invalid_resource_id_format(self):
        """Test invalid resource ID format."""
        config = {
            "resource_type": "apim",
            "resource_id": "invalid-resource-id",
            "metrics": {}
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is False
    
    def test_invalid_time_range_format(self):
        """Test invalid time_range format."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "request_count": {
                    "enabled": True,
                    "type": "request_count",
                    "time_range": "invalid",
                    "aggregation": "sum"
                }
            }
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is False
        assert "time_range" in error.lower()
    
    def test_invalid_aggregation(self):
        """Test invalid aggregation type."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "request_count": {
                    "enabled": True,
                    "type": "request_count",
                    "time_range": "PT1H",
                    "aggregation": "invalid"
                }
            }
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is False
    
    def test_requests_by_codes_valid(self):
        """Test valid requests_by_codes configuration."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "requests_by_codes": {
                    "enabled": True,
                    "type": "requests_by_codes",
                    "time_range": "PT1H",
                    "aggregation": "sum",
                    "response_codes": ["200", "404", "500"],
                    "api_ids": []
                }
            }
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is True
    
    def test_requests_by_codes_missing_response_codes(self):
        """Test requests_by_codes without response_codes."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "requests_by_codes": {
                    "enabled": True,
                    "type": "requests_by_codes",
                    "time_range": "PT1H",
                    "aggregation": "sum",
                    "api_ids": []
                }
            }
        }
        is_valid, error = ConfigValidator.validate_config(config)
        assert is_valid is False


class TestLoadAndValidateConfig:
    """Test loading and validating configuration files."""
    
    def test_load_valid_config_file(self):
        """Test loading valid configuration file."""
        config = {
            "resource_type": "apim",
            "subscription_id": "sub-id",
            "resource_group": "rg",
            "resource_name": "apim-name",
            "location": "westeurope",
            "time_range": "PT1H",
            "aggregation": "sum",
            "service_name": "APIM Test",
            "metrics": {
                "request_count": {
                    "enabled": True,
                    "type": "request_count",
                    "time_range": "PT1H",
                    "aggregation": "sum",
                    "api_ids": []
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        
        try:
            loaded_config = ConfigValidator.load_and_validate_config(temp_path)
            assert loaded_config == config
        finally:
            os.unlink(temp_path)
    
    def test_load_invalid_json(self):
        """Test loading invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError):
                ConfigValidator.load_and_validate_config(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent file."""
        with pytest.raises(ConfigValidationError) as exc_info:
            ConfigValidator.load_and_validate_config("/nonexistent/file.json")
        assert "not found" in str(exc_info.value).lower()
    
    def test_load_invalid_config(self):
        """Test loading invalid configuration."""
        config = {
            "resource_type": "apim",
            "resource_id": "invalid"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError):
                ConfigValidator.load_and_validate_config(temp_path)
        finally:
            os.unlink(temp_path)

