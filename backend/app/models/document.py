from sqlalchemy import Column, String, BigInteger, Integer, DateTime, ForeignKey, Table, Text, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.models.base import Base


# Association table for many-to-many relationship
class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_type = Column(String(50))  # File type: pdf, docx, excel, etc.
    author = Column(String(200))  # Author extracted from document metadata
    page_count = Column(Integer)
    chunk_count = Column(Integer, default=0)
    has_embeddings = Column(Boolean, default=True)  # False if embedding generation failed
    status = Column(
        String(20),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')"),
        default='pending'
    )
    error_message = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tags = relationship("Tag", secondary="document_tags", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    upload_task = relationship("UploadTask", back_populates="document", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='check_status'),
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    documents = relationship("Document", secondary="document_tags", back_populates="tags")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(
        String(10),
        CheckConstraint("chunk_type IN ('text', 'table', 'image')"),
        nullable=False
    )
    page_number = Column(Integer)
    section_heading = Column(String(500), nullable=True)  # Section or heading title
    text = Column(Text)  # Full chunk text
    text_preview = Column(Text)  # First 200 chars
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        CheckConstraint("chunk_type IN ('text', 'table', 'image')", name='check_chunk_type'),
    )


class UploadTask(Base):
    __tablename__ = "upload_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status = Column(
        String(20),
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed')"),
        default='queued'
    )
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="upload_task")

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed')", name='check_upload_status'),
        CheckConstraint("progress >= 0 AND progress <= 100", name='check_progress_range'),
    )
