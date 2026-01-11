#!/usr/bin/env python3
"""
Azure Monitor Utilities

Utilities for Azure Monitor.
"""

import re
import logging
import traceback
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

# ============================================================================
# MonitorUtils Class
# ============================================================================

class MonitorUtils:
    """
    Monitor Utilities class.
    
    Encapsulates all monitoring utilities functionality with shared state management.
    """
    
    @staticmethod
    def parse_iso8601_duration(duration_str: str) -> Optional[Dict[str, int]]:
        """
        Parse ISO 8601 duration string to components.
        
        Supports format: PT<N><unit> where unit is M (minutes), H (hours), or D (days)
        Examples: PT1H, PT5M, PT1D
        
        Args:
            duration_str: ISO 8601 duration string
            
        Returns:
            dict with keys 'value' and 'unit' (M, H, or D), or None if invalid
        """
        if not isinstance(duration_str, str):
            return None
        
        # Pattern: PT followed by digits and M, H, or D
        pattern = r'^PT(\d+)([MHD])$'
        match = re.match(pattern, duration_str)
        
        if not match:
            return None
        
        value = int(match.group(1))
        unit = match.group(2)
        
        return {'value': value, 'unit': unit}
    
    @staticmethod
    def iso8601_to_timedelta(duration_str: str) -> timedelta:
        """
        Convert ISO 8601 duration string to timedelta.
        
        Supports: PT<N>M (minutes), PT<N>H (hours), PT<N>D (days)
        Examples: PT1H, PT5M, PT1D
        
        Args:
            duration_str: ISO 8601 duration string
            
        Returns:
            timedelta object
            
        Raises:
            ValueError: If duration format is invalid
        """
        parsed = MonitorUtils.parse_iso8601_duration(duration_str)
        if not parsed:
            raise ValueError(f"Invalid ISO 8601 duration format: {duration_str}")
        
        value = parsed['value']
        unit = parsed['unit']
        
        if unit == 'M':
            return timedelta(minutes=value)
        elif unit == 'H':
            return timedelta(hours=value)
        elif unit == 'D':
            return timedelta(days=value)
        else:
            raise ValueError(f"Unsupported duration unit: {unit}")


    @staticmethod
    def get_metrics_endpoint(location: str) -> str:
        """
        Get the Azure Monitor metrics endpoint for the given location.
        
        The endpoint format is: https://<region>.metrics.monitor.azure.com
        
        Args:
            location: Azure location
            
        Returns:
            Metrics endpoint URL (e.g., "https://polandcentral.metrics.monitor.azure.com")
            
        Raises:
            ValueError: If unable to determine endpoint
        """
        try:
            
            if location:
                # Convert location to endpoint format (e.g., "polandcentral" -> "polandcentral.metrics.monitor.azure.com")
                # Azure locations are typically lowercase and match the endpoint region
                endpoint = f"https://{location}.metrics.monitor.azure.com"
                return endpoint
            else:
                raise ValueError("Unable to determine location for metrics endpoint")
        except Exception as e:
            raise ValueError(f"Failed to get metrics endpoint: {str(e)}")


    @staticmethod
    def cap_granularity(granularity: timedelta) -> timedelta:
        """
        Cap granularity at PT1D (1 day) as that's the maximum supported by Azure Monitor.
        
        Args:
            granularity: Time granularity as timedelta
            
        Returns:
            Capped granularity (maximum PT1D)
        """
        max_granularity = timedelta(days=1)
        return min(granularity, max_granularity)

    @staticmethod
    def cap_granularity(granularity: timedelta, max_granularity: timedelta) -> timedelta:
        """
        Cap granularity at PT1D (1 day) as that's the maximum supported by Azure Monitor.
        
        Args:
            granularity: Time granularity as timedelta
            
        Returns:
            Capped granularity (maximum PT1D)
        """
        return min(granularity, max_granularity)


# ============================================================================
# ExceptionLogger Class
# ============================================================================

