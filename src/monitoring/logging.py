"""
Structured logging configuration for Email Subject Line Optimizer
"""

import os
import sys
import json
import logging
import logging.handlers
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
import asyncio
from functools import wraps

import structlog
from pythonjsonlogger import jsonlogger


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record"""
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add hostname
        log_record['hostname'] = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        
        # Add process and thread info
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread
        log_record['thread_name'] = record.threadName
        
        # Add code location
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line_number'] = record.lineno
        
        # Add environment
        log_record['environment'] = os.getenv('APP_ENV', 'development')
        log_record['app_name'] = 'email-optimizer'
        log_record['app_version'] = os.getenv('APP_VERSION', '1.0.0')
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
        
        # Add user ID if present
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


class ErrorFilter(logging.Filter):
    """Filter to add error details to log records"""
    
    def filter(self, record):
        """Add error details if exception info is present"""
        if record.exc_info:
            record.error_type = record.exc_info[0].__name__
            record.error_message = str(record.exc_info[1])
            record.error_traceback = traceback.format_exception(*record.exc_info)
        return True


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records"""
    
    def __init__(self):
        super().__init__()
        self.correlation_id = None
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current context"""
        self.correlation_id = correlation_id
    
    def filter(self, record):
        """Add correlation ID to log record"""
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        return True


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = "json",
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 10,
    include_hostname: bool = True
) -> None:
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None for stdout only)
        log_format: Log format ("json" or "text")
        max_bytes: Max size of log file before rotation
        backup_count: Number of backup files to keep
        include_hostname: Include hostname in logs
    """
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Create formatters
    if log_format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            json_ensure_ascii=False
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ErrorFilter())
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ErrorFilter())
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Log startup message
    root_logger.info(
        "Logging initialized",
        extra={
            "log_level": log_level,
            "log_format": log_format,
            "log_file": log_file,
            "hostname": os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        }
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def log_request(
    method: str,
    path: str,
    client_ip: str,
    headers: Dict[str, str],
    correlation_id: Optional[str] = None
) -> None:
    """
    Log incoming HTTP request
    
    Args:
        method: HTTP method
        path: Request path
        client_ip: Client IP address
        headers: Request headers
        correlation_id: Request correlation ID
    """
    logger = get_logger("http.request")
    logger.info(
        "Request received",
        method=method,
        path=path,
        client_ip=client_ip,
        user_agent=headers.get("user-agent", "unknown"),
        correlation_id=correlation_id
    )


def log_response(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    correlation_id: Optional[str] = None
) -> None:
    """
    Log HTTP response
    
    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        correlation_id: Request correlation ID
    """
    logger = get_logger("http.response")
    
    log_method = logger.info
    if status_code >= 500:
        log_method = logger.error
    elif status_code >= 400:
        log_method = logger.warning
    
    log_method(
        "Request completed",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        correlation_id=correlation_id
    )


def log_error(
    error: Exception,
    context: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> None:
    """
    Log error with context
    
    Args:
        error: Exception instance
        context: Additional context
        correlation_id: Request correlation ID
    """
    logger = get_logger("error")
    logger.error(
        f"Error occurred: {str(error)}",
        error_type=type(error).__name__,
        error_message=str(error),
        error_traceback=traceback.format_exc(),
        context=context,
        correlation_id=correlation_id,
        exc_info=True
    )


def log_ai_request(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    success: bool,
    correlation_id: Optional[str] = None
) -> None:
    """
    Log AI provider request
    
    Args:
        provider: AI provider name
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        duration_ms: Request duration in milliseconds
        success: Whether request was successful
        correlation_id: Request correlation ID
    """
    logger = get_logger("ai.request")
    log_method = logger.info if success else logger.warning
    
    log_method(
        "AI request completed",
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        duration_ms=duration_ms,
        success=success,
        correlation_id=correlation_id
    )


def log_cache_operation(
    operation: str,
    key: str,
    hit: bool,
    duration_ms: float,
    correlation_id: Optional[str] = None
) -> None:
    """
    Log cache operation
    
    Args:
        operation: Cache operation (get, set, delete)
        key: Cache key
        hit: Whether it was a cache hit
        duration_ms: Operation duration in milliseconds
        correlation_id: Request correlation ID
    """
    logger = get_logger("cache")
    logger.debug(
        f"Cache {operation}",
        operation=operation,
        key=key,
        hit=hit,
        duration_ms=duration_ms,
        correlation_id=correlation_id
    )


def log_database_operation(
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: int = 0,
    correlation_id: Optional[str] = None
) -> None:
    """
    Log database operation
    
    Args:
        operation: Database operation (select, insert, update, delete)
        table: Table name
        duration_ms: Operation duration in milliseconds
        rows_affected: Number of rows affected
        correlation_id: Request correlation ID
    """
    logger = get_logger("database")
    logger.debug(
        f"Database {operation}",
        operation=operation,
        table=table,
        duration_ms=duration_ms,
        rows_affected=rows_affected,
        correlation_id=correlation_id
    )


# Decorators for automatic logging
def log_execution(func_name: Optional[str] = None):
    """Decorator to log function execution"""
    def decorator(func):
        name = func_name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = datetime.utcnow()
            
            logger.debug(f"Executing {name}", function=name, args=args, kwargs=kwargs)
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.debug(
                    f"Completed {name}",
                    function=name,
                    duration_ms=duration_ms,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"Failed {name}",
                    function=name,
                    duration_ms=duration_ms,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = datetime.utcnow()
            
            logger.debug(f"Executing {name}", function=name)
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.debug(
                    f"Completed {name}",
                    function=name,
                    duration_ms=duration_ms,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"Failed {name}",
                    function=name,
                    duration_ms=duration_ms,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


@contextmanager
def log_context(**kwargs):
    """Context manager to add context to logs"""
    logger = structlog.get_logger()
    try:
        logger = logger.bind(**kwargs)
        yield logger
    finally:
        logger = logger.unbind(*kwargs.keys())


# Sentry integration (optional)
def setup_sentry(dsn: Optional[str] = None, environment: str = "production"):
    """
    Setup Sentry error tracking
    
    Args:
        dsn: Sentry DSN
        environment: Environment name
    """
    if not dsn:
        return
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        
        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[
                sentry_logging,
                SqlalchemyIntegration(),
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            attach_stacktrace=True,
            send_default_pii=False,
            before_send=lambda event, hint: event if event.get("level") != "debug" else None
        )
        
        logging.info("Sentry initialized successfully")
    except ImportError:
        logging.warning("Sentry SDK not installed, skipping Sentry setup")
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {e}")