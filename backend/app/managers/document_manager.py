"""
Document Manager - Business logic orchestration for documents

Coordinates CRUD operations, transactions, and business rules.
Uses DocumentService and TagService for data access.
"""
from typing import List, Literal, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.transactions import transactional
from app.core.exceptions import DocumentNotFoundException, TaskNotFoundException
from app.models.document import Document, UploadTask
from app.schemas.requests import UpdateDocumentRequest, ListDocumentsRequest
from app.services.document_service import DocumentService
from app.services.pdf_service import PDFService
from app.services.qdrant_service import QdrantService
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

        # Mutate the already-loaded instance directly — going through the
        # service would fetch a second ORM instance and leave `document`
        # with stale attributes, causing MissingGreenlet errors when
        # Pydantic later tries to lazy-load `updated_at` post-commit.
        if request.name:
            document.name = request.name

        if request.tags is not None:
            document.tags = []
            await self.db.flush()

            for tag_name in request.tags:
                tag = await self.tag_service.get_or_create(tag_name)
                document.tags.append(tag)

        await self.db.flush()
        # Refresh so `updated_at` (and any DB-side defaults) are materialised
        # before the @transactional commit expires the session attributes.
        await self.db.refresh(document, ["updated_at"])
        logger.info("document_updated", document_id=str(document_id))

        return document

    async def delete_document(self, document_id: UUID) -> None:
        """Delete document from Postgres, then cascade-clean Qdrant.

        Postgres cascade handles chunks/tasks rows. Qdrant has no FK, so
        we must delete its points by document_id ourselves. The Qdrant
        cleanup runs AFTER the PG transaction commits — if it fails we
        log and move on (leaves orphan vector points, better than
        rolling back a user-visible delete).
        """
        await self._delete_from_db(document_id)

        import asyncio
        try:
            qdrant = QdrantService()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, qdrant.delete_by_document, document_id)
        except Exception as e:
            logger.warning(
                "qdrant_cascade_delete_failed",
                document_id=str(document_id),
                error=str(e),
            )

    @transactional
    async def _delete_from_db(self, document_id: UUID) -> None:
        """Transactional Postgres delete (chunks/tasks cascade via FK).

        Also prunes tags that are no longer attached to any document — left
        alone they accumulate in list_tags across upload/delete cycles.
        """
        await self.get_document(document_id)
        await self.document_service.delete(document_id)
        orphan_count = await self.tag_service.delete_orphans()
        logger.info(
            "document_deleted",
            document_id=str(document_id),
            orphan_tags_pruned=orphan_count,
        )

    async def get_document_content(
        self,
        document_id: UUID,
        format: Literal["text", "markdown", "json"] = "markdown",
    ) -> dict:
        """Reconstruct document content from its chunks.

        - markdown: chunks joined with blank lines, markdown preserved
        - text:     same join, then markdown syntax stripped
        - json:     structured list of chunks with metadata
        """
        document = await self.get_document(document_id)
        chunks = await self.document_service.get_chunks_by_document(document_id)

        if format == "json":
            content = [
                {
                    "chunk_index": c.chunk_index,
                    "chunk_type": c.chunk_type,
                    "page_number": c.page_number,
                    "section_heading": c.section_heading,
                    "text": c.text or "",
                }
                for c in chunks
            ]
        else:
            joined = "\n\n".join(c.text for c in chunks if c.text)
            content = PDFService.strip_markdown_syntax(joined) if format == "text" else joined

        return {
            "id": document.id,
            "name": document.name,
            "format": format,
            "chunk_count": len(chunks),
            "content": content,
        }

    async def get_task_status(self, task_id: UUID) -> UploadTask:
        """Get upload task status"""
        task = await self.upload_task_service.get_by_id(task_id)

        if not task:
            raise TaskNotFoundException(str(task_id))

        return task

    async def get_stats(self) -> dict:
        """Get document statistics (counts by status + tag list)"""
        return await self.document_service.get_stats()
