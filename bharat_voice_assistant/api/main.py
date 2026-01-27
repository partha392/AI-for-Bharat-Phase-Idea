"""
Main FastAPI application for the Bharat Voice Assistant.

This module sets up the FastAPI application with all necessary middleware,
routes, and configuration for the voice assistant service.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from typing import Dict, Any

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger, LogPerformance
from bharat_voice_assistant.core.monitoring import monitor
from bharat_voice_assistant.core.exceptions import BharatVoiceAssistantError

logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Bharat Voice Assistant",
    description="Multilingual voice-first AI system for government services in India",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all HTTP requests with performance metrics."""
    start_time = time.time()
    
    # Generate request ID for correlation
    request_id = f"req_{int(time.time() * 1000)}"
    
    # Log request
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration_ms:.2f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        )
        
        # Record metrics
        monitor.metrics.record_timer(
            "http_request_duration",
            duration_ms,
            {"method": request.method, "path": request.url.path, "status": str(response.status_code)}
        )
        monitor.metrics.increment_counter(
            "http_requests_total",
            1,
            {"method": request.method, "path": request.url.path, "status": str(response.status_code)}
        )
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        logger.error(
            f"Request failed: {request.method} {request.url.path} - {str(e)} ({duration_ms:.2f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error": str(e),
                "duration_ms": duration_ms
            },
            exc_info=True
        )
        
        # Record error metrics
        monitor.metrics.increment_counter(
            "http_requests_total",
            1,
            {"method": request.method, "path": request.url.path, "status": "500"}
        )
        
        raise


@app.exception_handler(BharatVoiceAssistantError)
async def bharat_voice_assistant_exception_handler(request: Request, exc: BharatVoiceAssistantError):
    """Handle custom application exceptions."""
    logger.error(f"Application error: {exc.message}", extra=exc.context)
    
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "code": exc.error_code,
                "message": exc.message,
                "context": exc.context
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "An internal server error occurred"
            }
        }
    )


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting Bharat Voice Assistant API")
    
    # Start monitoring
    monitor.start_monitoring(interval_seconds=60)
    
    logger.info("Bharat Voice Assistant API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Bharat Voice Assistant API")
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    logger.info("Bharat Voice Assistant API shutdown complete")


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with basic information."""
    return {
        "name": "Bharat Voice Assistant",
        "version": "0.1.0",
        "description": "Multilingual voice-first AI system for government services in India",
        "status": "running",
        "environment": config.env
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    with LogPerformance("api", "health_check"):
        # Run health checks
        health_status = monitor.health.get_health_status()
        
        # Get basic metrics
        metrics = {
            "requests_total": monitor.metrics.get_counter("http_requests_total"),
            "avg_response_time": monitor.metrics.get_timer_stats("http_request_duration").get("avg", 0)
        }
        
        return {
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "timestamp": health_status["timestamp"],
            "version": "0.1.0",
            "environment": config.env,
            "health_checks": health_status["checks"],
            "metrics": metrics
        }


@app.get("/metrics")
async def metrics_endpoint() -> Dict[str, Any]:
    """Metrics endpoint for monitoring."""
    return {
        "counters": dict(monitor.metrics.counters),
        "gauges": dict(monitor.metrics.gauges),
        "timers": {
            name: monitor.metrics.get_timer_stats(name)
            for name in monitor.metrics.timers.keys()
        }
    }


# Include voice routes
from .voice_routes import router as voice_router
app.include_router(voice_router)

# Include grievance routes
from .grievance_routes import router as grievance_router
app.include_router(grievance_router)

# Placeholder endpoints for future implementation
@app.get("/schemes/search")
async def search_schemes():
    """Search government schemes (placeholder)."""
    return {"message": "Scheme search endpoint - to be implemented"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bharat_voice_assistant.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.is_development(),
        log_level="info"
    )