class ExceptionLogger:
    """
    Exception Logger class.
    
    Handles lazy, thread-safe exception logging to files.
    Creates log directory and file only when an exception occurs and file doesn't exist.
    """
    
    # Thread lock for lazy log file creation
    _log_file_creation_lock = threading.Lock()
    
    @staticmethod
    def setup_exception_logging(service_name: str = None, base_path: Path = None) -> logging.Logger:
        """
        Set up logging for exceptions to logs directory.
        Logger is configured but file handler is created lazily on first exception.
        
        Args:
            service_name: Service name from config, or None for default
            base_path: Base path for logs directory. If None, uses parent of parent of caller's file.
            
        Returns:
            Logger instance configured for exception logging (file handler created lazily)
        """
        # Use default service name if not provided
        if not service_name:
            service_name = "Azure Monitor"
        
        # Sanitize service name for filesystem (remove invalid characters)
        safe_service_name = "".join(c for c in service_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_service_name = safe_service_name.replace(' ', '_')
        if not safe_service_name:
            safe_service_name = "Azure_Monitor"
        
        # Determine logs base directory
        if base_path is None:
            # Default: assume logs directory is at project root (3 levels up from src/utils.py)
            base_path = Path(__file__).parent.parent
        logs_base = base_path / "logs"
        service_log_dir = logs_base / safe_service_name
        log_filename = datetime.now().strftime("%Y%m%d.log")
        log_file_path = service_log_dir / log_filename
        
        # Set up logger
        logger = logging.getLogger(f"azure_monitor_{safe_service_name}")
        logger.setLevel(logging.ERROR)  # Only log errors/exceptions
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Prevent propagation to root logger (which might print to console)
        logger.propagate = False
        
        # Store log file path and directory as attributes for lazy creation
        logger._log_file_path = log_file_path
        logger._service_log_dir = service_log_dir
        logger._file_handler_created = False
        
        return logger
    
    @staticmethod
    def _ensure_file_handler(logger: logging.Logger):
        """
        Lazily create file handler for logger if it doesn't exist.
        Thread-safe and only creates directory/file if they don't exist.
        
        Args:
            logger: Logger instance with _log_file_path and _service_log_dir attributes
        """
        # Check if handler already exists (double-check pattern for performance)
        if getattr(logger, '_file_handler_created', False):
            return
        
        # Thread-safe creation
        with ExceptionLogger._log_file_creation_lock:
            # Double-check after acquiring lock
            if getattr(logger, '_file_handler_created', False):
                return
            
            log_file_path = getattr(logger, '_log_file_path', None)
            service_log_dir = getattr(logger, '_service_log_dir', None)
            
            if not log_file_path or not service_log_dir:
                return
            
            # Only create directory if it doesn't exist
            if not service_log_dir.exists():
                service_log_dir.mkdir(parents=True, exist_ok=True)
            
            # Only create file handler if log file doesn't exist
            # FileHandler will create the file on first write, or append if it exists
            if not log_file_path.exists():
                # Create file handler (will create file on first write)
                file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
                file_handler.setLevel(logging.ERROR)
                
                # Create formatter with timestamp
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(formatter)
                
                logger.addHandler(file_handler)
                logger._file_handler_created = True
    
    @staticmethod
    def log_exception(logger: logging.Logger, exception: Exception, exception_type_name: str = None):
        """
        Log exception with full stacktrace.
        Creates log file handler lazily on first exception if file doesn't exist.
        
        Args:
            logger: Logger instance
            exception: Exception instance
            exception_type_name: Optional name for exception type
        """
        # Lazily create file handler if needed (thread-safe)
        ExceptionLogger._ensure_file_handler(logger)
        
        if exception_type_name:
            error_msg = f"{exception_type_name}: {str(exception)}"
        else:
            error_msg = f"{type(exception).__name__}: {str(exception)}"
        
        logger.error(error_msg)
        logger.error("Full traceback:\n%s", traceback.format_exc())
