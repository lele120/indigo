from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.database_async import init_async_db, close_async_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events

    Handles:
    - Async database initialization
    - Resource cleanup on shutdown
    """
    # Startup
    logger.info("application_startup")
    await init_async_db()

    yield

    # Shutdown
    logger.info("application_shutdown")
    await close_async_db()


# Create FastAPI app
app = FastAPI(
    title="Indigo Document Intelligence Server",
    description="RAG system with MCP server for semantic document search",
    version="1.0.0",
    lifespan=lifespan
)

# Register exception handlers
register_exception_handlers(app)

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
