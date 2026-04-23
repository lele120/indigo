"""
Tag Service - Async data access layer for tags

Pure data operations without business logic.
Used by TagManager for orchestration.
"""
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.document import Tag, Document, DocumentTag


class TagService:
    """Async service for tag data access operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_name(self, tag_name: str) -> Optional[Tag]:
        """Get tag by name"""
        result = await self.db.execute(
            select(Tag).where(Tag.name == tag_name.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, tag_id: int) -> Optional[Tag]:
        """Get tag by ID"""
        result = await self.db.execute(
            select(Tag).where(Tag.id == tag_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[Dict]:
        """
        List all tags with document counts
        Returns list of dicts with tag info and counts
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

    async def create(self, tag_name: str) -> Tag:
        """Create new tag (no commit, managed by transaction)"""
        tag = Tag(name=tag_name.lower())
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def get_or_create(self, tag_name: str) -> Tag:
        """Get existing tag or create new one"""
        tag = await self.get_by_name(tag_name)

        if tag:
            return tag

        return await self.create(tag_name)

    async def delete(self, tag_id: int) -> bool:
        """Delete tag"""
        tag = await self.get_by_id(tag_id)
        if not tag:
            return False

        await self.db.delete(tag)
        await self.db.flush()
        return True

    async def get_documents_by_tag(self, tag_name: str) -> List[Document]:
        """Get all documents with specific tag"""
        result = await self.db.execute(
            select(Document)
            .join(Document.tags)
            .where(Tag.name == tag_name.lower())
            .options(selectinload(Document.tags))
        )
        return list(result.scalars().all())

    async def delete_orphans(self) -> int:
        """Delete tags that are no longer attached to any document.

        Kept as a bulk SQL operation (no per-tag round trip) so it's cheap
        to invoke as a post-delete cleanup hook.
        Returns the number of orphan tags removed.
        """
        orphan_ids_result = await self.db.execute(
            select(Tag.id).outerjoin(DocumentTag, Tag.id == DocumentTag.tag_id)
            .group_by(Tag.id)
            .having(func.count(DocumentTag.document_id) == 0)
        )
        orphan_ids = [row[0] for row in orphan_ids_result.all()]
        if not orphan_ids:
            return 0

        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(Tag).where(Tag.id.in_(orphan_ids))
        )
        await self.db.flush()
        return len(orphan_ids)
