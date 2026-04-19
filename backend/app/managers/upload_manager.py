"""
Upload Manager - Orchestrates document upload workflow

Responsibilities:
- File validation (type, size, format)
- Duplicate detection
- Document creation with transaction
- Task queuing for async processing
"""
import os
import tempfile
import hashlib
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.transactions import transactional
from app.core.exceptions import (
    InvalidFileException,
    FileTooLargeException,
    UnsupportedFileTypeException,
    DuplicateDocumentException,
)
from app.models.document import Document, Tag, UploadTask
from app.schemas.document import FileUploadResponse
from app.schemas.requests import UploadDocumentRequest
from app.core.config import settings
from app.tasks.document_tasks import process_document

logger = structlog.get_logger()


class UploadManager:
    """Manager for document upload operations"""

    ALLOWED_EXTENSIONS = {
        ".pdf", ".txt", ".md", ".markdown",
        ".docx", ".doc", ".xlsx", ".xls",
        ".pptx", ".ppt", ".csv", ".rst"
    }

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/csv",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _validate_file(self, file: UploadFile) -> None:
        """
        Validate file before processing

        Checks:
        - File extension
        - MIME type
        - File size

        Raises:
            InvalidFileException: If file is invalid
            FileTooLargeException: If file exceeds max size
            UnsupportedFileTypeException: If file type not allowed
        """
        if not file.filename:
            raise InvalidFileException("Filename is required", None)

        # Check extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeException(
                file.content_type or "unknown",
                file.filename
            )

        # Check MIME type
        if file.content_type and file.content_type not in self.ALLOWED_MIME_TYPES:
            raise UnsupportedFileTypeException(
                file.content_type,
                file.filename
            )

        # Check file size (read and seek back)
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Seek back to start

        if file_size > settings.MAX_FILE_SIZE:
            raise FileTooLargeException(
                file_size,
                settings.MAX_FILE_SIZE,
                file.filename
            )

        logger.info(
            "file_validated",
            filename=file.filename,
            size=file_size,
            mime_type=file.content_type
        )

    async def _calculate_hash(self, file: UploadFile) -> str:
        """Calculate SHA256 hash of file content"""
        sha256 = hashlib.sha256()
        file.file.seek(0)

        while chunk := file.file.read(8192):
            sha256.update(chunk)

        file.file.seek(0)  # Reset for next read
        return sha256.hexdigest()

    async def _save_temp_file(self, file: UploadFile) -> str:
        """Save uploaded file to temporary location"""
        file_ext = os.path.splitext(file.filename)[1]
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext
        )

        try:
            file.file.seek(0)
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            logger.info("temp_file_saved", path=temp_file.name)
            return temp_file.name
        finally:
            temp_file.close()

    async def _get_or_create_tag(self, tag_name: str) -> Tag:
        """Get existing tag or create new one"""
        # Check if tag exists
        result = await self.db.execute(
            select(Tag).where(Tag.name == tag_name.lower())
        )
        tag = result.scalar_one_or_none()

        if tag:
            return tag

        # Create new tag
        tag = Tag(name=tag_name.lower())
        self.db.add(tag)
        await self.db.flush()  # Get ID without committing
        return tag

    @transactional
    async def upload_document(
        self,
        file: UploadFile,
        request: UploadDocumentRequest
    ) -> FileUploadResponse:
        """
        Handle complete document upload workflow

        Steps:
        1. Validate file
        2. Calculate hash and check duplicates
        3. Save to temp location
        4. Create document record in transaction
        5. Create upload task
        6. Queue async processing

        Args:
            file: Uploaded file
            request: Upload parameters (tags, chunk_size, etc.)

        Returns:
            FileUploadResponse with document_id and task_id

        Raises:
            InvalidFileException: Invalid file
            DuplicateDocumentException: File already exists
        """
        logger.info("upload_started", filename=file.filename)

        # Step 1: Validate file
        await self._validate_file(file)

        # Step 2: Calculate hash and check duplicates
        file_hash = await self._calculate_hash(file)

        # Check for duplicate
        result = await self.db.execute(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.name == file.filename
            )
        )
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            raise DuplicateDocumentException(file.filename, file_hash)

        # Step 3: Save to temp location
        temp_path = await self._save_temp_file(file)

        try:
            # Step 4: Create document record
            file.file.seek(0, 2)
            file_size = file.file.tell()

            document = Document(
                name=file.filename,
                file_hash=file_hash,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                status="pending",
            )

            # Add tags if provided
            if request.tags:
                for tag_name in request.tags:
                    tag = await self._get_or_create_tag(tag_name)
                    document.tags.append(tag)

            self.db.add(document)
            await self.db.flush()  # Get document ID

            # Step 5: Create upload task
            task = UploadTask(
                document_id=document.id,
                status="queued",
                progress=0,
            )
            self.db.add(task)
            await self.db.flush()  # Get task ID

            # Transaction commits here automatically via @transactional

            logger.info(
                "document_created",
                document_id=str(document.id),
                task_id=str(task.id),
                filename=file.filename
            )

            # Step 6: Queue async processing (outside transaction)
            process_document.delay(
                str(document.id),
                str(task.id),
                temp_path,
                request.chunk_size,
                request.chunk_overlap
            )

            return FileUploadResponse(
                document_id=str(document.id),
                task_id=str(task.id),
                message=f"Document '{file.filename}' uploaded successfully. Processing started.",
            )

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(
                "upload_failed",
                filename=file.filename,
                error=str(e),
                exc_info=True
            )
            raise
