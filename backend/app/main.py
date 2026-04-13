from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

from app.core.config import settings
from app.api.v1 import api_router

# Configure structured logging
if settings.STRUCTLOG_ENABLED:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ]
    )

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Indigo Document Intelligence Server",
    description="RAG system with MCP server for semantic document search",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker healthcheck"""
    return {
        "status": "healthy",
        "service": "backend",
        "version": "1.0.0"
    }

# Metrics endpoint for Prometheus
if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Indigo Document Intelligence Server",
        "version": "1.0.0",
        "docs": "/docs"
    }

logger.info("backend_started", version="1.0.0")
