"""
Document Manager - CRUD operations for documents

Coordinates document lifecycle management with transactions.
"""
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload
import structlog

from app.core.transactions import transactional
from app.core.exceptions import DocumentNotFoundException
from app.models.document import Document, Tag, UploadTask
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.schemas.requests import UpdateDocumentRequest, ListDocumentsRequest

logger = structlog.get_logger()


class DocumentManager:
    """Manager for document CRUD operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_document(self, document_id: UUID) -> Document:
        """Get document by ID with tags loaded"""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.tags))
            .where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise DocumentNotFoundException(str(document_id))

        return document

    async def list_documents(
        self,
        request: ListDocumentsRequest
    ) -> Tuple[List[Document], int]:
        """List documents with pagination and filters"""
        query = select(Document).options(selectinload(Document.tags))

        # Apply filters
        if request.file_type:
            query = query.where(Document.file_type == request.file_type)

        if request.author:
            query = query.where(Document.author.ilike(f"%{request.author}%"))

        if request.tag:
            query = query.join(Document.tags).where(Tag.name == request.tag.lower())

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (request.page - 1) * request.page_size
        query = query.order_by(desc(Document.uploaded_at))
        query = query.offset(offset).limit(request.page_size)

        result = await self.db.execute(query)
        documents = result.scalars().all()

        return list(documents), total

    @transactional
    async def update_document(
        self,
        document_id: UUID,
        request: UpdateDocumentRequest
    ) -> Document:
        """Update document metadata (name, tags)"""
        document = await self.get_document(document_id)

        if request.name:
            document.name = request.name

        if request.tags is not None:
            # Clear existing tags
            document.tags = []
            await self.db.flush()

            # Add new tags
            for tag_name in request.tags:
                tag = await self._get_or_create_tag(tag_name)
                document.tags.append(tag)

        await self.db.flush()
        logger.info("document_updated", document_id=str(document_id))

        return document

    @transactional
    async def delete_document(self, document_id: UUID) -> None:
        """Delete document (cascades to chunks and tasks)"""
        document = await self.get_document(document_id)
        await self.db.delete(document)
        logger.info("document_deleted", document_id=str(document_id))

    async def get_task_status(self, task_id: UUID) -> UploadTask:
        """Get upload task status"""
        result = await self.db.execute(
            select(UploadTask).where(UploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            from app.core.exceptions import TaskNotFoundException
            raise TaskNotFoundException(str(task_id))

        return task

    async def _get_or_create_tag(self, tag_name: str) -> Tag:
        """Get or create tag"""
        result = await self.db.execute(
            select(Tag).where(Tag.name == tag_name.lower())
        )
        tag = result.scalar_one_or_none()

        if tag:
            return tag

        tag = Tag(name=tag_name.lower())
        self.db.add(tag)
        await self.db.flush()
        return tag
