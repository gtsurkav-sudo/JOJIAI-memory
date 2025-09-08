
"""Monitoring and metrics system for JOJI Oi."""

import time
import logging
import threading
from typing import Any, Dict, List, Optional
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
from pythonjsonlogger import jsonlogger

# Prometheus metrics
OPERATION_COUNTER = Counter(
    'jojiai_operations_total',
    'Total number of operations',
    ['operation_type', 'status']
)

OPERATION_DURATION = Histogram(
    'jojiai_operation_duration_seconds',
    'Operation duration in seconds',
    ['operation_type']
)

MEMORY_USAGE = Gauge(
    'jojiai_memory_usage_bytes',
    'Memory usage in bytes',
    ['memory_type']
)

ERROR_COUNTER = Counter(
    'jojiai_errors_total',
    'Total number of errors',
    ['error_type', 'component']
)

RETRY_COUNTER = Counter(
    'jojiai_retries_total',
    'Total number of retries',
    ['operation_type']
)

CONCURRENT_OPERATIONS = Gauge(
    'jojiai_concurrent_operations',
    'Number of concurrent operations',
    ['operation_type']
)

SYSTEM_INFO = Info(
    'jojiai_system_info',
    'System information'
)


class StructuredLogger:
    """Structured JSON logger for JOJI Oi."""
    
    def __init__(self, name: str, level: str = 'INFO', log_file: Optional[str] = None):
        """Initialize structured logger.
        
        Args:
            name: Logger name
            level: Log level
            log_file: Optional log file path
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create JSON formatter
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self.logger.debug(message, extra=kwargs)


class MetricsCollector:
    """Collects and manages system metrics."""
    
    def __init__(self, port: int = 8000):
        """Initialize metrics collector.
        
        Args:
            port: Port for metrics HTTP server
        """
        self.port = port
        self.logger = StructuredLogger('metrics')
        self._start_metrics_server()
        
        # Initialize system info
        SYSTEM_INFO.info({
            'version': '1.0.0',
            'component': 'jojiai',
            'start_time': str(time.time())
        })
    
    def _start_metrics_server(self):
        """Start Prometheus metrics HTTP server."""
        try:
            start_http_server(self.port)
            self.logger.info(f"Metrics server started on port {self.port}")
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
    
    def record_operation(self, operation_type: str, duration: float, status: str = 'success'):
        """Record operation metrics.
        
        Args:
            operation_type: Type of operation
            duration: Operation duration in seconds
            status: Operation status (success, error)
        """
        OPERATION_COUNTER.labels(operation_type=operation_type, status=status).inc()
        OPERATION_DURATION.labels(operation_type=operation_type).observe(duration)
        
        self.logger.debug(
            "Operation recorded",
            operation_type=operation_type,
            duration=duration,
            status=status
        )
    
    def record_error(self, error_type: str, component: str):
        """Record error metrics.
        
        Args:
            error_type: Type of error
            component: Component where error occurred
        """
        ERROR_COUNTER.labels(error_type=error_type, component=component).inc()
        
        self.logger.warning(
            "Error recorded",
            error_type=error_type,
            component=component
        )
    
    def record_retry(self, operation_type: str):
        """Record retry metrics.
        
        Args:
            operation_type: Type of operation being retried
        """
        RETRY_COUNTER.labels(operation_type=operation_type).inc()
        
        self.logger.debug(
            "Retry recorded",
            operation_type=operation_type
        )
    
    def set_memory_usage(self, memory_type: str, bytes_used: int):
        """Set memory usage metrics.
        
        Args:
            memory_type: Type of memory (heap, file, cache)
            bytes_used: Memory usage in bytes
        """
        MEMORY_USAGE.labels(memory_type=memory_type).set(bytes_used)
    
    def increment_concurrent_operations(self, operation_type: str):
        """Increment concurrent operations counter.
        
        Args:
            operation_type: Type of operation
        """
        CONCURRENT_OPERATIONS.labels(operation_type=operation_type).inc()
    
    def decrement_concurrent_operations(self, operation_type: str):
        """Decrement concurrent operations counter.
        
        Args:
            operation_type: Type of operation
        """
        CONCURRENT_OPERATIONS.labels(operation_type=operation_type).dec()


# Global metrics collector instance
metrics_collector = MetricsCollector()


def monitor_operation(operation_type: str):
    """Decorator to monitor operation metrics.
    
    Args:
        operation_type: Type of operation to monitor
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics_collector.increment_concurrent_operations(operation_type)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics_collector.record_operation(operation_type, duration, 'success')
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.record_operation(operation_type, duration, 'error')
                metrics_collector.record_error(type(e).__name__, func.__module__)
                raise
                
            finally:
                metrics_collector.decrement_concurrent_operations(operation_type)
        
        return wrapper
    return decorator


