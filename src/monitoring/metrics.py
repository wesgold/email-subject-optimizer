"""
Prometheus metrics collection for Email Subject Line Optimizer
"""

import time
import psutil
import asyncio
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager
from datetime import datetime

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from prometheus_client.multiprocess import MultiProcessCollector
from fastapi import Response
import os

# Create a custom registry for our metrics
registry = CollectorRegistry()

# System Information
system_info = Info(
    "email_optimizer_info",
    "Email Optimizer system information",
    registry=registry
)

# Request Metrics
http_requests_total = Counter(
    "email_optimizer_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry
)

http_request_duration_seconds = Histogram(
    "email_optimizer_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

http_request_size_bytes = Summary(
    "email_optimizer_http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    registry=registry
)

http_response_size_bytes = Summary(
    "email_optimizer_http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    registry=registry
)

# AI Provider Metrics
ai_requests_total = Counter(
    "email_optimizer_ai_requests_total",
    "Total AI provider requests",
    ["provider", "model", "status"],
    registry=registry
)

ai_request_duration_seconds = Histogram(
    "email_optimizer_ai_request_duration_seconds",
    "AI provider request duration in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
    registry=registry
)

ai_tokens_used = Counter(
    "email_optimizer_ai_tokens_used_total",
    "Total AI tokens used",
    ["provider", "model", "type"],  # type: prompt, completion
    registry=registry
)

# Cache Metrics
cache_operations_total = Counter(
    "email_optimizer_cache_operations_total",
    "Total cache operations",
    ["operation", "status"],  # operation: get, set, delete; status: hit, miss, error
    registry=registry
)

cache_size_bytes = Gauge(
    "email_optimizer_cache_size_bytes",
    "Current cache size in bytes",
    registry=registry
)

# Database Metrics
db_operations_total = Counter(
    "email_optimizer_db_operations_total",
    "Total database operations",
    ["operation", "table", "status"],
    registry=registry
)

db_operation_duration_seconds = Histogram(
    "email_optimizer_db_operation_duration_seconds",
    "Database operation duration in seconds",
    ["operation", "table"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=registry
)

db_connections_active = Gauge(
    "email_optimizer_db_connections_active",
    "Active database connections",
    registry=registry
)

# Business Metrics
subjects_generated_total = Counter(
    "email_optimizer_subjects_generated_total",
    "Total subject lines generated",
    ["status"],
    registry=registry
)

ab_tests_created_total = Counter(
    "email_optimizer_ab_tests_created_total",
    "Total A/B tests created",
    registry=registry
)

email_opens_total = Counter(
    "email_optimizer_email_opens_total",
    "Total email opens tracked",
    ["subject_id"],
    registry=registry
)

email_clicks_total = Counter(
    "email_optimizer_email_clicks_total",
    "Total email clicks tracked",
    ["subject_id"],
    registry=registry
)

mab_selections_total = Counter(
    "email_optimizer_mab_selections_total",
    "Total Multi-Armed Bandit selections",
    ["algorithm", "selected_variant"],
    registry=registry
)

# System Metrics
cpu_usage_percent = Gauge(
    "email_optimizer_cpu_usage_percent",
    "CPU usage percentage",
    registry=registry
)

memory_usage_bytes = Gauge(
    "email_optimizer_memory_usage_bytes",
    "Memory usage in bytes",
    ["type"],  # type: rss, vms, available
    registry=registry
)

disk_usage_percent = Gauge(
    "email_optimizer_disk_usage_percent",
    "Disk usage percentage",
    registry=registry
)

# Error Metrics
errors_total = Counter(
    "email_optimizer_errors_total",
    "Total errors",
    ["type", "component"],
    registry=registry
)

# Rate Limiting Metrics
rate_limit_exceeded_total = Counter(
    "email_optimizer_rate_limit_exceeded_total",
    "Total rate limit exceeded events",
    ["client_id"],
    registry=registry
)


class MetricsCollector:
    """Metrics collector for the application"""
    
    def __init__(self, app_version: str = "1.0.0"):
        """Initialize metrics collector"""
        self.app_version = app_version
        self._setup_info_metrics()
        self._start_system_metrics_collection()
    
    def _setup_info_metrics(self):
        """Setup application info metrics"""
        system_info.info({
            "version": self.app_version,
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "hostname": os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        })
    
    def _start_system_metrics_collection(self):
        """Start background task to collect system metrics"""
        asyncio.create_task(self._collect_system_metrics())
    
    async def _collect_system_metrics(self):
        """Collect system metrics periodically"""
        while True:
            try:
                # CPU usage
                cpu_usage_percent.set(psutil.cpu_percent(interval=1))
                
                # Memory usage
                memory = psutil.virtual_memory()
                memory_usage_bytes.labels(type="rss").set(memory.rss)
                memory_usage_bytes.labels(type="vms").set(memory.vms if hasattr(memory, 'vms') else 0)
                memory_usage_bytes.labels(type="available").set(memory.available)
                
                # Disk usage
                disk = psutil.disk_usage('/')
                disk_usage_percent.set(disk.percent)
                
            except Exception as e:
                errors_total.labels(type="system_metrics", component="collector").inc()
            
            await asyncio.sleep(30)  # Collect every 30 seconds
    
    @staticmethod
    def track_request(method: str, endpoint: str, status: int, duration: float, 
                     request_size: int = 0, response_size: int = 0):
        """Track HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        
        if request_size > 0:
            http_request_size_bytes.labels(method=method, endpoint=endpoint).observe(request_size)
        if response_size > 0:
            http_response_size_bytes.labels(method=method, endpoint=endpoint).observe(response_size)
    
    @staticmethod
    def track_ai_request(provider: str, model: str, status: str, duration: float,
                        prompt_tokens: int = 0, completion_tokens: int = 0):
        """Track AI provider request metrics"""
        ai_requests_total.labels(provider=provider, model=model, status=status).inc()
        ai_request_duration_seconds.labels(provider=provider, model=model).observe(duration)
        
        if prompt_tokens > 0:
            ai_tokens_used.labels(provider=provider, model=model, type="prompt").inc(prompt_tokens)
        if completion_tokens > 0:
            ai_tokens_used.labels(provider=provider, model=model, type="completion").inc(completion_tokens)
    
    @staticmethod
    def track_cache_operation(operation: str, status: str):
        """Track cache operation metrics"""
        cache_operations_total.labels(operation=operation, status=status).inc()
    
    @staticmethod
    def track_db_operation(operation: str, table: str, status: str, duration: float):
        """Track database operation metrics"""
        db_operations_total.labels(operation=operation, table=table, status=status).inc()
        db_operation_duration_seconds.labels(operation=operation, table=table).observe(duration)
    
    @staticmethod
    def track_business_metric(metric_type: str, **labels):
        """Track business metrics"""
        if metric_type == "subject_generated":
            subjects_generated_total.labels(status=labels.get("status", "success")).inc()
        elif metric_type == "ab_test_created":
            ab_tests_created_total.inc()
        elif metric_type == "email_open":
            email_opens_total.labels(subject_id=labels.get("subject_id", "unknown")).inc()
        elif metric_type == "email_click":
            email_clicks_total.labels(subject_id=labels.get("subject_id", "unknown")).inc()
        elif metric_type == "mab_selection":
            mab_selections_total.labels(
                algorithm=labels.get("algorithm", "thompson"),
                selected_variant=labels.get("variant", "unknown")
            ).inc()
    
    @staticmethod
    def track_error(error_type: str, component: str):
        """Track error metrics"""
        errors_total.labels(type=error_type, component=component).inc()
    
    @staticmethod
    def track_rate_limit_exceeded(client_id: str):
        """Track rate limit exceeded events"""
        rate_limit_exceeded_total.labels(client_id=client_id).inc()


# Decorator for tracking request duration
def track_request_duration(endpoint: str):
    """Decorator to track request duration"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                http_request_duration_seconds.labels(
                    method=kwargs.get("request", {}).get("method", "GET"),
                    endpoint=endpoint
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                http_request_duration_seconds.labels(
                    method=kwargs.get("request", {}).get("method", "GET"),
                    endpoint=endpoint
                ).observe(duration)
                errors_total.labels(type="request", component=endpoint).inc()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                http_request_duration_seconds.labels(
                    method="GET",
                    endpoint=endpoint
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                http_request_duration_seconds.labels(
                    method="GET",
                    endpoint=endpoint
                ).observe(duration)
                errors_total.labels(type="request", component=endpoint).inc()
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Context manager for tracking operations
@contextmanager
def track_operation(operation_type: str, **labels):
    """Context manager to track operation duration"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if operation_type == "db":
            db_operation_duration_seconds.labels(
                operation=labels.get("operation", "unknown"),
                table=labels.get("table", "unknown")
            ).observe(duration)
        elif operation_type == "ai":
            ai_request_duration_seconds.labels(
                provider=labels.get("provider", "unknown"),
                model=labels.get("model", "unknown")
            ).observe(duration)


# Helper functions
def track_api_call(provider: str, model: str, success: bool = True):
    """Track AI API call"""
    status = "success" if success else "error"
    ai_requests_total.labels(provider=provider, model=model, status=status).inc()


def track_cache_hit(hit: bool = True):
    """Track cache hit/miss"""
    status = "hit" if hit else "miss"
    cache_operations_total.labels(operation="get", status=status).inc()


def track_error(error_type: str, component: str):
    """Track error occurrence"""
    errors_total.labels(type=error_type, component=component).inc()


def get_metrics_handler():
    """Get metrics handler for FastAPI"""
    async def metrics_endpoint():
        """Prometheus metrics endpoint"""
        # Add multiprocess mode support if needed
        if "prometheus_multiproc_dir" in os.environ:
            registry_with_multiprocess = CollectorRegistry()
            MultiProcessCollector(registry_with_multiprocess)
            metrics = generate_latest(registry_with_multiprocess)
        else:
            metrics = generate_latest(registry)
        
        return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)
    
    return metrics_endpoint


# Initialize global metrics collector
metrics_collector = None

def init_metrics(app_version: str = "1.0.0"):
    """Initialize metrics collector"""
    global metrics_collector
    metrics_collector = MetricsCollector(app_version)
    return metrics_collector