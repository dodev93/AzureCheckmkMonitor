#!/usr/bin/env python3
"""
Azure Secrets and Certificates Monitor

Monitors expiration dates of secrets and certificates for Azure App Registrations
using Microsoft Graph API.
"""

import sys
import time
import requests
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Callable

from checkmk.checkmk_formatter import Metric, MetricResult, MetricProblem
from exceptions import UnsupportedMetricTypeError
from azurechecks.azure_auth import get_graph_token
from exceptions import AzureAuthError


# ============================================================================
# Secrets Metric Type Enum
# ============================================================================

class SecretsMetricType(Enum):
    """Enumeration of supported Secrets metric types."""
    SECRETS = "secrets"
    CERTIFICATES = "certificates"


# ============================================================================
# SecretsMonitor Class
# ============================================================================

class SecretsMonitor:
    """
    Azure Secrets and Certificates Monitor class.
    
    Monitors expiration dates of secrets and certificates for Azure App Registrations.
    Uses Microsoft Graph API instead of Azure Monitor metrics.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Secrets monitor from configuration dictionary.
        
        Args:
            config: Full configuration dictionary containing:
                - app_registrations: List of app registration configs (app_id or app_name)
        """
        # Extract app_registrations list
        self.app_registrations = config.get('app_registrations', [])
        if not self.app_registrations:
            raise ValueError("Missing 'app_registrations' in configuration (required)")
    
    def monitor(self, config: Dict[str, Any], debug: bool = False) -> MetricResult:
        """
        Main monitoring method that runs all enabled metrics sequentially.
        
        Args:
            config: Full configuration dictionary with common config and metrics
            debug: Whether to print execution time for each metric
            
        Returns:
            Single MetricResult instance with all metrics
        """
        metrics_config = config.get('metrics', {})
        
        # Extract common configuration
        common_config = {
            'service_name': config.get('service_name'),
            'app_registrations': self.app_registrations
        }
        
        # Get metric methods map
        metric_methods = self._get_metric_methods()
        
        # Collect all metrics and problematic items
        all_metrics = []
        all_problems = []
        service_name = common_config.get('service_name', 'Azure Secrets')
        
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
                metric_type = SecretsMetricType(metric_type_str)
            except ValueError:
                # Raise custom exception
                supported_types = [e.value for e in SecretsMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Verify metric type is supported
            if metric_type not in metric_methods:
                supported_types = [e.value for e in SecretsMetricType]
                raise UnsupportedMetricTypeError(
                    checkmk_metric_name,
                    metric_type_str,
                    supported_types
                )
            
            # Merge common config with metric-specific config
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
        
        # Return result
        return MetricResult(
            service_name=service_name,
            metrics=all_metrics,
            problems=all_problems if all_problems else None
        )
    
    def _get_metric_methods(self) -> Dict[SecretsMetricType, Callable]:
        """
        Get mapping of metric types to method references.
        
        Returns:
            Dictionary mapping enum values to method references
        """
        return {
            SecretsMetricType.SECRETS: self.monitor_secrets,
            SecretsMetricType.CERTIFICATES: self.monitor_certificates
        }
    
    def _get_app_registration_by_id(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Get App Registration by Application (Client) ID.
        
        Args:
            app_id: Application (Client) ID
        
        Returns:
            App Registration details dictionary, or None if not found
        """
        token = get_graph_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{app_id}'"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('value') and len(data['value']) > 0:
            return data['value'][0]
        return None
    
    def _get_app_registration_by_name(self, app_name: str) -> Optional[Dict[str, Any]]:
        """
        Get App Registration by display name.
        
        Args:
            app_name: Application display name
        
        Returns:
            App Registration details dictionary, or None if not found
        """
        token = get_graph_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"https://graph.microsoft.com/v1.0/applications?$filter=displayName eq '{app_name}'"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data.get('value') and len(data['value']) > 0:
            return data['value'][0]
        return None
    
    def _get_secrets_and_certificates(self, app_object_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get secrets and certificates for an App Registration.
        
        Args:
            app_object_id: Application object ID
        
        Returns:
            Dictionary with 'secrets' and 'certificates' lists
        """
        token = get_graph_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"https://graph.microsoft.com/v1.0/applications/{app_object_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        app_data = response.json()
        
        result = {
            'secrets': [],
            'certificates': []
        }
        
        # Get password credentials (secrets)
        if 'passwordCredentials' in app_data:
            for secret in app_data['passwordCredentials']:
                secret_info = {
                    'id': secret.get('keyId', 'unknown'),
                    'hint': secret.get('hint', ''),
                    'display_name': secret.get('displayName', 'Secret'),
                    'end_date': secret.get('endDateTime')
                }
                
                days = self._calculate_days_until_expiry(secret_info['end_date'])
                secret_info['days_until_expiry'] = days
                secret_info['expired'] = days is not None and days < 0
                
                result['secrets'].append(secret_info)
        
        # Get key credentials (certificates)
        if 'keyCredentials' in app_data:
            for cert in app_data['keyCredentials']:
                cert_info = {
                    'id': cert.get('keyId', 'unknown'),
                    'display_name': cert.get('displayName', 'Certificate'),
                    'end_date': cert.get('endDateTime'),
                    'type': cert.get('type', 'AsymmetricX509Cert')
                }
                
                days = self._calculate_days_until_expiry(cert_info['end_date'])
                cert_info['days_until_expiry'] = days
                cert_info['expired'] = days is not None and days < 0
                
                result['certificates'].append(cert_info)
        
        return result
    
    def _calculate_days_until_expiry(self, end_date_str: Optional[str]) -> Optional[int]:
        """
        Calculate days until expiration from ISO 8601 date string.
        
        Args:
            end_date_str: ISO 8601 formatted date string (e.g., "2024-12-31T00:00:00Z")
        
        Returns:
            Days until expiration (negative if expired), or None if date is missing/invalid
        """
        if not end_date_str:
            return None
        
        try:
            # Handle ISO 8601 format with 'Z' timezone
            date_str = end_date_str.replace('Z', '+00:00')
            end_date = datetime.fromisoformat(date_str)
            now = datetime.now(end_date.tzinfo) if end_date.tzinfo else datetime.utcnow()
            days_until_expiry = (end_date - now).days
            return days_until_expiry
        except (ValueError, AttributeError):
            # If date parsing fails, return None
            return None
    
    def _find_minimum_expiration_days(self, credentials: Dict[str, List[Dict[str, Any]]], credential_type: str) -> Optional[int]:
        """
        Find minimum days until expiration for a credential type (secrets or certificates).
        
        Args:
            credentials: Dictionary with 'secrets' and 'certificates' lists
            credential_type: Either 'secrets' or 'certificates'
        
        Returns:
            Minimum days until expiration, or None if no credentials with expiration dates
        """
        min_days = None
        credential_list = credentials.get(credential_type, [])
        
        for credential in credential_list:
            days = credential.get('days_until_expiry')
            if days is not None:
                if min_days is None or days < min_days:
                    min_days = days
        
        return min_days
    
    def monitor_secrets(
        self,
        config: Dict[str, Any],
        metric_name: str,
        debug: bool = False
    ) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor secrets expiration across all configured App Registrations.
        
        Counts applications with secrets expiring within expiration_threshold.
        Returns CRIT if more than 1 application has expiring secrets.
        
        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
        
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        app_registrations = config.get('app_registrations', [])
        expiration_threshold = config.get('expiration_threshold')
        
        if expiration_threshold is None:
            raise ValueError("Missing 'expiration_threshold' in metric configuration (required)")
        
        expiration_threshold = float(expiration_threshold)
        
        apps_with_expiring_secrets = []
        all_problems = []
        
        # Iterate over all app registrations
        for app_config in app_registrations:
            app_id = app_config.get('app_id')
            app_name = app_config.get('app_name')
            
            # Get app registration
            if app_id:
                app = self._get_app_registration_by_id(app_id)
                if not app:
                    raise ValueError(f"App Registration with ID '{app_id}' not found")
            elif app_name:
                app = self._get_app_registration_by_name(app_name)
                if not app:
                    raise ValueError(f"App Registration with name '{app_name}' not found")
            else:
                raise ValueError("App registration config must have either 'app_id' or 'app_name'")
            
            app_object_id = app['id']
            app_display_name = app.get('displayName', app_id or app_name)
            
            # Get secrets and certificates
            credentials = self._get_secrets_and_certificates(app_object_id)
            
            # Find minimum expiration days for secrets
            min_days = self._find_minimum_expiration_days(credentials, 'secrets')
            
            # Check if app has expiring secrets (within threshold or expired)
            if min_days is not None and min_days <= expiration_threshold:
                apps_with_expiring_secrets.append({
                    'name': app_display_name,
                    'days': min_days
                })
                
                # Create MetricProblem for this app
                problem_msg = f"{int(min_days)} days"
                all_problems.append(MetricProblem(
                    problem_name=app_display_name,
                    problem_value=float(min_days),
                    problem_message=problem_msg,
                    metadata_key="Secrets"
                ))
        
        # Count applications with expiring secrets
        app_count = len(apps_with_expiring_secrets)
        
        # Create Metric instance
        # Value is the count of apps with expiring secrets
        # Thresholds: warn=0, crit=1 (CRIT if count > 1)
        metric = Metric(
            name=metric_name,
            value=float(app_count),
            warn_threshold=None,
            crit_threshold=1.0,
            min_value=0.0,
            max_value=None,  # No max limit
            unit=''
        )
        
        return (metric, all_problems if all_problems else None)
    
    def monitor_certificates(
        self,
        config: Dict[str, Any],
        metric_name: str,
        debug: bool = False
    ) -> Tuple[Metric, Optional[List[MetricProblem]]]:
        """
        Monitor certificates expiration across all configured App Registrations.
        
        Counts applications with certificates expiring within expiration_threshold.
        Returns CRIT if more than 1 application has expiring certificates.
        
        Args:
            config: Metric configuration dictionary (already merged with common config)
            metric_name: Metric name to use in Checkmk output
        
        Returns:
            Tuple of (Metric, Optional[List[MetricProblem]])
        """
        app_registrations = config.get('app_registrations', [])
        expiration_threshold = config.get('expiration_threshold')
        
        if expiration_threshold is None:
            raise ValueError("Missing 'expiration_threshold' in metric configuration (required)")
        
        expiration_threshold = float(expiration_threshold)
        
        apps_with_expiring_certs = []
        all_problems = []
        
        # Iterate over all app registrations
        for app_config in app_registrations:
            app_id = app_config.get('app_id')
            app_name = app_config.get('app_name')
            
            # Get app registration
            if app_id:
                app = self._get_app_registration_by_id(app_id)
                if not app:
                    raise ValueError(f"App Registration with ID '{app_id}' not found")
            elif app_name:
                app = self._get_app_registration_by_name(app_name)
                if not app:
                    raise ValueError(f"App Registration with name '{app_name}' not found")
            else:
                raise ValueError("App registration config must have either 'app_id' or 'app_name'")
            
            app_object_id = app['id']
            app_display_name = app.get('displayName', app_id or app_name)
            
            # Get secrets and certificates
            credentials = self._get_secrets_and_certificates(app_object_id)
            
            # Find minimum expiration days for certificates
            min_days = self._find_minimum_expiration_days(credentials, 'certificates')
            
            # Check if app has expiring certificates (within threshold or expired)
            if min_days is not None and min_days <= expiration_threshold:
                apps_with_expiring_certs.append({
                    'name': app_display_name,
                    'days': min_days
                })
                
                # Create MetricProblem for this app
                problem_msg = f"{int(min_days)} days"
                all_problems.append(MetricProblem(
                    problem_name=app_display_name,
                    problem_value=float(min_days),
                    problem_message=problem_msg,
                    metadata_key="Certificates"
                ))
        
        # Count applications with expiring certificates
        app_count = len(apps_with_expiring_certs)
        
        # Create Metric instance
        # Value is the count of apps with expiring certificates
        # Thresholds: warn=0, crit=1 (CRIT if count > 1)
        metric = Metric(
            name=metric_name,
            value=float(app_count),
            warn_threshold=None,
            crit_threshold=1.0,
            min_value=0.0,
            max_value=None,  # No max limit
            unit=''
        )
        
        return (metric, all_problems if all_problems else None)
