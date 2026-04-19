"""
Custom application exceptions for centralized error handling
"""
from typing import Optional, Dict, Any


class AppException(Exception):
    """
    Base application exception

    All custom exceptions inherit from this for centralized handling.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code
        details: Optional additional details (dict)
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# Document-related exceptions
class DocumentNotFoundException(AppException):
    """Document not found in database"""

    def __init__(self, document_id: str):
        super().__init__(
            message=f"Document with ID '{document_id}' not found",
            status_code=404,
            details={"document_id": document_id}
        )


class DuplicateDocumentException(AppException):
    """Document already exists (duplicate hash)"""

    def __init__(self, filename: str, file_hash: str):
        super().__init__(
            message=f"Document '{filename}' already exists with hash {file_hash[:8]}...",
            status_code=409,
            details={"filename": filename, "file_hash": file_hash}
        )


class DocumentProcessingException(AppException):
    """Error during document processing"""

    def __init__(self, document_id: str, reason: str):
        super().__init__(
            message=f"Failed to process document: {reason}",
            status_code=500,
            details={"document_id": document_id, "reason": reason}
        )


# File-related exceptions
class InvalidFileException(AppException):
    """Invalid file upload (type, size, format)"""

    def __init__(self, reason: str, filename: Optional[str] = None):
        details = {"reason": reason}
        if filename:
            details["filename"] = filename

        super().__init__(
            message=f"Invalid file: {reason}",
            status_code=400,
            details=details
        )


class FileTooLargeException(AppException):
    """File exceeds maximum size"""

    def __init__(self, size: int, max_size: int, filename: str):
        super().__init__(
            message=f"File '{filename}' ({size} bytes) exceeds maximum size ({max_size} bytes)",
            status_code=413,
            details={
                "filename": filename,
                "size": size,
                "max_size": max_size
            }
        )


class UnsupportedFileTypeException(AppException):
    """File type not supported"""

    def __init__(self, mime_type: str, filename: str):
        super().__init__(
            message=f"File type '{mime_type}' is not supported",
            status_code=415,
            details={
                "filename": filename,
                "mime_type": mime_type,
                "supported_types": [
                    "application/pdf",
                    "text/plain",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ]
            }
        )


# Search-related exceptions
class SearchException(AppException):
    """Error during search operation"""

    def __init__(self, reason: str, query: Optional[str] = None):
        details = {"reason": reason}
        if query:
            details["query"] = query

        super().__init__(
            message=f"Search failed: {reason}",
            status_code=500,
            details=details
        )


class InvalidSearchParametersException(AppException):
    """Invalid search parameters provided"""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Invalid search parameters: {reason}",
            status_code=400,
            details={"reason": reason}
        )


# Tag-related exceptions
class TagNotFoundException(AppException):
    """Tag not found in database"""

    def __init__(self, tag_name: str):
        super().__init__(
            message=f"Tag '{tag_name}' not found",
            status_code=404,
            details={"tag_name": tag_name}
        )


class InvalidTagException(AppException):
    """Invalid tag name or format"""

    def __init__(self, tag_name: str, reason: str):
        super().__init__(
            message=f"Invalid tag '{tag_name}': {reason}",
            status_code=400,
            details={"tag_name": tag_name, "reason": reason}
        )


# Task-related exceptions
class TaskNotFoundException(AppException):
    """Upload task not found"""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task with ID '{task_id}' not found",
            status_code=404,
            details={"task_id": task_id}
        )


class TaskFailedException(AppException):
    """Task execution failed"""

    def __init__(self, task_id: str, error_message: str):
        super().__init__(
            message=f"Task {task_id} failed: {error_message}",
            status_code=500,
            details={"task_id": task_id, "error": error_message}
        )


# Database-related exceptions
class DatabaseException(AppException):
    """Generic database error"""

    def __init__(self, operation: str, reason: str):
        super().__init__(
            message=f"Database operation '{operation}' failed: {reason}",
            status_code=500,
            details={"operation": operation, "reason": reason}
        )


# Validation exceptions
class ValidationException(AppException):
    """Request validation failed"""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Validation error for '{field}': {reason}",
            status_code=422,
            details={"field": field, "reason": reason}
        )
