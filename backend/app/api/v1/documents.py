"""
Document API endpoints
"""
import os
import tempfile
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.services.document_service import DocumentService
from app.services.document_processor import DocumentProcessor
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    TagResponse,
    UploadTaskResponse,
    FileUploadResponse,
    DocumentCreate,
)
from app.tasks.document_tasks import process_document

logger = structlog.get_logger()

router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    chunk_size: Optional[int] = Query(None, ge=100, le=2000, description="Custom chunk size in tokens (default: 1000)"),
    chunk_overlap: Optional[int] = Query(None, ge=0, le=500, description="Custom chunk overlap in tokens (default: 200)"),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing

    Supported formats:
    - **PDF**: .pdf
    - **Word**: .docx, .doc
    - **Excel**: .xlsx, .xls
    - **CSV**: .csv
    - **Text**: .txt, .md, .markdown, .rst
    - **PowerPoint**: .pptx, .ppt

    Args:
    - **file**: Document file to upload (required)
    - **tags**: Optional comma-separated tags (e.g., "finance,report,2024")
    - **chunk_size**: Optional custom chunk size in tokens (100-2000, default: 1000)
        - Controls how text is split into searchable chunks
        - Larger chunks preserve more context but may be less precise
        - Smaller chunks are more precise but may lose context
    - **chunk_overlap**: Optional chunk overlap in tokens (0-500, default: 200)
        - How many tokens overlap between consecutive chunks
        - Higher overlap improves context continuity
        - Must be less than chunk_size

    Returns:
    - document_id: UUID of created document
    - task_id: UUID of processing task (use to check status)
    - message: Success message

    Processing:
    1. Document text is extracted (supports all formats above)
    2. Metadata (author, title) extracted if available
    3. Text is chunked with specified parameters
    4. Embeddings generated (or falls back to BM25-only if OpenAI fails)
    5. Stored in vector DB for hybrid search

    Example:
    ```bash
    curl -X POST "http://localhost:8000/api/v1/documents/upload?chunk_size=800&chunk_overlap=150" \\
      -F "file=@document.pdf" \\
      -F "tags=legal,contract,2024"
    ```
    """
    logger.info("document_upload_started", filename=file.filename)

    # Validate chunk parameters
    if chunk_size is not None and chunk_overlap is not None:
        if chunk_overlap >= chunk_size:
            raise HTTPException(
                status_code=400,
                detail=f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
            )

    if chunk_size is not None and chunk_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="chunk_size must be greater than 0"
        )

    if chunk_overlap is not None and chunk_overlap < 0:
        raise HTTPException(
            status_code=400,
            detail="chunk_overlap must be non-negative"
        )

    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    all_supported_extensions = [ext for exts in DocumentProcessor.SUPPORTED_FORMATS.values() for ext in exts]

    if file_ext not in all_supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}. Supported formats: {', '.join(all_supported_extensions)}"
        )

    try:
        # Read file content
        content = await file.read()

        # Calculate hash
        file_hash = DocumentService.calculate_file_hash(content)

        # Check for duplicates
        existing = DocumentService.check_duplicate(db, file_hash)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Document already exists with ID: {existing.id}",
            )

        # Parse tags
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        # Create document record
        document_data = DocumentCreate(
            name=file.filename,
            file_hash=file_hash,
            file_size=len(content),
            mime_type=file.content_type or "application/pdf",
            tags=tag_list,
        )

        document = DocumentService.create_document(db, document_data)

        # Create upload task
        task = DocumentService.create_upload_task(db, document.id)

        # Save file temporarily in shared volume
        temp_dir = "/tmp/uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{document.id}{file_ext}")
        with open(file_path, "wb") as f:
            f.write(content)

        # Queue processing task
        process_document.delay(
            str(document.id),
            str(task.id),
            file_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        logger.info(
            "document_upload_completed",
            document_id=str(document.id),
            task_id=str(task.id),
            filename=file.filename,
        )

        return FileUploadResponse(
            document_id=document.id,
            task_id=task.id,
            message="Document uploaded successfully and queued for processing",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("document_upload_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    search: Optional[str] = Query(None, description="Search in document names"),
    db: Session = Depends(get_db),
):
    """
    List documents with pagination and filters

    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    - **status**: Filter by status (pending, processing, completed, failed)
    - **tags**: Filter by tags (comma-separated)
    - **search**: Search term for document names
    """
    skip = (page - 1) * page_size

    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Get documents
    documents, total = DocumentService.get_documents(
        db,
        skip=skip,
        limit=page_size,
        status=status,
        tags=tag_list,
        search=search,
    )

    # Calculate total pages
    pages = (total + page_size - 1) // page_size

    return DocumentListResponse(
        items=documents,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific document by ID

    - **document_id**: UUID of the document
    """
    document = DocumentService.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: UUID,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a document (name and/or tags)

    - **document_id**: UUID of the document
    - **name**: New document name (optional)
    - **tags**: New tags list (optional)
    """
    document = DocumentService.update_document(db, document_id, document_update)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a document

    - **document_id**: UUID of the document

    This will also delete:
    - All chunks associated with this document
    - Upload tasks
    - Vector embeddings from Qdrant
    """
    success = DocumentService.delete_document(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant
    try:
        from app.services.qdrant_service import QdrantService
        qdrant_service = QdrantService()
        qdrant_service.delete_by_document(document_id)
        logger.info("qdrant_vectors_deleted", document_id=str(document_id))
    except Exception as e:
        logger.warning("qdrant_deletion_failed", document_id=str(document_id), error=str(e))

    logger.info("document_deleted", document_id=str(document_id))
    return None


@router.get("/tasks/{task_id}", response_model=UploadTaskResponse)
def get_task_status(
    task_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get upload task status

    - **task_id**: UUID of the upload task

    Returns current status and progress (0-100)
    """
    task = DocumentService.get_upload_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.get("/tags/all", response_model=List[TagResponse])
def list_tags(db: Session = Depends(get_db)):
    """
    Get all available tags

    Returns list of all tags in the system
    """
    tags = DocumentService.get_all_tags(db)
    return tags
