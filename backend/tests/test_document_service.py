"""
Unit tests for DocumentService - focusing on deduplication
"""
import pytest
import hashlib
from app.services.document_service import DocumentService
from app.models.document import Document, Tag
from uuid import uuid4


@pytest.mark.unit
@pytest.mark.requires_db
class TestDocumentServiceDeduplication:
    """Test suite for DocumentService deduplication logic"""

    def test_calculate_file_hash(self):
        """Test SHA256 hash calculation"""
        content = b"This is test file content"

        hash_result = DocumentService.calculate_file_hash(content)

        # Should return 64-character hex string (SHA256)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

        # Should be deterministic
        hash_result2 = DocumentService.calculate_file_hash(content)
        assert hash_result == hash_result2

        # Verify against hashlib
        expected = hashlib.sha256(content).hexdigest()
        assert hash_result == expected

    def test_calculate_file_hash_empty(self):
        """Test hash calculation for empty content"""
        content = b""

        hash_result = DocumentService.calculate_file_hash(content)

        # Should still return valid hash
        assert len(hash_result) == 64

        # Empty content should have known SHA256 hash
        expected = hashlib.sha256(b"").hexdigest()
        assert hash_result == expected

    def test_calculate_file_hash_different_content(self):
        """Test that different content produces different hashes"""
        content1 = b"Document version 1"
        content2 = b"Document version 2"

        hash1 = DocumentService.calculate_file_hash(content1)
        hash2 = DocumentService.calculate_file_hash(content2)

        # Different content should have different hashes
        assert hash1 != hash2

    def test_check_duplicate_no_duplicate(self, db_session):
        """Test duplicate check when no duplicate exists"""
        file_hash = "a" * 64  # Valid SHA256 hash format

        result = DocumentService.check_duplicate(db_session, file_hash)

        # Should return None (no duplicate found)
        assert result is None

    def test_check_duplicate_found(self, db_session, sample_document_data):
        """Test duplicate check when duplicate exists"""
        # Create document with specific hash
        file_hash = "a" * 64
        document = Document(
            id=uuid4(),
            name="existing_doc.pdf",
            file_hash=file_hash,
            file_size=12345,
            mime_type="application/pdf",
            page_count=10,
            chunk_count=0,
            status="completed",
        )
        db_session.add(document)
        db_session.commit()

        # Check for duplicate
        result = DocumentService.check_duplicate(db_session, file_hash)

        # Should find the duplicate
        assert result is not None
        assert result.file_hash == file_hash
        assert result.name == "existing_doc.pdf"

    def test_check_duplicate_different_hash(self, db_session, sample_document_data):
        """Test that documents with different hashes are not considered duplicates"""
        # Create document with hash A
        document = Document(
            id=uuid4(),
            name="doc1.pdf",
            file_hash="a" * 64,
            file_size=12345,
            mime_type="application/pdf",
            page_count=10,
            chunk_count=0,
            status="completed",
        )
        db_session.add(document)
        db_session.commit()

        # Check for different hash B
        result = DocumentService.check_duplicate(db_session, "b" * 64)

        # Should not find duplicate
        assert result is None

    def test_deduplication_same_name_different_content(self, db_session):
        """Test that same filename with different content is NOT a duplicate"""
        # Document 1: same name, hash A
        doc1 = Document(
            id=uuid4(),
            name="report.pdf",
            file_hash="a" * 64,
            file_size=12345,
            mime_type="application/pdf",
            page_count=10,
            chunk_count=0,
            status="completed",
        )
        db_session.add(doc1)
        db_session.commit()

        # Check for same name but different hash
        result = DocumentService.check_duplicate(db_session, "b" * 64)

        # Should not be duplicate (different hash = different content)
        assert result is None

    def test_deduplication_different_name_same_content(self, db_session):
        """Test that different filename with same content IS a duplicate"""
        # Document 1: name A, hash X
        doc1 = Document(
            id=uuid4(),
            name="original.pdf",
            file_hash="x" * 64,
            file_size=12345,
            mime_type="application/pdf",
            page_count=10,
            chunk_count=0,
            status="completed",
        )
        db_session.add(doc1)
        db_session.commit()

        # Check for different name but same hash (same content)
        result = DocumentService.check_duplicate(db_session, "x" * 64)

        # Should find duplicate (same hash = same content)
        assert result is not None
        assert result.file_hash == "x" * 64

    def test_multiple_documents_same_hash(self, db_session):
        """Test handling multiple documents with same hash (edge case)"""
        # This shouldn't happen in production due to duplicate check,
        # but test that query returns first match
        file_hash = "z" * 64

        # Create two documents with same hash (simulating race condition)
        doc1 = Document(
            id=uuid4(),
            name="doc1.pdf",
            file_hash=file_hash,
            file_size=100,
            mime_type="application/pdf",
            page_count=1,
            chunk_count=0,
            status="completed",
        )
        doc2 = Document(
            id=uuid4(),
            name="doc2.pdf",
            file_hash=file_hash,
            file_size=100,
            mime_type="application/pdf",
            page_count=1,
            chunk_count=0,
            status="completed",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        db_session.commit()

        # Check for duplicate
        result = DocumentService.check_duplicate(db_session, file_hash)

        # Should return one of them
        assert result is not None
        assert result.file_hash == file_hash

    def test_hash_consistency_across_uploads(self):
        """Test that identical content always produces same hash"""
        content = b"Consistent test content"

        # Calculate hash multiple times
        hash1 = DocumentService.calculate_file_hash(content)
        hash2 = DocumentService.calculate_file_hash(content)
        hash3 = DocumentService.calculate_file_hash(content)

        # All should be identical
        assert hash1 == hash2 == hash3

    def test_hash_sensitivity_to_changes(self):
        """Test that even small changes produce different hash"""
        original = b"Original document content"
        modified = b"Original document Content"  # Changed C to uppercase

        hash_original = DocumentService.calculate_file_hash(original)
        hash_modified = DocumentService.calculate_file_hash(modified)

        # Even one character change should produce different hash
        assert hash_original != hash_modified

    def test_hash_binary_content(self):
        """Test hash calculation with binary content (like PDF bytes)"""
        # Simulate PDF binary content
        pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

        hash_result = DocumentService.calculate_file_hash(pdf_bytes)

        # Should handle binary content correctly
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)

    def test_large_file_hash(self):
        """Test hash calculation for large file content"""
        # Simulate 1MB file
        large_content = b"x" * (1024 * 1024)

        hash_result = DocumentService.calculate_file_hash(large_content)

        # Should still return valid hash
        assert len(hash_result) == 64

        # Should be reproducible
        hash_result2 = DocumentService.calculate_file_hash(large_content)
        assert hash_result == hash_result2
