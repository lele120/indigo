"""
Tag Manager - Business logic orchestration for tags

Coordinates tag operations, document-tag associations.
Uses TagService for data access.
"""
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.transactions import transactional
from app.core.exceptions import TagNotFoundException, InvalidTagException
from app.models.document import Tag, Document
from app.schemas.requests import CreateTagRequest
from app.services.tag_service import TagService

logger = structlog.get_logger()


class TagManager:
    """Manager for tag business logic orchestration"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tag_service = TagService(db)

    async def list_tags(self) -> List[Dict]:
        """
        List all tags with document counts

        Returns list of dicts with tag info and counts
        """
        return await self.tag_service.list_all()

    async def get_tag(self, tag_name: str) -> Tag:
        """Get tag by name"""
        tag = await self.tag_service.get_by_name(tag_name)

        if not tag:
            raise TagNotFoundException(tag_name)

        return tag

    @transactional
    async def create_tag(self, request: CreateTagRequest) -> Tag:
        """
        Create new tag

        Business logic:
        - Check if tag already exists
        - Create via service if not
        """
        existing = await self.tag_service.get_by_name(request.name)

        if existing:
            raise InvalidTagException(
                request.name,
                "Tag already exists"
            )

        tag = await self.tag_service.create(request.name)
        logger.info("tag_created", tag_name=request.name)
        return tag

    @transactional
    async def delete_tag(self, tag_name: str) -> None:
        """
        Delete tag (removes from all documents)

        Business logic:
        - Validate tag exists
        - Delete via service (cascade handled by DB)
        """
        tag = await self.get_tag(tag_name)
        await self.tag_service.delete(tag.id)
        logger.info("tag_deleted", tag_name=tag_name)

    async def get_documents_by_tag(self, tag_name: str) -> List[Document]:
        """
        Get all documents with specific tag

        Business logic:
        - Validate tag exists
        - Fetch documents via service
        """
        tag = await self.get_tag(tag_name)
        return await self.tag_service.get_documents_by_tag(tag.name)
