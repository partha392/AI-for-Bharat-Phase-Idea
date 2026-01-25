"""
Monitoring and metrics collection for the Bharat Voice Assistant.

This module provides comprehensive monitoring capabilities including health checks,
metrics collection, alerting, and integration with AWS CloudWatch.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from .config import config
from .logging import get_logger, get_performance_logger


logger = get_logger(__name__)
performance_logger = get_performance_logger()


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_function: Callable[[], bool]
    timeout_seconds: int = 30
    critical: bool = True
    description: str = ""


@dataclass
class Metric:
    """Metric data point."""
    name: str
    value: float
    timestamp: datetime
    unit: str = "Count"
    dimensions: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and manages application metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, dimensions: Dict[str, str] = None):
        """Increment a counter metric."""
        with self._lock:
            self.counters[name] += value
            self._add_metric(name, value, "Count", dimensions or {})
    
    def set_gauge(self, name: str, value: float, dimensions: Dict[str, str] = None):
        """Set a gauge metric value."""
        with self._lock:
            self.gauges[name] = value
            self._add_metric(name, value, "None", dimensions or {})
    
    def record_timer(self, name: str, duration_ms: float, dimensions: Dict[str, str] = None):
        """Record a timer metric."""
        with self._lock:
            self.timers[name].append(duration_ms)
            # Keep only last 100 timer values
            if len(self.timers[name]) > 100:
                self.timers[name] = self.timers[name][-100:]
            self._add_metric(name, duration_ms, "Milliseconds", dimensions or {})
    
    def _add_metric(self, name: str, value: float, unit: str, dimensions: Dict[str, str]):
        """Add a metric to the collection."""
        metric = Metric(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            unit=unit,
            dimensions=dimensions
        )
        self.metrics[name].append(metric)
    
    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        return self.counters.get(name, 0)
    
    def get_gauge(self, name: str) -> float:
        """Get current gauge value."""
        return self.gauges.get(name, 0.0)
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics."""
        values = self.timers.get(name, [])
        if not values:
            return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
        
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "p95": sorted(values)[int(len(values) * 0.95)] if len(values) > 0 else 0.0
        }
    
    def get_recent_metrics(self, name: str, minutes: int = 5) -> List[Metric]:
        """Get metrics from the last N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [m for m in self.metrics.get(name, []) if m.timestamp >= cutoff]
    
    def reset_counters(self):
        """Reset all counters to zero."""
        with self._lock:
            self.counters.clear()


class HealthMonitor:
    """Monitors system health and component status."""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.last_check_results: Dict[str, bool] = {}
        self.last_check_times: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check."""
        with self._lock:
            self.health_checks[health_check.name] = health_check
            logger.info(f"Registered health check: {health_check.name}")
    
    def run_health_check(self, name: str) -> bool:
        """Run a specific health check."""
        if name not in self.health_checks:
            logger.error(f"Health check not found: {name}")
            return False
        
        health_check = self.health_checks[name]
        
        try:
            start_time = time.time()
            result = health_check.check_function()
            duration = (time.time() - start_time) * 1000
            
            with self._lock:
                self.last_check_results[name] = result
                self.last_check_times[name] = datetime.utcnow()
            
            # Log the result
            level = "info" if result else "error"
            getattr(logger, level)(
                f"Health check {name}: {'PASS' if result else 'FAIL'} ({duration:.2f}ms)",
                extra={'component': 'health_monitor', 'health_check': name, 'result': result}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Health check {name} failed with exception: {e}", exc_info=True)
            with self._lock:
                self.last_check_results[name] = False
                self.last_check_times[name] = datetime.utcnow()
            return False
    
    def run_all_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks."""
        results = {}
        for name in self.health_checks:
            results[name] = self.run_health_check(name)
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        with self._lock:
            critical_checks = [
                name for name, check in self.health_checks.items() 
                if check.critical
            ]
            
            critical_failures = [
                name for name in critical_checks 
                if not self.last_check_results.get(name, False)
            ]
            
            overall_healthy = len(critical_failures) == 0
            
            return {
                "healthy": overall_healthy,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    name: {
                        "status": "pass" if self.last_check_results.get(name, False) else "fail",
                        "last_check": self.last_check_times.get(name, datetime.min).isoformat(),
                        "critical": self.health_checks[name].critical,
                        "description": self.health_checks[name].description
                    }
                    for name in self.health_checks
                },
                "critical_failures": critical_failures
            }


class CloudWatchPublisher:
    """Publishes metrics to AWS CloudWatch."""
    
    def __init__(self):
        self.enabled = BOTO3_AVAILABLE and not config.is_development()
        self.namespace = "BharatVoiceAssistant"
        
        if self.enabled:
            try:
                self.cloudwatch = boto3.client('cloudwatch', **config.get_aws_credentials())
                logger.info("CloudWatch publisher initialized")
            except Exception as e:
                logger.error(f"Failed to initialize CloudWatch client: {e}")
                self.enabled = False
        else:
            logger.info("CloudWatch publisher disabled (development mode or boto3 not available)")
    
    def publish_metrics(self, metrics: List[Metric]):
        """Publish metrics to CloudWatch."""
        if not self.enabled or not metrics:
            return
        
        try:
            # CloudWatch accepts max 20 metrics per request
            for i in range(0, len(metrics), 20):
                batch = metrics[i:i+20]
                metric_data = []
                
                for metric in batch:
                    metric_data.append({
                        'MetricName': metric.name,
                        'Value': metric.value,
                        'Unit': metric.unit,
                        'Timestamp': metric.timestamp,
                        'Dimensions': [
                            {'Name': k, 'Value': v} 
                            for k, v in metric.dimensions.items()
                        ]
                    })
                
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metric_data
                )
                
            logger.debug(f"Published {len(metrics)} metrics to CloudWatch")
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
        except Exception as e:
            logger.error(f"Unexpected error publishing metrics: {e}")


class Monitor:
    """Main monitoring class that coordinates metrics collection and health monitoring."""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.health = HealthMonitor()
        self.cloudwatch = CloudWatchPublisher()
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        # Register default health checks
        self._register_default_health_checks()
    
    def _register_default_health_checks(self):
        """Register default system health checks."""
        
        def check_memory_usage():
            """Check if memory usage is within acceptable limits."""
            try:
                import psutil
                memory_percent = psutil.virtual_memory().percent
                return memory_percent < 90  # Alert if memory usage > 90%
            except ImportError:
                return True  # Skip check if psutil not available
        
        def check_disk_space():
            """Check if disk space is sufficient."""
            try:
                import psutil
                disk_usage = psutil.disk_usage('/').percent
                return disk_usage < 85  # Alert if disk usage > 85%
            except ImportError:
                return True  # Skip check if psutil not available
        
        def check_aws_connectivity():
            """Check AWS service connectivity."""
            if not BOTO3_AVAILABLE:
                return True  # Skip if boto3 not available
            
            try:
                # Simple STS call to check AWS connectivity
                sts = boto3.client('sts', **config.get_aws_credentials())
                sts.get_caller_identity()
                return True
            except Exception:
                return False
        
        # Register health checks
        self.health.register_health_check(HealthCheck(
            name="memory_usage",
            check_function=check_memory_usage,
            critical=True,
            description="System memory usage check"
        ))
        
        self.health.register_health_check(HealthCheck(
            name="disk_space",
            check_function=check_disk_space,
            critical=True,
            description="System disk space check"
        ))
        
        self.health.register_health_check(HealthCheck(
            name="aws_connectivity",
            check_function=check_aws_connectivity,
            critical=True,
            description="AWS services connectivity check"
        ))
    
    def start_monitoring(self, interval_seconds: int = 60):
        """Start background monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Monitoring thread already running")
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitoring_thread.start()
        logger.info(f"Started monitoring thread with {interval_seconds}s interval")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        if self._monitoring_thread:
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5)
            logger.info("Stopped monitoring thread")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Background monitoring loop."""
        while not self._stop_monitoring.wait(interval_seconds):
            try:
                # Run health checks
                self.health.run_all_health_checks()
                
                # Collect and publish metrics
                self._collect_system_metrics()
                self._publish_metrics_to_cloudwatch()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
    
    def _collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            self.metrics.set_gauge("system.cpu_usage_percent", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.set_gauge("system.memory_usage_percent", memory.percent)
            self.metrics.set_gauge("system.memory_available_mb", memory.available / 1024 / 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.metrics.set_gauge("system.disk_usage_percent", disk.percent)
            self.metrics.set_gauge("system.disk_free_gb", disk.free / 1024 / 1024 / 1024)
            
        except ImportError:
            pass  # Skip system metrics if psutil not available
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _publish_metrics_to_cloudwatch(self):
        """Publish recent metrics to CloudWatch."""
        try:
            # Get metrics from the last 5 minutes
            recent_metrics = []
            for metric_name in self.metrics.metrics:
                recent_metrics.extend(self.metrics.get_recent_metrics(metric_name, minutes=5))
            
            if recent_metrics:
                self.cloudwatch.publish_metrics(recent_metrics)
                
        except Exception as e:
            logger.error(f"Error publishing metrics to CloudWatch: {e}")


# Global monitor instance
monitor = Monitor()