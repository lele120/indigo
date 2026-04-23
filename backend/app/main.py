from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware
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

    # Warm cross-encoder into the process cache so the first search
    # query doesn't pay the ~15s model-load penalty.
    from app.core.config import settings
    if settings.ENABLE_RERANKING:
        import asyncio as _asyncio
        from app.services.reranking_service import RerankingService

        def _warm():
            try:
                RerankingService()._load_model()
            except Exception as e:
                logger.warning("reranker_warmup_failed", error=str(e))

        # Fire and forget: don't block startup on it, but get it cached
        # before real traffic arrives. Readiness probe already waits for
        # the HTTP layer, so the model finishes loading in the background.
        _asyncio.get_event_loop().run_in_executor(None, _warm)

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


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Bearer-token gate on /api/v1/*.

    Health probes, docs, metrics and the root ping stay open so they can be
    checked by Docker / browsers without credentials. Everything under
    /api/v1 requires `Authorization: Bearer <MCP_API_KEY>`.
    """

    PROTECTED_PREFIX = "/api/v1"

    async def dispatch(self, request: Request, call_next):
        if (
            settings.MCP_API_KEY
            and request.url.path.startswith(self.PROTECTED_PREFIX)
            and request.method != "OPTIONS"  # let CORS preflight through
        ):
            auth = request.headers.get("authorization", "")
            token = auth.replace("Bearer ", "").strip()
            if token != settings.MCP_API_KEY:
                return JSONResponse(
                    {"error": "unauthorized", "message": "Missing or invalid Bearer token"},
                    status_code=401,
                )
        return await call_next(request)


app.add_middleware(BearerAuthMiddleware)

# CORS middleware — registered after auth so preflight always returns headers.
# Order of add_middleware is reverse of execution: CORS runs first, auth second.
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
