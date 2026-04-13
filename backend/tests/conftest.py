"""
Pytest configuration and fixtures
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.document import Document, Tag, Chunk


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session

    This fixture creates an in-memory SQLite database for testing.
    Each test gets a fresh database that is cleaned up after the test.
    """
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_document_data():
    """Sample document data for testing"""
    return {
        "name": "test_document.pdf",
        "file_hash": "a" * 64,  # SHA256 hash (64 hex chars)
        "file_size": 12345,
        "mime_type": "application/pdf",
        "page_count": 10,
        "chunk_count": 0,
        "status": "pending",
    }


@pytest.fixture
def sample_chunk_data():
    """Sample chunk data for testing"""
    return {
        "chunk_index": 0,
        "text": "This is a sample chunk of text for testing purposes.",
        "token_count": 10,
        "char_count": 53,
        "page_number": 1,
        "section_heading": "Introduction",
        "chunk_type": "text",
    }


@pytest.fixture
def sample_pages_data():
    """Sample PDF pages data with headings"""
    return [
        {
            "page_number": 1,
            "text": "Introduction\n\nThis is the introduction text...",
            "char_count": 100,
            "headings": [
                {"text": "Introduction", "font_size": 14.0, "position": 50},
            ],
        },
        {
            "page_number": 2,
            "text": "Background\n\nThis is the background section...",
            "char_count": 120,
            "headings": [
                {"text": "Background", "font_size": 14.0, "position": 60},
            ],
        },
    ]
