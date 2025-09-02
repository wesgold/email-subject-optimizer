"""
Production configuration for Email Subject Line Optimizer
"""

import os
import secrets
from typing import List, Optional
from pydantic import BaseSettings, validator
from urllib.parse import urlparse

class ProductionConfig(BaseSettings):
    """Production configuration with secure defaults"""
    
    # Application Settings
    APP_NAME: str = "Email Subject Line Optimizer"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "production"
    DEBUG: bool = False
    TESTING: bool = False
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    API_KEY_HEADER: str = "X-API-Key"
    ALLOWED_HOSTS: List[str] = ["*"]
    TRUSTED_PROXIES: List[str] = ["127.0.0.1"]
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/email_optimizer"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_ECHO: bool = False
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_CONNECTION_TIMEOUT: int = 20
    REDIS_SOCKET_TIMEOUT: int = 5
    
    # Cache Configuration
    CACHE_BACKEND: str = "redis"  # redis or diskcache
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_KEY_PREFIX: str = "email_optimizer:"
    DISK_CACHE_DIR: str = "/app/data/cache"
    
    # AI Provider Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL: str = "gpt-4-turbo-preview"
    AI_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 500
    AI_REQUEST_TIMEOUT: int = 30
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_PER_DAY: int = 10000
    RATE_LIMIT_STORAGE: str = "redis"
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "/app/logs/app.log"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 10
    LOG_INCLUDE_HOSTNAME: bool = True
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_METRICS_PATH: str = "/metrics"
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_ENVIRONMENT: str = "production"
    
    # Health Check
    HEALTH_CHECK_PATH: str = "/health"
    HEALTH_CHECK_INCLUDE_DETAILS: bool = True
    
    # Email Tracking
    TRACKING_ENABLED: bool = True
    TRACKING_DOMAIN: str = os.getenv("TRACKING_DOMAIN", "https://track.example.com")
    TRACKING_SECRET: str = os.getenv("TRACKING_SECRET", secrets.token_urlsafe(32))
    TRACKING_PIXEL_ENABLED: bool = True
    
    # Multi-Armed Bandit Configuration
    MAB_EPSILON: float = 0.1
    MAB_DECAY_RATE: float = 0.995
    MAB_MIN_EPSILON: float = 0.01
    MAB_CONFIDENCE_LEVEL: float = 0.95
    MAB_MIN_SAMPLES: int = 10
    
    # Performance
    WORKER_CONNECTIONS: int = 1000
    WORKER_CLASS: str = "uvicorn.workers.UvicornWorker"
    GRACEFUL_TIMEOUT: int = 30
    KEEPALIVE: int = 5
    
    # Security Headers
    SECURITY_HEADERS: dict = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate and potentially modify database URL for production"""
        parsed = urlparse(v)
        if not parsed.scheme:
            raise ValueError("Invalid DATABASE_URL: missing scheme")
        
        # Force SSL for production PostgreSQL
        if parsed.scheme.startswith("postgresql") and "sslmode" not in v:
            return f"{v}?sslmode=require"
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """Ensure secret key is strong enough for production"""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if v == "change-me-in-production":
            raise ValueError("Please set a secure SECRET_KEY for production")
        return v
    
    @validator("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    def validate_api_keys(cls, v, field):
        """Validate API keys format"""
        if v and len(v) < 20:
            raise ValueError(f"{field.name} appears to be invalid")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_database_settings(self) -> dict:
        """Get SQLAlchemy database configuration"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_timeout": self.DATABASE_POOL_TIMEOUT,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "echo": self.DATABASE_ECHO,
            "pool_pre_ping": True,
            "connect_args": {
                "server_settings": {
                    "application_name": self.APP_NAME,
                    "jit": "off"
                },
                "command_timeout": 60,
                "options": "-c statement_timeout=60000"
            }
        }
    
    def get_redis_settings(self) -> dict:
        """Get Redis connection configuration"""
        parsed = urlparse(self.REDIS_URL)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 6379,
            "db": int(parsed.path.lstrip("/")) if parsed.path else 0,
            "password": parsed.password,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "decode_responses": self.REDIS_DECODE_RESPONSES,
            "socket_connect_timeout": self.REDIS_CONNECTION_TIMEOUT,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "retry_on_timeout": True,
            "health_check_interval": 30,
        }
    
    def get_logging_config(self) -> dict:
        """Get logging configuration dictionary"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                },
                "standard": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.LOG_LEVEL,
                    "formatter": "json" if self.LOG_FORMAT == "json" else "standard",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.LOG_LEVEL,
                    "formatter": "json",
                    "filename": self.LOG_FILE,
                    "maxBytes": self.LOG_MAX_BYTES,
                    "backupCount": self.LOG_BACKUP_COUNT
                }
            },
            "loggers": {
                "": {
                    "level": self.LOG_LEVEL,
                    "handlers": ["console", "file"]
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "sqlalchemy.engine": {
                    "level": "WARNING",
                    "handlers": ["console", "file"],
                    "propagate": False
                }
            }
        }


# Create singleton instance
settings = ProductionConfig()


def get_settings() -> ProductionConfig:
    """Get production configuration instance"""
    return settings