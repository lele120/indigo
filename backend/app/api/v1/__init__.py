"""
API v1 routes
"""
from fastapi import APIRouter
from app.api.v1 import documents, documents_v2, search

api_router = APIRouter()

# Original endpoints (legacy, keep for backward compatibility)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])

# New architecture pattern endpoints (example)
# Mount at /documents-v2 to show new pattern without breaking existing API
api_router.include_router(
    documents_v2.router,
    prefix="/documents-v2",
    tags=["documents-v2 (new architecture)"]
)
