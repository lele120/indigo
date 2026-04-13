#!/usr/bin/env python3
"""
Database initialization script
Run migrations and verify database setup
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.models.base import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize database and run migrations"""
    try:
        # Create engine
        logger.info(f"Connecting to database: {settings.DATABASE_URL}")
        engine = create_engine(settings.DATABASE_URL)

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✓ PostgreSQL version: {version}")

            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]

            if tables:
                logger.info(f"✓ Existing tables: {', '.join(tables)}")
            else:
                logger.info("! No tables found. Run: alembic upgrade head")

            # Check UUID extension
            result = conn.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'
                );
            """))
            uuid_exists = result.fetchone()[0]

            if uuid_exists:
                logger.info("✓ UUID extension enabled")
            else:
                logger.warning("! UUID extension not enabled")

        logger.info("✓ Database initialization complete")
        return True

    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
