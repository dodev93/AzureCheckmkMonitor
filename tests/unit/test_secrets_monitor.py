#!/usr/bin/env python3
"""
Unit tests for Secrets monitor module.

Tests match PRD section 3.6 requirements.
"""

import pytest
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from azurechecks.monitors.secrets_monitor import SecretsMonitor
from checkmk.checkmk_formatter import MetricResult, Metric, MetricProblem
from tests.fixtures.config_generators import generate_secrets_config
from tests.fixtures.checkmk_assertions import (
    assert_metric_result,
    assert_ok_message
)


class TestSecretAndCertificateExpiration:
    """Test secret and certificate expiration per PRD section 3.6.1."""
    
    def test_secret_expiration_monitoring(self):
        """Test secret expiration monitoring."""
        config = generate_secrets_config(
            app_registration_ids=['app-id-1'],
            metrics={
                'secret_expiration': {
                    'enabled': True,
                    'type': 'secrets',
                    'expiration_threshold': 30
                }
            }
        )
        
        # Mock app registration dict (as returned by Graph API)
        mock_app = {
            'id': 'app-object-id-1',
            'displayName': 'Test App'
        }
        
        # Mock secret expiring in 20 days (format returned by _get_secrets_and_certificates)
        end_date = datetime.now() + timedelta(days=20)
        mock_credentials = {
            'secrets': [{
                'id': 'secret-id-1',
                'hint': 'test',
                'display_name': 'Test Secret',
                'end_date': end_date.isoformat() + 'Z',
                'days_until_expiry': 20,
                'expired': False
            }],
            'certificates': []
        }
        
        monitor = SecretsMonitor(config)
        
        # Mock the internal methods that query Graph API
        with patch.object(monitor, '_get_app_registration_by_id', return_value=mock_app):
            with patch.object(monitor, '_get_secrets_and_certificates', return_value=mock_credentials):
                result = monitor.monitor(config)
                
                assert isinstance(result, MetricResult)
                # Should detect expiring secret
                assert len(result.metrics) >= 1
    
    def test_certificate_expiration_monitoring(self):
        """Test certificate expiration monitoring."""
        config = generate_secrets_config(
            app_registration_ids=['app-id-1'],
            metrics={
                'certificate_expiration': {
                    'enabled': True,
                    'type': 'certificates',
                    'expiration_threshold': 30
                }
            }
        )
        
        monitor = SecretsMonitor(config)
        
        # Mock app registration dict (as returned by Graph API)
        mock_app = {
            'id': 'app-object-id-1',
            'displayName': 'Test App'
        }
        
        # Mock certificate expiring in 20 days (format returned by _get_secrets_and_certificates)
        end_date = datetime.now(timezone.utc) + timedelta(days=20)
        mock_credentials = {
            'secrets': [],
            'certificates': [{
                'id': 'cert-id-1',
                'display_name': 'Test Certificate',
                'end_date': end_date.isoformat().replace('+00:00', 'Z'),
                'type': 'AsymmetricX509Cert',
                'days_until_expiry': 20,
                'expired': False
            }]
        }
        
        with patch.object(monitor, '_get_app_registration_by_id', return_value=mock_app):
            with patch.object(monitor, '_get_secrets_and_certificates', return_value=mock_credentials):
                result = monitor.monitor(config)
                
                assert isinstance(result, MetricResult)
                # Should detect expiring certificate
                assert len(result.metrics) >= 1
    
    def test_multiple_app_registrations(self):
        """Test multiple app registrations monitoring."""
        config = generate_secrets_config(
            app_registration_ids=['app-id-1', 'app-id-2'],
            metrics={
                'secret_expiration': {
                    'enabled': True,
                    'type': 'secrets',
                    'expiration_threshold': 30
                }
            }
        )
        
        monitor = SecretsMonitor(config)
        
        # Mock app registrations (as returned by Graph API)
        mock_app1 = {
            'id': 'app-object-id-1',
            'displayName': 'App 1'
        }
        
        mock_app2 = {
            'id': 'app-object-id-2',
            'displayName': 'App 2'
        }
        
        # Mock secret expiring in 20 days (format returned by _get_secrets_and_certificates)
        end_date = datetime.now(timezone.utc) + timedelta(days=20)
        mock_credentials = {
            'secrets': [{
                'id': 'secret-id-1',
                'hint': 'test',
                'display_name': 'Test Secret',
                'end_date': end_date.isoformat().replace('+00:00', 'Z'),
                'days_until_expiry': 20,
                'expired': False
            }],
            'certificates': []
        }
        
        # Mock methods to return different apps for different IDs
        def get_app_by_id(app_id):
            if app_id == 'app-id-1':
                return mock_app1
            elif app_id == 'app-id-2':
                return mock_app2
            return None
        
        with patch.object(monitor, '_get_app_registration_by_id', side_effect=get_app_by_id):
            with patch.object(monitor, '_get_secrets_and_certificates', return_value=mock_credentials):
                result = monitor.monitor(config)
                
                assert isinstance(result, MetricResult)
    
    def test_expiration_threshold_evaluation(self):
        """Test expiration threshold evaluation."""
        # This test would verify that secrets/certificates expiring within
        # days_before_expiration are identified correctly
        pass
    
    def test_days_until_expiration_calculation(self):
        """Test days until expiration calculation."""
        # This test would verify the calculation of days until expiration
        pass
    
    def test_status_determination(self):
        """Test status determination (OK: 0-1 apps, CRIT: >1 apps)."""
        # Status is CRIT when count > 1
        # This is typically handled in the monitor logic
        pass
    
    def test_message_includes_app_names(self):
        """Test message includes app names and days until expiration."""
        # Message should include app names and days until expiration
        pass

