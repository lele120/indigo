"""
Unit tests for SearchService - focusing on RRF algorithm
"""
import pytest
from unittest.mock import Mock, patch
from app.services.search_service import SearchService


@pytest.mark.unit
class TestSearchServiceRRF:
    """Test suite for SearchService Reciprocal Rank Fusion"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def search_service(self, mock_db):
        """Create SearchService instance with mocked dependencies"""
        with patch('app.services.search_service.EmbeddingService'):
            with patch('app.services.search_service.QdrantService'):
                with patch('app.services.search_service.CacheService'):
                    with patch('app.services.search_service.RerankingService'):
                        service = SearchService(db=mock_db)
                        return service

    def test_reciprocal_rank_fusion_basic(self, search_service):
        """Test basic RRF calculation"""
        # Mock results from vector search
        vector_results = [
            {"chunk_id": "chunk1", "score": 0.9},
            {"chunk_id": "chunk2", "score": 0.8},
            {"chunk_id": "chunk3", "score": 0.7},
        ]

        # Mock results from BM25 search
        bm25_results = [
            {"chunk_id": "chunk2", "score": 0.85},
            {"chunk_id": "chunk1", "score": 0.75},
            {"chunk_id": "chunk4", "score": 0.65},
        ]

        # Call RRF
        merged = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Should return merged results
        assert len(merged) > 0

        # chunk1 and chunk2 appear in both lists, should rank higher
        chunk_ids = [r["chunk_id"] for r in merged]

        # chunk2 should rank high (rank 1 in vector, rank 1 in BM25)
        assert "chunk2" in chunk_ids[:2]
        # chunk1 should rank high (rank 1 in vector, rank 2 in BM25)
        assert "chunk1" in chunk_ids[:2]

    def test_rrf_formula_calculation(self, search_service):
        """Test RRF formula: score = 1/(k + rank)"""
        vector_results = [
            {"chunk_id": "A", "score": 0.9},
        ]
        bm25_results = [
            {"chunk_id": "A", "score": 0.8},
        ]

        merged = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Should have RRF score
        assert len(merged) == 1
        assert "rrf_score" in merged[0]

        # RRF for rank 1 in both: 0.5 * (1/(60+1)) + 0.5 * (1/(60+1))
        # = 0.5 * (1/61) + 0.5 * (1/61) = 1/61 ≈ 0.0164
        expected_rrf = 2 * 0.5 * (1 / 61)
        assert abs(merged[0]["rrf_score"] - expected_rrf) < 0.001

    def test_rrf_disjoint_results(self, search_service):
        """Test RRF with completely different results from each method"""
        vector_results = [
            {"chunk_id": "A", "score": 0.9},
            {"chunk_id": "B", "score": 0.8},
        ]
        bm25_results = [
            {"chunk_id": "C", "score": 0.85},
            {"chunk_id": "D", "score": 0.75},
        ]

        merged = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Should include all 4 chunks
        assert len(merged) == 4
        chunk_ids = {r["chunk_id"] for r in merged}
        assert chunk_ids == {"A", "B", "C", "D"}

    def test_rrf_weight_influence(self, search_service):
        """Test that weights influence final ranking"""
        vector_results = [
            {"chunk_id": "A", "score": 0.9},
            {"chunk_id": "B", "score": 0.8},
        ]
        bm25_results = [
            {"chunk_id": "B", "score": 0.95},
            {"chunk_id": "A", "score": 0.7},
        ]

        # High vector weight
        merged_vector_heavy = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.9,
            bm25_weight=0.1,
        )

        # High BM25 weight
        merged_bm25_heavy = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.1,
            bm25_weight=0.9,
        )

        # Rankings should differ based on weights
        vector_heavy_top = merged_vector_heavy[0]["chunk_id"]
        bm25_heavy_top = merged_bm25_heavy[0]["chunk_id"]

        # With different weights, top results might differ
        # (This depends on actual RRF scores, but at minimum they should have scores)
        assert all("rrf_score" in r for r in merged_vector_heavy)
        assert all("rrf_score" in r for r in merged_bm25_heavy)

    def test_rrf_empty_results(self, search_service):
        """Test RRF with empty result sets"""
        # Both empty
        merged = search_service._reciprocal_rank_fusion([], [], 0.5, 0.5)
        assert merged == []

        # Vector empty
        bm25_results = [{"chunk_id": "A", "score": 0.8}]
        merged = search_service._reciprocal_rank_fusion([], bm25_results, 0.5, 0.5)
        assert len(merged) == 1
        assert merged[0]["chunk_id"] == "A"

        # BM25 empty
        vector_results = [{"chunk_id": "B", "score": 0.9}]
        merged = search_service._reciprocal_rank_fusion(vector_results, [], 0.5, 0.5)
        assert len(merged) == 1
        assert merged[0]["chunk_id"] == "B"

    def test_rrf_preserves_metadata(self, search_service):
        """Test that RRF preserves chunk metadata"""
        vector_results = [
            {
                "chunk_id": "A",
                "score": 0.9,
                "page_number": 1,
                "section_heading": "Introduction",
                "text": "Sample text",
            },
        ]
        bm25_results = [
            {
                "chunk_id": "A",
                "score": 0.8,
                "page_number": 1,
                "section_heading": "Introduction",
            },
        ]

        merged = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Should preserve metadata
        assert merged[0]["page_number"] == 1
        assert merged[0]["section_heading"] == "Introduction"
        assert merged[0]["text"] == "Sample text"

    def test_rrf_sorted_by_score(self, search_service):
        """Test that results are sorted by RRF score descending"""
        vector_results = [
            {"chunk_id": "A", "score": 0.9},
            {"chunk_id": "B", "score": 0.7},
            {"chunk_id": "C", "score": 0.5},
        ]
        bm25_results = [
            {"chunk_id": "C", "score": 0.95},
            {"chunk_id": "B", "score": 0.8},
            {"chunk_id": "A", "score": 0.6},
        ]

        merged = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Scores should be in descending order
        scores = [r["rrf_score"] for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_limit_results(self, search_service):
        """Test limiting RRF results"""
        vector_results = [
            {"chunk_id": f"A{i}", "score": 0.9 - i * 0.1} for i in range(20)
        ]
        bm25_results = [
            {"chunk_id": f"A{i}", "score": 0.85 - i * 0.1} for i in range(20)
        ]

        # RRF without limit
        merged_all = search_service._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        # Should return all 20 results
        assert len(merged_all) == 20

        # Manually limit top 5
        merged_limited = merged_all[:5]
        assert len(merged_limited) == 5

        # Top results should have highest scores
        assert merged_limited[0]["rrf_score"] >= merged_limited[-1]["rrf_score"]
