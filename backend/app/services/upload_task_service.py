"""
Upload Task Service - Async data access layer for upload tasks

Pure data operations without business logic.
Used by UploadManager for orchestration.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import UploadTask


class UploadTaskService:
    """Async service for upload task data access operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_id: UUID) -> Optional[UploadTask]:
        """Get upload task by ID"""
        result = await self.db.execute(
            select(UploadTask).where(UploadTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create(self, document_id: UUID) -> UploadTask:
        """Create an upload task for a document"""
        task = UploadTask(
            document_id=document_id,
            status="queued",
            progress=0,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def update_progress(
        self,
        task_id: UUID,
        progress: int,
        status: Optional[str] = None
    ) -> Optional[UploadTask]:
        """Update task progress"""
        task = await self.get_by_id(task_id)
        if not task:
            return None

        task.progress = progress
        if status:
            task.status = status

        if status == "completed":
            task.completed_at = datetime.now(timezone.utc)
        elif status == "processing" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)

        await self.db.flush()
        return task

    async def mark_failed(
        self,
        task_id: UUID,
        error_message: str
    ) -> Optional[UploadTask]:
        """Mark task as failed with error message"""
        task = await self.get_by_id(task_id)
        if not task:
            return None

        task.status = "failed"
        task.error_message = error_message
        task.completed_at = datetime.now(timezone.utc)

        await self.db.flush()
        return task
