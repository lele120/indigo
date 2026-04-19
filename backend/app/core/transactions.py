"""
Transaction management utilities for ACID compliance
"""
from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def transaction(session: AsyncSession):
    """
    Async context manager for database transactions

    Ensures ACID properties:
    - Atomicity: All operations succeed or none
    - Consistency: Database constraints maintained
    - Isolation: Concurrent transactions don't interfere
    - Durability: Committed changes persist

    Usage:
        async with transaction(db):
            await db.execute(...)
            await db.execute(...)
            # Auto-commit on success, rollback on exception

    Args:
        session: AsyncSession instance

    Yields:
        AsyncSession: Same session for operations

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        yield session
        await session.commit()
        logger.debug("transaction_committed")
    except Exception as e:
        await session.rollback()
        logger.error(
            "transaction_rolled_back",
            error=str(e),
            exc_info=True
        )
        raise


def transactional(func: Callable) -> Callable:
    """
    Decorator for automatic transaction management in manager methods

    Wraps async methods to automatically handle commit/rollback.
    Assumes the first argument after self is 'db: AsyncSession' or
    the class has self.db attribute.

    Usage:
        class Manager:
            def __init__(self, db: AsyncSession):
                self.db = db

            @transactional
            async def create_document(self, ...):
                # Operations here
                # Auto-commit on success, rollback on error
                pass

    Args:
        func: Async function to wrap

    Returns:
        Wrapped async function with transaction management
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs) -> Any:
        # Get session from self.db
        if not hasattr(self, 'db'):
            raise AttributeError(
                f"{self.__class__.__name__} must have 'db' attribute for @transactional"
            )

        async with transaction(self.db):
            return await func(self, *args, **kwargs)

    return wrapper


def transactional_method(method: Callable) -> Callable:
    """
    Alternative decorator for methods where db is passed as argument

    Usage:
        @transactional_method
        async def update(self, db: AsyncSession, doc_id: str, data: dict):
            # Operations
            pass

    Args:
        method: Async method with db as first argument

    Returns:
        Wrapped method with transaction management
    """
    @wraps(method)
    async def wrapper(self, db: AsyncSession, *args, **kwargs) -> Any:
        async with transaction(db):
            return await method(self, db, *args, **kwargs)

    return wrapper
