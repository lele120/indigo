"""
Upload Manager - Orchestrates document upload workflow

Business logic:
- File validation (type, size, format)
- File operations (hash calculation, temp storage)
- Duplicate detection via DocumentService
- Document creation via DocumentService
- Task creation via UploadTaskService
- Celery task queuing

Uses DocumentService, TagService, UploadTaskService for data access.
"""
import os
import tempfile
import hashlib
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import shutil

from app.core.transactions import transactional
from app.core.exceptions import (
    InvalidFileException,
    FileTooLargeException,
    UnsupportedFileTypeException,
    DuplicateDocumentException,
)
from app.models.document import Document
from app.schemas.document import FileUploadResponse, DocumentCreate
from app.schemas.requests import UploadDocumentRequest
from app.core.config import settings
from app.services.document_service import DocumentService
from app.services.tag_service import TagService
from app.services.upload_task_service import UploadTaskService
from app.tasks.document_tasks import process_document

logger = structlog.get_logger()


class UploadManager:
    """Manager for document upload business logic orchestration"""

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
        self.document_service = DocumentService(db)
        self.tag_service = TagService(db)
        self.upload_task_service = UploadTaskService(db)

    async def _validate_file(self, file: UploadFile) -> None:
        """
        Validate file before processing (Business logic)

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
        """Calculate SHA256 hash of file content (Business logic)"""
        sha256 = hashlib.sha256()
        file.file.seek(0)

        while chunk := file.file.read(8192):
            sha256.update(chunk)

        file.file.seek(0)  # Reset for next read
        return sha256.hexdigest()

    async def _save_temp_file(self, file: UploadFile) -> str:
        """Save uploaded file to temporary location (Business logic).

        Writes to /tmp/uploads which is a shared Docker volume also mounted
        into the Celery worker container, so the worker can read the file.
        """
        file_ext = os.path.splitext(file.filename)[1]
        upload_dir = "/tmp/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            dir=upload_dir,
        )

        try:
            file.file.seek(0)
            shutil.copyfileobj(file.file, temp_file)
            temp_file.flush()
            logger.info("temp_file_saved", path=temp_file.name)
            return temp_file.name
        finally:
            temp_file.close()

    async def upload_document(
        self,
        file: UploadFile,
        request: UploadDocumentRequest
    ) -> FileUploadResponse:
        """Orchestrate the full upload workflow.

        Persists the document + task inside a single transaction, then queues
        the Celery job only AFTER the commit is visible. This avoids the
        race where the worker picks up the task and queries Postgres before
        the producing transaction has committed — which surfaced as
        intermittent "Document X not found" failures.
        """
        logger.info("upload_started", filename=file.filename)

        await self._validate_file(file)
        file_hash = await self._calculate_hash(file)

        existing_doc = await self.document_service.get_by_hash(file_hash)
        if existing_doc and existing_doc.name == file.filename:
            raise DuplicateDocumentException(file.filename, file_hash)

        temp_path = await self._save_temp_file(file)

        try:
            document_id, task_id = await self._persist_document_records(
                file, request, file_hash
            )
        except Exception:
            # Transactional step failed — clean up the temp file we already
            # staged on the shared volume.
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

        # Transaction has committed at this point. The Celery worker can now
        # safely query Postgres for document_id / task_id without racing.
        process_document.delay(
            str(document_id),
            str(task_id),
            temp_path,
            request.chunk_size,
            request.chunk_overlap,
        )

        return FileUploadResponse(
            document_id=str(document_id),
            task_id=str(task_id),
            message=f"Document '{file.filename}' uploaded successfully. Processing started.",
        )

    @transactional
    async def _persist_document_records(
        self,
        file: UploadFile,
        request: UploadDocumentRequest,
        file_hash: str,
    ):
        """Create the Document + UploadTask rows in a single committed txn.

        Tag ORM objects are resolved and attached before the document enters
        the session (transient assignment) to avoid async lazy-load issues.
        """
        file.file.seek(0, 2)
        file_size = file.file.tell()

        document_create = DocumentCreate(
            name=file.filename,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            tags=request.tags if request.tags else None,
        )

        tag_objects = []
        if request.tags:
            for tag_name in request.tags:
                tag = await self.tag_service.get_or_create(tag_name)
                tag_objects.append(tag)

        document = await self.document_service.create(
            document_create,
            tags=tag_objects or None,
        )
        task = await self.upload_task_service.create(document.id)

        logger.info(
            "document_created",
            document_id=str(document.id),
            task_id=str(task.id),
            filename=file.filename,
        )
        return document.id, task.id
