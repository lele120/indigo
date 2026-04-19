"""
Document Manager - Business logic orchestration for documents

Coordinates CRUD operations, transactions, and business rules.
Uses DocumentService and TagService for data access.
"""
from typing import List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.transactions import transactional
from app.core.exceptions import DocumentNotFoundException, TaskNotFoundException
from app.models.document import Document, UploadTask
from app.schemas.requests import UpdateDocumentRequest, ListDocumentsRequest
from app.services.document_service import DocumentService
from app.services.tag_service import TagService
from app.services.upload_task_service import UploadTaskService

logger = structlog.get_logger()


class DocumentManager:
    """Manager for document business logic orchestration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.document_service = DocumentService(db)
        self.tag_service = TagService(db)
        self.upload_task_service = UploadTaskService(db)

    async def get_document(self, document_id: UUID) -> Document:
        """Get document by ID with tags loaded"""
        document = await self.document_service.get_by_id(document_id, load_tags=True)

        if not document:
            raise DocumentNotFoundException(str(document_id))

        return document

    async def list_documents(
        self,
        request: ListDocumentsRequest
    ) -> Tuple[List[Document], int]:
        """List documents with pagination and filters"""
        offset = (request.page - 1) * request.page_size

        documents, total = await self.document_service.list_documents(
            skip=offset,
            limit=request.page_size,
            file_type=request.file_type,
            author=request.author,
            tag=request.tag,
        )

        return documents, total

    @transactional
    async def update_document(
        self,
        document_id: UUID,
        request: UpdateDocumentRequest
    ) -> Document:
        """
        Update document metadata (name, tags)

        Business logic:
        - Update name if provided
        - Replace all tags if provided
        - Validate document exists
        """
        document = await self.get_document(document_id)

        # Update name via service
        if request.name:
            await self.document_service.update_metadata(
                document_id,
                name=request.name
            )

        # Update tags via tag service
        if request.tags is not None:
            # Clear existing tags
            document.tags = []
            await self.db.flush()

            # Add new tags (get_or_create ensures no duplicates)
            for tag_name in request.tags:
                tag = await self.tag_service.get_or_create(tag_name)
                document.tags.append(tag)

        await self.db.flush()
        logger.info("document_updated", document_id=str(document_id))

        return document

    @transactional
    async def delete_document(self, document_id: UUID) -> None:
        """
        Delete document (cascades to chunks and tasks)

        Business logic:
        - Validate document exists
        - Delete via service (cascade handled by DB)
        """
        document = await self.get_document(document_id)
        await self.document_service.delete(document_id)
        logger.info("document_deleted", document_id=str(document_id))

    async def get_task_status(self, task_id: UUID) -> UploadTask:
        """Get upload task status"""
        task = await self.upload_task_service.get_by_id(task_id)

        if not task:
            raise TaskNotFoundException(str(task_id))

        return task
