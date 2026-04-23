"""
Pydantic request schemas for automatic validation

These schemas replace manual validation in controllers and provide:
- Automatic type checking
- Field validation
- Default values
- Clear error messages
"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


class UploadDocumentRequest(BaseModel):
    """
    Request schema for document upload

    Validates file upload parameters with business rules.
    """
    tags: Optional[List[str]] = Field(
        default=None,
        description="Document tags for categorization",
        examples=[["compliance", "legal", "2024"]]
    )
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=2000,
        description="Chunk size in tokens (100-2000)"
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Chunk overlap in tokens (0-500)"
    )

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and clean tag list"""
        if v is None:
            return None

        # Remove empty strings and whitespace
        cleaned_tags = [tag.strip() for tag in v if tag.strip()]

        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in cleaned_tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)

        return unique_tags if unique_tags else None

    @model_validator(mode='after')
    def validate_chunk_overlap(self):
        """Ensure chunk_overlap < chunk_size"""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        return self


class UpdateDocumentRequest(BaseModel):
    """
    Request schema for document metadata updates

    Allows updating name and tags only (immutable content).
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="New document name",
        examples=["Financial Report Q4 2024.pdf"]
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New tags (replaces existing)",
        examples=[["finance", "report", "q4"]]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Trim and validate document name"""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty or whitespace")
        return v

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and clean tag list"""
        if v is None:
            return None

        cleaned_tags = [tag.strip() for tag in v if tag.strip()]

        # Remove duplicates
        seen = set()
        unique_tags = []
        for tag in cleaned_tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)

        return unique_tags if unique_tags else None


class SearchDocumentsRequest(BaseModel):
    """
    Request schema for document search

    Validates search parameters for hybrid search.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["machine learning algorithms"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results"
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific document IDs",
        examples=[["uuid-1", "uuid-2"]]
    )
    file_type: Optional[str] = Field(
        default=None,
        description="Filter by file type",
        examples=["pdf", "docx", "txt"]
    )
    author: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Filter by author name (partial match)",
        examples=["John Smith"]
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Filter documents uploaded after this date"
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Filter documents uploaded before this date"
    )
    use_hybrid: bool = Field(
        default=True,
        description="Use hybrid search (vector + BM25)"
    )
    vector_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for vector search (0.0-1.0)"
    )
    bm25_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 search (0.0-1.0)"
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Trim and validate search query"""
        v = v.strip()
        if not v:
            raise ValueError("query cannot be empty or whitespace")
        return v

    @field_validator('author')
    @classmethod
    def validate_author(cls, v: Optional[str]) -> Optional[str]:
        """Trim and validate author name"""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return v

    @model_validator(mode='after')
    def validate_date_range(self):
        """Ensure date_to is after date_from"""
        if self.date_to and self.date_from:
            if self.date_to < self.date_from:
                raise ValueError("date_to must be after date_from")
        return self


class ListDocumentsRequest(BaseModel):
    """
    Request schema for listing documents with pagination

    Provides pagination and filtering options.
    """
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Number of items per page (max 1000; MCP resolver tools "
                    "pass 1000 to resolve tag→docs and name→UUID in a single "
                    "round-trip)"
    )
    file_type: Optional[str] = Field(
        default=None,
        description="Filter by file type",
        examples=["pdf", "docx"]
    )
    author: Optional[str] = Field(
        default=None,
        description="Filter by author (partial match)"
    )
    tag: Optional[str] = Field(
        default=None,
        description="Filter by tag name"
    )

    @field_validator('author')
    @classmethod
    def validate_author(cls, v: Optional[str]) -> Optional[str]:
        """Trim author name"""
        if v is None:
            return None
        v = v.strip()
        return v if v else None

    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v: Optional[str]) -> Optional[str]:
        """Lowercase file type"""
        if v is None:
            return None
        return v.lower().strip()


class DeleteDocumentRequest(BaseModel):
    """
    Request schema for document deletion confirmation

    Optional: Can add confirmation flag if needed.
    """
    confirm: bool = Field(
        default=False,
        description="Confirm deletion (prevents accidental deletes)"
    )


class CreateTagRequest(BaseModel):
    """
    Request schema for creating new tags
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Tag name",
        examples=["compliance", "finance"]
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Trim and lowercase tag name"""
        v = v.strip().lower()
        if not v:
            raise ValueError("tag name cannot be empty")
        # Allow only alphanumeric, dash, underscore
        if not all(c.isalnum() or c in ['-', '_'] for c in v):
            raise ValueError("tag name can only contain letters, numbers, dash, and underscore")
        return v
