"""
Celery tasks for document processing
"""
import os
import structlog
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.document_service import DocumentService
from app.services.document_processor import DocumentProcessor
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.models.document import Document, UploadTask, Chunk

logger = structlog.get_logger()


@celery_app.task(bind=True, name="app.tasks.document_tasks.process_document")
def process_document(self, document_id: str, task_id: str, file_path: str, chunk_size: int = None, chunk_overlap: int = None):
    """
    Process uploaded document asynchronously (supports PDF, DOCX, Excel, CSV, TXT, MD, PPTX)

    Steps:
    1. Update task status to 'processing'
    2. Extract text from document (any supported format)
    3. Chunk text with LangChain
    4. Generate embeddings with OpenAI (with fallback to text-only mode)
    5. Store in Qdrant (if embeddings available)
    6. Save chunks to PostgreSQL
    7. Update document status

    Args:
        document_id: UUID of the document
        task_id: UUID of the upload task
        file_path: Path to the uploaded file
        chunk_size: Optional custom chunk size in tokens
        chunk_overlap: Optional custom chunk overlap in tokens
    """
    db: Session = SessionLocal()

    try:
        logger.info(
            "document_processing_started",
            document_id=document_id,
            task_id=task_id,
            file_path=file_path,
        )

        # Get document and task
        doc_uuid = UUID(document_id)
        task_uuid = UUID(task_id)

        document = DocumentService.get_document(db, doc_uuid)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Update document status
        document.status = "processing"
        db.commit()

        # Update task status
        task = DocumentService.get_upload_task(db, task_uuid)
        if task:
            task.status = "processing"
            task.started_at = datetime.utcnow()
            task.progress = 5
            db.commit()

        # Step 1: Extract metadata and text from document (any format)
        logger.info("extracting_document_metadata", document_id=document_id, file_path=file_path)
        file_type = DocumentProcessor.get_file_type(file_path)
        metadata = DocumentProcessor.extract_metadata(file_path)
        full_text, page_count, pages_data = DocumentProcessor.extract_text(file_path)

        # Update document metadata, page count, and file type
        document.page_count = page_count
        document.file_type = file_type
        document.author = metadata.get("author")
        db.commit()

        logger.info("document_metadata_extracted", document_id=document_id, author=document.author, file_type=file_type)

        if task:
            task.progress = 20
            db.commit()

        # Step 2: Chunk text
        logger.info("chunking_text", document_id=document_id, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunking_service = ChunkingService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks_data = chunking_service.chunk_text(
            full_text,
            document_id,
            pages_data=pages_data
        )

        if task:
            task.progress = 40
            db.commit()

        # Step 3: Generate embeddings (with fallback)
        logger.info("generating_embeddings", document_id=document_id)
        embedding_service = EmbeddingService()
        chunks_with_embeddings, has_embeddings = embedding_service.generate_embeddings(
            chunks_data,
            document_id,
            fallback_on_error=True  # Enable fallback to text-only mode
        )

        # Update document embedding status
        document.has_embeddings = has_embeddings
        db.commit()

        if task:
            task.progress = 70
            db.commit()

        # Step 4: Save chunks to PostgreSQL
        logger.info("saving_chunks_to_db", document_id=document_id)
        chunk_db_ids = []
        for chunk_data in chunks_with_embeddings:
            chunk_record = Chunk(
                document_id=doc_uuid,
                chunk_index=chunk_data["chunk_index"],
                chunk_type=chunk_data.get("chunk_type", "text"),
                page_number=chunk_data.get("page_number"),
                section_heading=chunk_data.get("section_heading"),  # Section heading
                text=chunk_data["text"],  # Full text
                text_preview=chunk_data["text"][:200],  # First 200 chars
            )
            db.add(chunk_record)
            db.flush()  # Get the ID without committing
            chunk_db_ids.append(chunk_record.id)

        db.commit()

        if task:
            task.progress = 80
            db.commit()

        # Step 5: Store in Qdrant (only if embeddings available)
        if has_embeddings:
            logger.info("storing_in_qdrant", document_id=document_id)
            qdrant_service = QdrantService()
            qdrant_service.upsert_chunks(
                doc_uuid,
                chunks_with_embeddings,
                chunk_db_ids
            )
        else:
            logger.warning(
                "skipping_qdrant_storage",
                document_id=document_id,
                message="No embeddings available - document will use BM25 search only"
            )

        if task:
            task.progress = 95
            db.commit()

        # Step 6: Clean up temporary file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("temp_file_deleted", file_path=file_path)
        except Exception as e:
            logger.warning("temp_file_cleanup_failed", file_path=file_path, error=str(e))

        # Complete
        document.status = "completed"
        document.chunk_count = len(chunks_with_embeddings)
        db.commit()

        if task:
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.utcnow()
            db.commit()

        logger.info(
            "document_processing_completed",
            document_id=document_id,
            task_id=task_id,
            page_count=page_count,
            chunk_count=len(chunks_with_embeddings),
        )

    except Exception as e:
        logger.error(
            "document_processing_failed",
            document_id=document_id,
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )

        # Update document status
        try:
            document = DocumentService.get_document(db, UUID(document_id))
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()

            # Update task status
            task = DocumentService.get_upload_task(db, UUID(task_id))
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.commit()
        except Exception as update_error:
            logger.error(
                "failed_to_update_error_status",
                error=str(update_error),
            )

        # Clean up temp file on error
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

        raise

    finally:
        db.close()


@celery_app.task(name="app.tasks.document_tasks.cleanup_old_tasks")
def cleanup_old_tasks():
    """
    Cleanup old completed tasks (runs periodically)
    Remove tasks older than 7 days
    """
    db: Session = SessionLocal()

    try:
        from datetime import timedelta

        logger.info("cleanup_task_started")

        # Query and delete old tasks
        cutoff = datetime.utcnow() - timedelta(days=7)
        deleted_count = db.query(UploadTask).filter(
            UploadTask.completed_at < cutoff,
            UploadTask.status.in_(["completed", "failed"])
        ).delete()

        db.commit()

        logger.info("cleanup_task_completed", deleted_count=deleted_count)

    except Exception as e:
        logger.error("cleanup_task_failed", error=str(e), exc_info=True)
        raise
    finally:
        db.close()
