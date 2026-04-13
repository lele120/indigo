"""
API v1 routes
"""
from fastapi import APIRouter
from app.api.v1 import documents, search

api_router = APIRouter()

api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
