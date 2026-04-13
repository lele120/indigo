"""
Document schemas for API validation
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# Tag schemas
class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class TagResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# Document schemas
class DocumentCreate(BaseModel):
    """Schema for creating a document (used internally after file upload)"""
    name: str = Field(..., min_length=1, max_length=500)
    file_hash: str = Field(..., min_length=64, max_length=64)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=100)
    tags: Optional[List[str]] = Field(default=None, description="List of tag names")


class DocumentUpdate(BaseModel):
    """Schema for updating a document"""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    tags: Optional[List[str]] = None


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: UUID
    name: str
    file_hash: str
    file_size: int
    mime_type: str
    file_type: Optional[str]
    author: Optional[str]
    has_embeddings: bool = True
    page_count: Optional[int]
    chunk_count: int
    status: str
    error_message: Optional[str]
    uploaded_at: datetime
    updated_at: datetime
    tags: List[TagResponse]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for paginated document list"""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Upload task schemas
class UploadTaskResponse(BaseModel):
    """Schema for upload task status"""
    id: UUID
    document_id: UUID
    status: str
    progress: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# File upload schema
class FileUploadResponse(BaseModel):
    """Response after file upload"""
    document_id: UUID
    task_id: UUID
    message: str