class HealthChecker:
    """System health monitoring."""
    
    def __init__(self):
        """Initialize health checker."""
        self.logger = StructuredLogger('health')
        self.checks = {}
        self._start_health_monitoring()
    
    def register_check(self, name: str, check_func, interval: float = 60.0):
        """Register health check.
        
        Args:
            name: Check name
            check_func: Function that returns True if healthy
            interval: Check interval in seconds
        """
        self.checks[name] = {
            'func': check_func,
            'interval': interval,
            'last_check': 0,
            'status': 'unknown'
        }
        
        self.logger.info(f"Health check registered: {name}")
    
    def _start_health_monitoring(self):
        """Start background health monitoring."""
        def monitor():
            while True:
                current_time = time.time()
                
                for name, check in self.checks.items():
                    if current_time - check['last_check'] >= check['interval']:
                        try:
                            is_healthy = check['func']()
                            check['status'] = 'healthy' if is_healthy else 'unhealthy'
                            check['last_check'] = current_time
                            
                            if not is_healthy:
                                self.logger.warning(f"Health check failed: {name}")
                                
                        except Exception as e:
                            check['status'] = 'error'
                            check['last_check'] = current_time
                            self.logger.error(f"Health check error: {name}", error=str(e))
                
                time.sleep(10)  # Check every 10 seconds
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status.
        
        Returns:
            Health status dictionary
        """
        overall_status = 'healthy'
        check_results = {}
        
        for name, check in self.checks.items():
            check_results[name] = {
                'status': check['status'],
                'last_check': check['last_check']
            }
            
            if check['status'] in ['unhealthy', 'error']:
                overall_status = 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'checks': check_results,
            'timestamp': time.time()
        }


# Global health checker instance
health_checker = HealthChecker()


class AlertManager:
    """Alert management system."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.logger = StructuredLogger('alerts')
        self.alert_rules = []
        self.active_alerts = {}
    
    def add_rule(self, name: str, condition_func, severity: str = 'warning'):
        """Add alert rule.
        
        Args:
            name: Alert rule name
            condition_func: Function that returns True if alert should fire
            severity: Alert severity (info, warning, critical)
        """
        self.alert_rules.append({
            'name': name,
            'condition': condition_func,
            'severity': severity
        })
        
        self.logger.info(f"Alert rule added: {name}")
    
    def check_alerts(self):
        """Check all alert rules and fire alerts if needed."""
        for rule in self.alert_rules:
            try:
                should_alert = rule['condition']()
                
                if should_alert and rule['name'] not in self.active_alerts:
                    # Fire alert
                    alert = {
                        'name': rule['name'],
                        'severity': rule['severity'],
                        'timestamp': time.time(),
                        'status': 'firing'
                    }
                    
                    self.active_alerts[rule['name']] = alert
                    self._send_alert(alert)
                    
                elif not should_alert and rule['name'] in self.active_alerts:
                    # Resolve alert
                    alert = self.active_alerts[rule['name']]
                    alert['status'] = 'resolved'
                    alert['resolved_timestamp'] = time.time()
                    
                    self._send_alert(alert)
                    del self.active_alerts[rule['name']]
                    
            except Exception as e:
                self.logger.error(f"Alert rule check failed: {rule['name']}", error=str(e))
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Send alert notification.
        
        Args:
            alert: Alert information
        """
        if alert['status'] == 'firing':
            self.logger.warning(
                f"ALERT FIRING: {alert['name']}",
                severity=alert['severity'],
                timestamp=alert['timestamp']
            )
        else:
            self.logger.info(
                f"ALERT RESOLVED: {alert['name']}",
                resolved_timestamp=alert['resolved_timestamp']
            )
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of active alerts.
        
        Returns:
            List of active alerts
        """
        return list(self.active_alerts.values())


# Global alert manager instance
alert_manager = AlertManager()
