"""
API v1 routes
"""
from fastapi import APIRouter
from app.api.v1 import documents, search

api_router = APIRouter()

# Document endpoints (3-layer architecture)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])

# Search endpoints
api_router.include_router(search.router, prefix="/search", tags=["search"])
