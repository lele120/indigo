"""
Search request and response schemas
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class SearchRequest(BaseModel):
    """Search request schema"""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    document_ids: Optional[List[str]] = Field(None, description="Filter by document IDs")
    file_type: Optional[str] = Field(None, description="Filter by file type (pdf, docx, excel, csv, text, powerpoint)")
    author: Optional[str] = Field(None, description="Filter by author name (partial match)")
    date_from: Optional[datetime] = Field(None, description="Filter documents uploaded after this date (ISO 8601 format)")
    date_to: Optional[datetime] = Field(None, description="Filter documents uploaded before this date (ISO 8601 format)")
    use_hybrid: bool = Field(True, description="Use hybrid search (vector + BM25)")
    vector_weight: float = Field(0.5, ge=0.0, le=1.0, description="Weight for vector search")
    bm25_weight: float = Field(0.5, ge=0.0, le=1.0, description="Weight for BM25 search")

    @field_validator('date_from', 'date_to')
    @classmethod
    def validate_dates(cls, v):
        """Validate date format"""
        if v is not None and not isinstance(v, datetime):
            raise ValueError("Date must be in ISO 8601 format (e.g., 2024-01-01T00:00:00)")
        return v

    @field_validator('date_to')
    @classmethod
    def validate_date_range(cls, v, info):
        """Validate that date_to is after date_from"""
        if v is not None and info.data.get('date_from') is not None:
            if v < info.data['date_from']:
                raise ValueError("date_to must be after date_from")
        return v

    @field_validator('author')
    @classmethod
    def validate_author(cls, v):
        """Trim and validate author name"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class SearchResult(BaseModel):
    """Individual search result"""
    chunk_id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Document UUID")
    document_name: Optional[str] = Field(None, description="Document filename")
    text: str = Field(..., description="Chunk text content")
    text_preview: str = Field(..., description="Short text preview")
    page_number: Optional[int] = Field(None, description="Page number in document")
    chunk_type: str = Field("text", description="Type of chunk")
    rrf_score: Optional[float] = Field(None, description="RRF combined score")
    cross_encoder_score: Optional[float] = Field(None, description="Cross-encoder reranking score")
    vector_score: Optional[float] = Field(None, description="Vector similarity score")
    bm25_score: Optional[float] = Field(None, description="BM25 relevance score")
    vector_rank: Optional[int] = Field(None, description="Rank in vector results")
    bm25_rank: Optional[int] = Field(None, description="Rank in BM25 results")


class SearchResponse(BaseModel):
    """Search response schema"""
    query: str = Field(..., description="Original search query")
    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    use_hybrid: bool = Field(..., description="Whether hybrid search was used")
    search_time_ms: Optional[float] = Field(None, description="Search execution time in milliseconds")
