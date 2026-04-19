"""
Document API endpoints - Clean 3-layer architecture

Architecture:
- Controllers: HTTP handling, Pydantic validation
- Managers: Business logic orchestration, @transactional
- Services: Pure data access, async operations

Features:
- Pydantic request validation (automatic)
- Manager pattern (business logic separation)
- Async/await throughout
- Centralized exception handling
- Transaction management (@transactional)
"""
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_async import get_async_db
from app.managers import DocumentManager, UploadManager, TagManager
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    FileUploadResponse,
    TagResponse,
    UploadTaskResponse,
)
from app.schemas.requests import (
    UploadDocumentRequest,
    UpdateDocumentRequest,
    ListDocumentsRequest,
)

router = APIRouter()


# Dependency to get managers
def get_upload_manager(db: AsyncSession = Depends(get_async_db)) -> UploadManager:
    return UploadManager(db)


def get_document_manager(db: AsyncSession = Depends(get_async_db)) -> DocumentManager:
    return DocumentManager(db)


def get_tag_manager(db: AsyncSession = Depends(get_async_db)) -> TagManager:
    return TagManager(db)


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    request: UploadDocumentRequest = Depends(),
    manager: UploadManager = Depends(get_upload_manager),
):
    """
    Upload document with automatic validation

    **New Features**:
    - Automatic request validation via Pydantic
    - Transaction management via @transactional decorator
    - Centralized exception handling
    - Full async/await stack

    **Request Parameters** (auto-validated):
    - file: Document file (required)
    - tags: List of tags (optional, validated)
    - chunk_size: 100-2000 (default: 1000, validated)
    - chunk_overlap: 0-500 (default: 200, validated, must be < chunk_size)

    **Raises** (handled automatically):
    - InvalidFileException: Invalid file type/size
    - DuplicateDocumentException: File already exists
    - FileTooLargeException: File exceeds limit

    **Returns**:
    - document_id: UUID of created document
    - task_id: UUID for status polling
    - message: Success message
    """
    return await manager.upload_document(file, request)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    request: ListDocumentsRequest = Depends(),
    manager: DocumentManager = Depends(get_document_manager),
):
    """
    List documents with pagination and filters

    **Auto-validated parameters**:
    - page: Page number (default: 1, must be >= 1)
    - page_size: Items per page (default: 20, range: 1-100)
    - file_type: Filter by type (optional)
    - author: Filter by author (optional)
    - tag: Filter by tag (optional)

    **Benefits of new pattern**:
    - No manual validation needed
    - Business logic in manager (testable)
    - Full async for better performance
    """
    documents, total = await manager.list_documents(request)

    # Convert to response schema
    document_responses = [
        DocumentResponse.model_validate(doc) for doc in documents
    ]

    pages = (total + request.page_size - 1) // request.page_size

    return DocumentListResponse(
        items=document_responses,
        total=total,
        page=request.page,
        page_size=request.page_size,
        pages=pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    manager: DocumentManager = Depends(get_document_manager),
):
    """
    Get document by ID

    **Automatic error handling**:
    - DocumentNotFoundException -> 404 response (automatic)
    - DatabaseException -> 500 response (automatic)

    No manual HTTPException raising needed!
    """
    document = await manager.get_document(document_id)
    return DocumentResponse.model_validate(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    request: UpdateDocumentRequest,
    manager: DocumentManager = Depends(get_document_manager),
):
    """
    Update document metadata

    **Validated fields**:
    - name: 1-500 chars (optional, auto-trimmed)
    - tags: List of strings (optional, deduplicated)

    **Transaction safety**:
    - All updates in single transaction via @transactional
    - Auto-rollback on error
    """
    document = await manager.update_document(document_id, request)
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    manager: DocumentManager = Depends(get_document_manager),
):
    """
    Delete document (cascades to chunks and tasks)

    **Transaction safety**:
    - Atomic delete via @transactional
    - Cascades handled by database relationships

    **Error handling**:
    - DocumentNotFoundException -> 404 (automatic)
    """
    await manager.delete_document(document_id)


@router.get("/tasks/{task_id}/status", response_model=UploadTaskResponse)
async def get_task_status(
    task_id: UUID,
    manager: DocumentManager = Depends(get_document_manager),
):
    """
    Get upload task status for progress tracking

    **Polling endpoint** for frontend to track upload progress (0-100%).

    **Error handling**:
    - TaskNotFoundException -> 404 (automatic)
    """
    task = await manager.get_task_status(task_id)
    return UploadTaskResponse.model_validate(task)


@router.get("/tags/all", response_model=list[TagResponse], response_model_exclude_none=False)
async def list_all_tags(
    manager: TagManager = Depends(get_tag_manager),
):
    """
    List all tags with document counts

    **Async query** with JOIN for counts (efficient).
    """
    tags_data = await manager.list_tags()

    return [
        TagResponse(
            id=tag["id"],
            name=tag["name"],
            created_at=tag["created_at"],
            document_count=tag["document_count"]
        )
        for tag in tags_data
    ]
