"""
Unit tests for ChunkingService
"""
import pytest
from app.services.chunking_service import ChunkingService


@pytest.mark.unit
class TestChunkingService:
    """Test suite for ChunkingService"""

    def test_token_length_calculation(self):
        """Test that token length is calculated correctly"""
        service = ChunkingService(chunk_size=100, chunk_overlap=20)

        # Simple text
        text = "This is a test sentence."
        token_count = service._token_length(text)

        # Should be more than 0
        assert token_count > 0
        # Should be less than word count (tokens can be subwords)
        assert token_count <= len(text.split())

    def test_chunk_text_basic(self):
        """Test basic text chunking"""
        service = ChunkingService(chunk_size=50, chunk_overlap=10)

        text = "This is a test. " * 20  # Repeat to create long text
        chunks = service.chunk_text(text, document_id="test-id")

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should have required fields
        for chunk in chunks:
            assert "chunk_index" in chunk
            assert "text" in chunk
            assert "token_count" in chunk
            assert "char_count" in chunk
            assert "chunk_type" in chunk
            assert chunk["chunk_type"] == "text"

        # Chunk indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i

    def test_chunk_with_overlap(self):
        """Test that chunks have proper overlap"""
        service = ChunkingService(chunk_size=50, chunk_overlap=10)

        text = "A " * 100  # Simple repeating pattern
        chunks = service.chunk_text(text, document_id="test-id")

        # Should have overlap between consecutive chunks
        if len(chunks) > 1:
            # Check that there's some overlap
            chunk1_end = chunks[0]["text"][-20:]
            chunk2_start = chunks[1]["text"][:20]

            # Some words should appear in both (overlap)
            assert any(word in chunk2_start for word in chunk1_end.split())

    def test_page_number_estimation(self, sample_pages_data):
        """Test page number estimation from pages data"""
        service = ChunkingService()

        chunks = service.chunk_text(
            "Introduction This is the introduction text...",
            document_id="test-id",
            pages_data=sample_pages_data,
        )

        # Should assign page numbers
        assert chunks[0]["page_number"] is not None
        assert chunks[0]["page_number"] == 1

    def test_section_heading_detection(self, sample_pages_data):
        """Test section heading detection from pages data"""
        service = ChunkingService()

        # Text that matches first page with heading
        text = "Introduction This is the introduction text for testing purposes."

        chunks = service.chunk_text(
            text,
            document_id="test-id",
            pages_data=sample_pages_data,
        )

        # Should detect section heading
        assert len(chunks) > 0
        assert chunks[0]["section_heading"] is not None
        assert "Introduction" in chunks[0]["section_heading"]

    def test_empty_text(self):
        """Test chunking empty text"""
        service = ChunkingService()

        chunks = service.chunk_text("", document_id="test-id")

        # Should return empty list
        assert chunks == []

    def test_single_word(self):
        """Test chunking a single word"""
        service = ChunkingService(chunk_size=100)

        chunks = service.chunk_text("Hello", document_id="test-id")

        # Should create one chunk
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello"
        assert chunks[0]["token_count"] > 0

    def test_custom_chunk_size(self):
        """Test custom chunk size parameter"""
        # Small chunks
        small_service = ChunkingService(chunk_size=20, chunk_overlap=5)
        # Large chunks
        large_service = ChunkingService(chunk_size=200, chunk_overlap=20)

        text = "This is a test sentence. " * 50

        small_chunks = small_service.chunk_text(text, document_id="test-id")
        large_chunks = large_service.chunk_text(text, document_id="test-id")

        # Small chunks should create more chunks
        assert len(small_chunks) > len(large_chunks)

    def test_chunk_by_page(self, sample_pages_data):
        """Test page-by-page chunking method"""
        service = ChunkingService()

        chunks = service.chunk_by_page(sample_pages_data, document_id="test-id")

        # Should create chunks
        assert len(chunks) > 0

        # Should have correct page numbers
        page_numbers = {chunk["page_number"] for chunk in chunks}
        assert 1 in page_numbers
        assert 2 in page_numbers

    def test_find_section_heading_single_heading(self):
        """Test section heading detection when page has single heading"""
        service = ChunkingService()

        pages_data = [
            {
                "page_number": 1,
                "text": "Title\n\nSome content here...",
                "headings": [{"text": "Title", "font_size": 14.0, "position": 10}],
            }
        ]

        heading = service._find_section_heading(
            "Some content here...", pages_data, page_number=1
        )

        assert heading == "Title"

    def test_find_section_heading_no_headings(self):
        """Test section heading detection when page has no headings"""
        service = ChunkingService()

        pages_data = [
            {"page_number": 1, "text": "Just plain text...", "headings": []}
        ]

        heading = service._find_section_heading(
            "Just plain text...", pages_data, page_number=1
        )

        assert heading is None

    def test_find_section_heading_in_chunk_text(self):
        """Test section heading detection when heading appears in chunk"""
        service = ChunkingService()

        pages_data = [
            {
                "page_number": 1,
                "text": "Introduction\n\nThis is intro text...",
                "headings": [
                    {"text": "Introduction", "font_size": 14.0, "position": 10}
                ],
            }
        ]

        # Chunk contains the heading
        chunk_text = "Introduction This is intro text about the topic."
        heading = service._find_section_heading(chunk_text, pages_data, page_number=1)

        assert heading == "Introduction"
