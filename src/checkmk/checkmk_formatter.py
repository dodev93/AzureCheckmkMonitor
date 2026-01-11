#!/usr/bin/env python3
"""
Checkmk Formatter Module

Centralized Checkmk output formatting with support for:
- Multiple service lines
- Threshold evaluation
- Performance data formatting
- Metric result classes
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Union


# ============================================================================
# Metric Result Classes
# ============================================================================

@dataclass
class MetricProblem:
    """Represents a problematic metadata value that exceeds thresholds."""
    problem_name: str  # The metadata value (e.g., "api-id-1", "PutBlob")
    problem_value: Optional[float] = None  # The problematic metric value (None if problem_message is used)
    metadata_key: Optional[str] = None  # The metadata key used (e.g., "ApiId", "OperationName")
    problem_message: Optional[str] = None  # Human-readable problem message (used when problem_value is None)

@dataclass
class Metric:
    """Represents a single metric with its value and thresholds."""
    name: str
    value: float
    warn_threshold: Optional[float]
    crit_threshold: Optional[float]
    min_value: Optional[float]
    max_value: Optional[float]
    unit: str
    
    def evaluate_status(self) -> int:
        """
        Evaluate status code based on value and thresholds.
        
        Returns:
            Status code: 0=OK, 1=WARN, 2=CRIT
        """
        return CheckmkFormatter.evaluate_status(self.value, self.warn_threshold, self.crit_threshold)
    
    def has_thresholds(self) -> bool:
        """
        Check if this metric has any thresholds defined.
        
        Returns:
            True if warn_threshold or crit_threshold is not None
        """
        return self.warn_threshold is not None or self.crit_threshold is not None


@dataclass
class MetricResult:
    """Result containing multiple metrics for a single service line."""
    service_name: Optional[str]
    metrics: List[Metric]
    problems: Optional[List[MetricProblem]] = None
    _status: Union[int, str] = field(init=False, repr=False)  # Computed status
    _message: str = field(init=False, repr=False)  # Computed message
    
    def __post_init__(self):
        """Calculate status after initialization."""
        self._status = self._calculate_status(self.metrics)
        self._message = None  # Will be computed lazily
    
    @property
    def status(self) -> Union[int, str]:
        """Get the calculated status."""
        return self._status
    
    @property
    def message(self) -> str:
        """Generate message based on metrics and problematic APIs."""
        if self._message is None:
            self._message = self._generate_message()
        return self._message
    
    def _generate_message(self) -> str:
        """
        Generate message based on metrics and problematic metadata.
        
        Message format:
        - "OK" if no problems
        - "Problems: <metadata_key>: <problem1> ; <problem2> . ..." for metadata problems
        - "Problem detected" when only metric problems exist (no metadata problems)
        - Metadata problems are shown when present, metric problems are not included in message
        
        Returns:
            Human-readable status message
        """
        message_parts = []
        
        # Check for problematic metadata (metadata problems)
        if self.problems:
            # Group by metadata_key for better message formatting
            metadata_groups = {}
            for problem in self.problems:
                key = problem.metadata_key or "metadata"
                if key not in metadata_groups:
                    metadata_groups[key] = []
                metadata_groups[key].append(problem)
            
            # Format message with metadata details
            details = []
            for metadata_key, problems in metadata_groups.items():
                problem_details = []
                for p in sorted(problems, key=lambda x: x.problem_name):
                    if p.problem_message:
                        # Use problem_message if provided
                        problem_details.append(f"{p.problem_name} ({p.problem_message})")
                    elif p.problem_value is not None:
                        # Use problem_value if available
                        problem_details.append(f"{p.problem_name} ({p.problem_value})")
                    else:
                        # Fallback to just problem_name
                        problem_details.append(p.problem_name)
                details.append(f"{metadata_key}: {' ; '.join(problem_details)}")
            
            message_parts.append(f"Problems: {' . '.join(details)}")
        
        # Check for metric problems (but don't add details to message)
        has_metric_problems = False
        for metric in self.metrics:
            metric_status = metric.evaluate_status()
            if metric_status > 0:
                has_metric_problems = True
                break
        
        # If only metric problems exist (no metadata problems), add "Problem detected"
        if has_metric_problems and not self.problems:
            message_parts.append("Problem detected")
        
        # Return combined message or OK
        if message_parts:
            return ". ".join(message_parts)
        
        return "OK"
    

    def _calculate_status(self, metrics: List[Metric]) -> Union[int, str]:
        """
        Calculate overall status from a list of metrics.
        
        This method evaluates all metrics to determine the worst status and checks
        if any metric has thresholds. If thresholds are present, returns "P" 
        (Checkmk will evaluate from performance data), otherwise returns the worst
        numeric status (0=OK, 1=WARN, 2=CRIT).
        
        Args:
            metrics: List of Metric instances to evaluate
            
        Returns:
            Overall status: "P" if any metric has thresholds, otherwise worst numeric status
        """
        # Check if any metric has thresholds
        has_thresholds = any(metric.has_thresholds() for metric in metrics)
        
        # Evaluate status for all metrics to determine worst status
        worst_metric_status = 0
        for metric in metrics:
            metric_status = metric.evaluate_status()
            if metric_status > worst_metric_status:
                worst_metric_status = metric_status
        
        if has_thresholds:
            # If any threshold is defined, status is "P" (Checkmk will evaluate from perf data)
            return "P"
        else:
            # No thresholds, use worst metric status
            return worst_metric_status
    
    def to_service_line_dict(self) -> Dict[str, Any]:
        """
        Convert to service line dictionary format for formatter.
        
        This method is kept for backward compatibility but the logic
        has been moved to CheckmkFormatter.format_single_service_line().
        
        Returns:
            Dictionary with status, service_name, performance_data, and message
        """
        # Format performance data for all metrics
        performance_data = []
        for metric in self.metrics:
            perf_data = CheckmkFormatter.format_metrics_data(
                metric_name=metric.name,
                value=metric.value,
                warn_threshold=metric.warn_threshold,
                crit_threshold=metric.crit_threshold,
                min_value=metric.min_value,
                max_value=metric.max_value,
                unit=metric.unit
            )
            performance_data.append(perf_data)
        
        return {
            'status': self.status,
            'service_name': self.service_name,
            'performance_data': performance_data,
            'message': self.message
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MetricResult(service_name={self.service_name!r}, message={self.message!r}, status={self.status}, metrics_count={len(self.metrics)})"


# ============================================================================
# CheckmkFormatter Class
# ============================================================================

class CheckmkFormatter:
    """
    Checkmk formatter class providing centralized formatting functionality.
    
    This class encapsulates all Checkmk formatting logic including:
    - Status evaluation
    - Performance data formatting
    - Service line formatting
    - Metric result formatting
    """
    
    @staticmethod
    def evaluate_status(value: float, warn_threshold: Optional[float], crit_threshold: Optional[float]) -> int:
        """
        Evaluate status code based on value and thresholds.
        
        Args:
            value: Metric value
            warn_threshold: Warning threshold (None if not set)
            crit_threshold: Critical threshold (None if not set)
            
        Returns:
            Status code: 0=OK, 1=WARN, 2=CRIT
        """
        # If critical threshold is set and value exceeds it, return CRIT
        if crit_threshold is not None:
            if value >= crit_threshold:
                return 2  # CRIT
        
        # If warning threshold is set and value exceeds it, return WARN
        if warn_threshold is not None:
            if value >= warn_threshold:
                return 1  # WARN
        
        return 0  # OK
    
    @staticmethod
    def format_metrics_data(
        metric_name: str,
        value: float,
        warn_threshold: Optional[float] = None,
        crit_threshold: Optional[float] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        unit: str = ""
    ) -> str:
        """
        Format performance data in Checkmk format.
        
        Format: metric=value;warn;crit;min;max
        
        Args:
            metric_name: Metric name
            value: Metric value
            warn_threshold: Warning threshold (None if not set)
            crit_threshold: Critical threshold (None if not set)
            min_value: Minimum value (None if not set)
            max_value: Maximum value (None if not set)
            unit: Unit suffix (e.g., "ms", "B")
            
        Returns:
            Formatted performance data string
        """
        # Format value with unit
        value_str = f"{value:.2f}" if isinstance(value, float) else str(value)
        if unit:
            value_str += unit
        
        # Format thresholds as integers when they're whole numbers, otherwise as strings
        def format_threshold(val):
            if val is None:
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)
        
        # Build threshold string (warn;crit;min;max)
        threshold_str = ";".join([
            format_threshold(warn_threshold),
            format_threshold(crit_threshold),
            format_threshold(min_value),
            format_threshold(max_value)
        ])
        
        return f"{metric_name}={value_str};{threshold_str}"
    
    @staticmethod
    def format_response_line(
        status: Union[int, str],
        service_name: str,
        metrics_data: List[str],
        message: str
    ) -> str:
        """
        Format a single Checkmk service line.
        
        Format: <status> "Service name" <perf_data> <message>
        
        Args:
            status: Status code (0=OK, 1=WARN, 2=CRIT, 3=UNKNOWN, "P"=calculated by Checkmk)
            service_name: Service name (will be quoted)
            performance_data: List of performance data strings
            message: Human-readable message
            
        Returns:
            Formatted Checkmk service line
        """
        # Ensure service name is quoted
        if not (service_name.startswith('"') and service_name.endswith('"')):
            service_name = f'"{service_name}"'
        
        # Combine performance data with pipe separator
        metrics_str = "|".join(metrics_data) if metrics_data else ""
        
        # Build output line
        parts = [str(status), service_name]
        if metrics_str:
            parts.append(metrics_str)
        if message:
            parts.append(message)
        
        return " ".join(parts)

    @staticmethod
    def format_single_response_line(metric_result: MetricResult) -> str:
        """
        Format a single Checkmk service line from a MetricResult instance.
        
        Args:
            metric_result: MetricResult instance to format
                
        Returns:
            Formatted Checkmk service line
        """
        # Format performance data for all metrics
        metrics_data = []
        for metric in metric_result.metrics:
            metrics_data_str = CheckmkFormatter.format_metrics_data(
                metric_name=metric.name,
                value=metric.value,
                warn_threshold=metric.warn_threshold,
                crit_threshold=metric.crit_threshold,
                min_value=metric.min_value,
                max_value=metric.max_value,
                unit=metric.unit
            )
            metrics_data.append(metrics_data_str)
        
        return CheckmkFormatter.format_response_line(
            status=metric_result.status,
            service_name=metric_result.service_name or "",
            metrics_data=metrics_data,
            message=metric_result.message
        )
    

