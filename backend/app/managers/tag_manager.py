"""
Tag Manager - Tag operations and statistics

Handles tag CRUD and document-tag associations.
"""
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from app.core.transactions import transactional
from app.core.exceptions import TagNotFoundException, InvalidTagException
from app.models.document import Tag, Document, DocumentTag
from app.schemas.requests import CreateTagRequest

logger = structlog.get_logger()


class TagManager:
    """Manager for tag operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tags(self) -> List[Dict]:
        """
        List all tags with document counts

        Returns:
            List of dicts with tag info and counts
        """
        result = await self.db.execute(
            select(
                Tag.id,
                Tag.name,
                Tag.created_at,
                func.count(DocumentTag.document_id).label("document_count")
            )
            .outerjoin(DocumentTag, Tag.id == DocumentTag.tag_id)
            .group_by(Tag.id, Tag.name, Tag.created_at)
            .order_by(Tag.name)
        )

        tags = []
        for row in result:
            tags.append({
                "id": row.id,
                "name": row.name,
                "created_at": row.created_at,
                "document_count": row.document_count or 0
            })

        return tags

    async def get_tag(self, tag_name: str) -> Tag:
        """Get tag by name"""
        result = await self.db.execute(
            select(Tag).where(Tag.name == tag_name.lower())
        )
        tag = result.scalar_one_or_none()

        if not tag:
            raise TagNotFoundException(tag_name)

        return tag

    @transactional
    async def create_tag(self, request: CreateTagRequest) -> Tag:
        """Create new tag"""
        # Check if exists
        result = await self.db.execute(
            select(Tag).where(Tag.name == request.name.lower())
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise InvalidTagException(
                request.name,
                "Tag already exists"
            )

        tag = Tag(name=request.name.lower())
        self.db.add(tag)
        await self.db.flush()

        logger.info("tag_created", tag_name=request.name)
        return tag

    @transactional
    async def delete_tag(self, tag_name: str) -> None:
        """Delete tag (removes from all documents)"""
        tag = await self.get_tag(tag_name)
        await self.db.delete(tag)
        logger.info("tag_deleted", tag_name=tag_name)

    async def get_documents_by_tag(self, tag_name: str) -> List[Document]:
        """Get all documents with specific tag"""
        tag = await self.get_tag(tag_name)

        result = await self.db.execute(
            select(Document)
            .join(Document.tags)
            .where(Tag.id == tag.id)
            .options(selectinload(Document.tags))
        )

        return list(result.scalars().all())
