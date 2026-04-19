"""
Document CRUD operations
"""
from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
import hashlib

from app.models.document import Document, Tag, UploadTask
from app.schemas.document import DocumentCreate, DocumentUpdate


class DocumentService:
    """Service for document CRUD operations"""

    @staticmethod
    def get_document(db: Session, document_id: UUID) -> Optional[Document]:
        """Get a document by ID"""
        return db.query(Document).filter(Document.id == document_id).first()

    @staticmethod
    def get_documents(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Document], int]:
        """
        Get documents with filters and pagination
        Returns (documents, total_count)
        """
        query = db.query(Document)

        # Filter by status
        if status:
            query = query.filter(Document.status == status)

        # Filter by tags
        if tags:
            query = query.join(Document.tags).filter(Tag.name.in_(tags))

        # Search in document name
        if search:
            query = query.filter(Document.name.ilike(f"%{search}%"))

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        documents = (
            query.order_by(desc(Document.uploaded_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return documents, total

    @staticmethod
    def create_document(db: Session, document: DocumentCreate) -> Document:
        """Create a new document"""
        # Create document
        db_document = Document(
            name=document.name,
            file_hash=document.file_hash,
            file_size=document.file_size,
            mime_type=document.mime_type,
            status="pending",
        )

        # Add tags if provided
        if document.tags:
            for tag_name in document.tags:
                tag = DocumentService.get_or_create_tag(db, tag_name)
                db_document.tags.append(tag)

        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        return db_document

    @staticmethod
    def update_document(
        db: Session, document_id: UUID, document_update: DocumentUpdate
    ) -> Optional[Document]:
        """Update a document"""
        db_document = DocumentService.get_document(db, document_id)
        if not db_document:
            return None

        # Update fields
        if document_update.name is not None:
            db_document.name = document_update.name

        # Update tags
        if document_update.tags is not None:
            db_document.tags = []
            for tag_name in document_update.tags:
                tag = DocumentService.get_or_create_tag(db, tag_name)
                db_document.tags.append(tag)

        db.commit()
        db.refresh(db_document)
        return db_document

    @staticmethod
    def delete_document(db: Session, document_id: UUID) -> bool:
        """Delete a document"""
        db_document = DocumentService.get_document(db, document_id)
        if not db_document:
            return False

        db.delete(db_document)
        db.commit()
        return True

    @staticmethod
    def get_or_create_tag(db: Session, tag_name: str) -> Tag:
        """Get existing tag or create new one"""
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        return tag

    @staticmethod
    def get_all_tags(db: Session) -> List[Tag]:
        """Get all tags"""
        return db.query(Tag).order_by(Tag.name).all()

    @staticmethod
    def create_upload_task(db: Session, document_id: UUID) -> UploadTask:
        """Create an upload task for a document"""
        task = UploadTask(
            document_id=document_id,
            status="queued",
            progress=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def get_upload_task(db: Session, task_id: UUID) -> Optional[UploadTask]:
        """Get upload task by ID"""
        return db.query(UploadTask).filter(UploadTask.id == task_id).first()

    @staticmethod
    def update_task_progress(
        db: Session, task_id: UUID, progress: int, status: Optional[str] = None
    ) -> Optional[UploadTask]:
        """Update task progress"""
        task = DocumentService.get_upload_task(db, task_id)
        if not task:
            return None

        task.progress = progress
        if status:
            task.status = status

        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def calculate_file_hash(file_content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()

    @staticmethod
    def check_duplicate(db: Session, file_hash: str) -> Optional[Document]:
        """Check if document with same hash already exists"""
        return db.query(Document).filter(Document.file_hash == file_hash).first()

    @staticmethod
    def get_stats(db: Session) -> Dict[str, any]:
        """
        Get document statistics with a single optimized query
        Returns counts by status and list of all tag names
        """
        # Single query to get all counts by status using CASE expressions
        result = db.query(
            func.count(Document.id).label('total'),
            func.sum(case((Document.status == 'pending', 1), else_=0)).label('pending'),
            func.sum(case((Document.status == 'processing', 1), else_=0)).label('processing'),
            func.sum(case((Document.status == 'completed', 1), else_=0)).label('completed'),
            func.sum(case((Document.status == 'failed', 1), else_=0)).label('failed'),
        ).first()

        # Get all unique tag names
        tags = db.query(Tag.name).order_by(Tag.name).all()
        tag_names = [tag[0] for tag in tags]

        return {
            'total': result.total or 0,
            'pending': result.pending or 0,
            'processing': result.processing or 0,
            'completed': result.completed or 0,
            'failed': result.failed or 0,
            'tags': tag_names,
        }
