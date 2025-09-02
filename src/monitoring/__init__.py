"""
Monitoring and observability module for Email Subject Line Optimizer
"""

from .metrics import (
    MetricsCollector,
    track_request_duration,
    track_api_call,
    track_cache_hit,
    track_error,
    get_metrics_handler
)

from .logging import (
    setup_logging,
    get_logger,
    log_request,
    log_response,
    log_error
)

__all__ = [
    "MetricsCollector",
    "track_request_duration",
    "track_api_call",
    "track_cache_hit",
    "track_error",
    "get_metrics_handler",
    "setup_logging",
    "get_logger",
    "log_request",
    "log_response",
    "log_error"
]