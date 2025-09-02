import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from src.config.database import create_tables
from src.config.cache import cache_manager
from src.api.routes import router
from src.monitoring.metrics import init_metrics, get_metrics_handler, MetricsCollector
from src.monitoring.logging import setup_logging, get_logger, log_request, log_response, log_error

# Initialize logging
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "/app/logs/app.log") if os.getenv("APP_ENV") == "production" else None,
    log_format="json" if os.getenv("APP_ENV") == "production" else "text"
)

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    logger.info("Starting Email Subject Line Optimizer", version="1.0.0", environment=os.getenv("APP_ENV", "development"))
    
    # Initialize metrics
    init_metrics(app_version="1.0.0")
    
    # Initialize cache
    await cache_manager.initialize()
    logger.info("Cache manager initialized")
    
    # Create database tables
    await create_tables()
    logger.info("Database tables created/verified")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Email Subject Line Optimizer")

app = FastAPI(
    title="AI Email Subject Line Optimizer",
    description="Generate and A/B test email subject line variations using AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("APP_ENV") != "production" else "/api/docs",
    redoc_url="/redoc" if os.getenv("APP_ENV") != "production" else None,
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request tracking middleware
@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track request metrics and logging"""
    start_time = time.time()
    
    # Generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", f"req_{int(time.time() * 1000)}")
    
    # Log request
    log_request(
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
        headers=dict(request.headers),
        correlation_id=correlation_id
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Track metrics
        if hasattr(MetricsCollector, 'track_request'):
            MetricsCollector.track_request(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
                duration=duration_ms / 1000,
                request_size=int(request.headers.get("content-length", 0)),
                response_size=int(response.headers.get("content-length", 0))
            )
        
        # Log response
        log_response(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id
        )
        
        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log error
        log_error(
            error=e,
            context={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms
            },
            correlation_id=correlation_id
        )
        
        # Track error metric
        if hasattr(MetricsCollector, 'track_error'):
            MetricsCollector.track_error(
                error_type=type(e).__name__,
                component="middleware"
            )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "correlation_id": correlation_id
            }
        )

# Health check endpoint
@app.get("/health", tags=["monitoring"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": os.getenv("APP_ENV", "development"),
        "services": {}
    }
    
    # Check database
    try:
        from src.config.database import get_session
        async with get_session() as session:
            await session.execute("SELECT 1")
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check cache
    try:
        test_key = "health_check_test"
        await cache_manager.set(test_key, "test", ttl=1)
        await cache_manager.get(test_key)
        health_status["services"]["cache"] = "healthy"
    except Exception as e:
        health_status["services"]["cache"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check AI provider
    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        health_status["services"]["ai_provider"] = "configured"
    else:
        health_status["services"]["ai_provider"] = "not configured"
        health_status["status"] = "degraded"
    
    return health_status

# Metrics endpoint
app.add_api_route("/metrics", get_metrics_handler(), methods=["GET"], tags=["monitoring"], response_class=PlainTextResponse)

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)