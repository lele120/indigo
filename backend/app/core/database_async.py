"""
Async database configuration for SQLAlchemy
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Create async engine
# Replace postgresql:// with postgresql+asyncpg:// for async driver
async_database_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine = create_async_engine(
    async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    poolclass=NullPool if "test" in async_database_url else None,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session

    Usage in FastAPI:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_async_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("database_error", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()


async def init_async_db():
    """Initialize async database connection (for startup)"""
    async with async_engine.begin() as conn:
        logger.info("async_database_initialized")


async def close_async_db():
    """Close async database connection (for shutdown)"""
    await async_engine.dispose()
    logger.info("async_database_closed")
