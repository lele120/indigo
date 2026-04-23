"""
Document Service - Async data access layer for documents

Pure data operations without business logic.
Used by DocumentManager for orchestration.
"""
from typing import List, Optional, Dict, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case
from sqlalchemy.orm import selectinload
import hashlib

from app.models.document import Document, Tag, Chunk
from app.schemas.document import DocumentCreate


class DocumentService:
    """Async service for document data access operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: UUID, load_tags: bool = True) -> Optional[Document]:
        """Get a document by ID"""
        query = select(Document).where(Document.id == document_id)

        if load_tags:
            query = query.options(selectinload(Document.tags))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_chunks_by_document(self, document_id: UUID) -> List[Chunk]:
        """Get all chunks for a document ordered by chunk_index."""
        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_by_hash(self, file_hash: str) -> Optional[Document]:
        """Get document by file hash"""
        result = await self.db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Tuple[List[Document], int]:
        """
        List documents with filters and pagination
        Returns (documents, total_count)
        """
        query = select(Document).options(selectinload(Document.tags))

        # Apply filters
        if status:
            query = query.where(Document.status == status)

        if file_type:
            query = query.where(Document.file_type == file_type)

        if author:
            query = query.where(Document.author.ilike(f"%{author}%"))

        if tag:
            query = query.join(Document.tags).where(Tag.name == tag.lower())

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination and ordering
        query = query.order_by(desc(Document.uploaded_at))
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        documents = result.scalars().all()

        return list(documents), total

    async def create(
        self,
        document: DocumentCreate,
        tags: Optional[List[Tag]] = None,
    ) -> Document:
        """Create a new document (no commit, managed by transaction).

        Tags must be passed as resolved ORM objects and are assigned before
        the document enters the session, so the collection is considered
        'loaded' and no async lazy IO is triggered by later access.
        """
        db_document = Document(
            name=document.name,
            file_hash=document.file_hash,
            file_size=document.file_size,
            mime_type=document.mime_type,
            status="pending",
        )
        if tags:
            db_document.tags = tags

        self.db.add(db_document)
        await self.db.flush()  # Get ID but don't commit

        return db_document

    async def update_status(
        self,
        document_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        """Update document status"""
        document = await self.get_by_id(document_id, load_tags=False)
        if not document:
            return None

        document.status = status
        if error_message:
            document.error_message = error_message

        await self.db.flush()
        return document

    async def update_metadata(
        self,
        document_id: UUID,
        name: Optional[str] = None,
    ) -> Optional[Document]:
        """Update document metadata"""
        document = await self.get_by_id(document_id, load_tags=False)
        if not document:
            return None

        if name is not None:
            document.name = name

        await self.db.flush()
        return document

    async def delete(self, document_id: UUID) -> bool:
        """Delete a document"""
        document = await self.get_by_id(document_id, load_tags=False)
        if not document:
            return False

        await self.db.delete(document)
        await self.db.flush()
        return True

    async def get_stats(self) -> Dict[str, any]:
        """
        Get document statistics
        Returns counts by status and list of all tag names
        """
        # Single query for all counts using CASE expressions
        result = await self.db.execute(
            select(
                func.count(Document.id).label('total'),
                func.sum(case((Document.status == 'pending', 1), else_=0)).label('pending'),
                func.sum(case((Document.status == 'processing', 1), else_=0)).label('processing'),
                func.sum(case((Document.status == 'completed', 1), else_=0)).label('completed'),
                func.sum(case((Document.status == 'failed', 1), else_=0)).label('failed'),
            )
        )
        stats = result.first()

        # Get all unique tag names
        tags_result = await self.db.execute(
            select(Tag.name).order_by(Tag.name)
        )
        tag_names = [tag[0] for tag in tags_result.all()]

        return {
            'total': stats.total or 0,
            'pending': stats.pending or 0,
            'processing': stats.processing or 0,
            'completed': stats.completed or 0,
            'failed': stats.failed or 0,
            'tags': tag_names,
        }

    @staticmethod
    def calculate_file_hash(file_content: bytes) -> str:
        """Calculate SHA256 hash of file content (stateless utility)"""
        return hashlib.sha256(file_content).hexdigest()
