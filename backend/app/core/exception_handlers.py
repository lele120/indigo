"""
Centralized exception handlers for FastAPI

Provides consistent error responses across all endpoints.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
import structlog

from app.core.exceptions import AppException

logger = structlog.get_logger()


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handler for custom AppException and its subclasses

    Returns consistent JSON error response with:
    - error: Exception class name
    - message: Human-readable message
    - details: Additional context (optional)
    - path: Request path that caused the error

    Args:
        request: FastAPI Request object
        exc: AppException instance

    Returns:
        JSONResponse with error details
    """
    logger.error(
        "app_exception",
        exception=exc.__class__.__name__,
        message=exc.message,
        status_code=exc.status_code,
        path=request.url.path,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url.path),
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handler for Pydantic validation errors

    Formats validation errors in a user-friendly way.

    Args:
        request: FastAPI Request object
        exc: RequestValidationError from Pydantic

    Returns:
        JSONResponse with validation errors
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": {"errors": errors},
            "path": str(request.url.path),
        },
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """
    Handler for Pydantic ValidationError (from model validation)

    Args:
        request: FastAPI Request object
        exc: ValidationError from Pydantic

    Returns:
        JSONResponse with validation errors
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "pydantic_validation_error",
        path=request.url.path,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Data validation failed",
            "details": {"errors": errors},
            "path": str(request.url.path),
        },
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handler for SQLAlchemy database errors

    Catches database-related exceptions and returns generic error
    (avoids exposing database internals to clients).

    Args:
        request: FastAPI Request object
        exc: SQLAlchemyError instance

    Returns:
        JSONResponse with generic database error
    """
    logger.error(
        "database_error",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "DatabaseError",
            "message": "A database error occurred. Please try again later.",
            "details": {},
            "path": str(request.url.path),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unhandled exceptions

    Logs the error and returns a generic 500 response
    (avoids exposing internal errors to clients).

    Args:
        request: FastAPI Request object
        exc: Any unhandled exception

    Returns:
        JSONResponse with generic error message
    """
    logger.error(
        "unhandled_exception",
        exception=exc.__class__.__name__,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please try again later.",
            "details": {},
            "path": str(request.url.path),
        },
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with FastAPI app

    Call this in main.py after creating the FastAPI app instance.

    Usage:
        from app.core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("exception_handlers_registered")
