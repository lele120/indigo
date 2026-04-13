"""
Celery tasks
"""
from app.tasks.document_tasks import process_document, cleanup_old_tasks

__all__ = ["process_document", "cleanup_old_tasks"]
