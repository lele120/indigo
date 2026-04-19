"""
Hybrid Search Service combining Vector and BM25 retrieval with RRF
"""
from typing import List, Dict, Optional
from uuid import UUID
import structlog
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.cache_service import CacheService
from app.services.reranking_service import RerankingService
from app.models.document import Chunk
from app.core.config import settings

logger = structlog.get_logger()


class SearchService:
    """Hybrid search service combining vector and BM25 search with RRF"""

    def __init__(self, db: Session):
        """Initialize search service with database session"""
        self.db = db
        self.embedding_service = EmbeddingService()
        self.qdrant_service = QdrantService()
        self.cache_service = CacheService()
        self.reranking_service = RerankingService()

    def search(
        self,
        query: str,
        limit: int = 10,
        document_ids: Optional[List[str]] = None,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        use_hybrid: bool = True,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        use_cache: bool = True,
    ) -> List[Dict]:
        """
        Perform hybrid search combining vector and BM25 retrieval with caching

        Args:
            query: Search query text
            limit: Maximum number of results to return
            document_ids: Optional list of document IDs to filter by
            use_hybrid: If True, use hybrid search; if False, use vector only
            vector_weight: Weight for vector search results (0.0-1.0)
            bm25_weight: Weight for BM25 search results (0.0-1.0)
            use_cache: If True, use cached results when available

        Returns:
            List of search results with scores and metadata
        """
        # Try cache first
        if use_cache:
            cached_results = self.cache_service.get(
                "search",
                query=query,
                limit=limit,
                document_ids=document_ids,
                file_type=file_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                use_hybrid=use_hybrid,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )
            if cached_results is not None:
                logger.info("search_cache_hit", query=query)
                return cached_results

        logger.info(
            "search_started",
            query=query,
            limit=limit,
            use_hybrid=use_hybrid,
            use_cache=use_cache,
        )

        if not use_hybrid:
            # Vector search only
            results = self._vector_search(query, limit, document_ids, file_type, author, date_from, date_to)
        else:
            # Hybrid search: Vector + BM25 + RRF
            vector_results = self._vector_search(query, limit * 2, document_ids, file_type, author, date_from, date_to)
            bm25_results = self._bm25_search(query, limit * 2, document_ids, file_type, author, date_from, date_to)

            # Reciprocal Rank Fusion
            merged_results = self._reciprocal_rank_fusion(
                vector_results,
                bm25_results,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )

            # Apply cross-encoder reranking if enabled
            if settings.ENABLE_RERANKING:
                logger.info("applying_reranking", query=query, num_results=len(merged_results))
                merged_results = self.reranking_service.rerank(
                    query=query,
                    results=merged_results,
                    top_k=limit  # Rerank and return top K
                )
                results = merged_results
            else:
                # No reranking, just limit
                results = merged_results[:limit]

        logger.info(
            "search_completed",
            query=query,
            final_count=len(results),
        )

        # Cache results
        if use_cache and results:
            self.cache_service.set(
                "search",
                results,
                query=query,
                limit=limit,
                document_ids=document_ids,
                file_type=file_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                use_hybrid=use_hybrid,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )

        return results

    def _vector_search(
        self,
        query: str,
        limit: int,
        document_ids: Optional[List[str]] = None,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict]:
        """
        Perform vector similarity search using Qdrant with filters

        Args:
            query: Search query text
            limit: Maximum number of results
            document_ids: Optional document IDs to filter
            file_type: Optional file type filter
            author: Optional author filter
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            List of results with vector similarity scores
        """
        try:
            from app.models.document import Document

            # Apply filters to get filtered document IDs
            filtered_doc_ids = document_ids

            if file_type or author or date_from or date_to:
                # Query documents with filters
                doc_query = self.db.query(Document.id)

                if document_ids:
                    doc_query = doc_query.filter(Document.id.in_([UUID(did) for did in document_ids]))

                if file_type:
                    doc_query = doc_query.filter(Document.file_type == file_type)

                if author:
                    doc_query = doc_query.filter(Document.author.ilike(f"%{author}%"))

                if date_from:
                    doc_query = doc_query.filter(Document.uploaded_at >= date_from)

                if date_to:
                    doc_query = doc_query.filter(Document.uploaded_at <= date_to)

                filtered_doc_ids = [str(doc.id) for doc in doc_query.all()]

                if not filtered_doc_ids:
                    return []

            # Generate query embedding
            query_embedding = self.embedding_service.generate_single_embedding(query)

            # Search in Qdrant
            results = []
            if filtered_doc_ids:
                # Search in specific documents
                for doc_id in filtered_doc_ids:
                    doc_results = self.qdrant_service.search(
                        query_vector=query_embedding,
                        limit=limit,
                        document_id=doc_id,
                    )
                    results.extend(doc_results)
            else:
                # Search across all documents
                results = self.qdrant_service.search(
                    query_vector=query_embedding,
                    limit=limit,
                )

            # Sort by score and limit
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error("vector_search_failed", error=str(e), exc_info=True)
            return []

    def _bm25_search(
        self,
        query: str,
        limit: int,
        document_ids: Optional[List[str]] = None,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict]:
        """
        Perform BM25 keyword search on chunk texts with filters

        Args:
            query: Search query text
            limit: Maximum number of results
            document_ids: Optional document IDs to filter
            file_type: Optional file type filter
            author: Optional author filter (partial match)
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            List of results with BM25 scores
        """
        try:
            from app.models.document import Document

            # Query chunks from database with JOIN on documents
            chunks_query = self.db.query(Chunk).join(Document, Chunk.document_id == Document.id)

            # Apply filters
            if document_ids:
                chunks_query = chunks_query.filter(
                    Chunk.document_id.in_([UUID(did) for did in document_ids])
                )

            if file_type:
                chunks_query = chunks_query.filter(Document.file_type == file_type)

            if author:
                chunks_query = chunks_query.filter(Document.author.ilike(f"%{author}%"))

            if date_from:
                chunks_query = chunks_query.filter(Document.uploaded_at >= date_from)

            if date_to:
                chunks_query = chunks_query.filter(Document.uploaded_at <= date_to)

            chunks = chunks_query.all()

            if not chunks:
                return []

            # Prepare corpus for BM25
            # Strip Markdown syntax for better keyword matching
            from app.services.pdf_service import PDFService
            import re

            corpus = []
            chunk_map = {}
            for i, chunk in enumerate(chunks):
                # Use full text if available, otherwise use preview
                text = chunk.text or chunk.text_preview or ""

                # Strip Markdown syntax for BM25 indexing
                plain_text = PDFService.strip_markdown_syntax(text)

                # Tokenize using regex to extract only words (alphanumeric)
                tokens = re.findall(r'\b\w+\b', plain_text.lower())
                corpus.append(tokens)
                chunk_map[i] = chunk

            # Create BM25 index
            bm25 = BM25Okapi(corpus)

            # Tokenize query (same way as corpus: alphanumeric words only)
            query_tokens = re.findall(r'\b\w+\b', query.lower())

            # Get BM25 scores
            scores = bm25.get_scores(query_tokens)

            # Create results with scores
            results = []
            for i, score in enumerate(scores):
                if score > 0:  # Only include results with positive scores
                    chunk = chunk_map[i]
                    full_text = chunk.text or chunk.text_preview or ""
                    results.append({
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "text": full_text,
                        "text_preview": full_text[:200] if full_text else "",
                        "page_number": chunk.page_number,
                        "chunk_type": chunk.chunk_type,
                        "score": float(score),
                    })

            # Sort by score and limit
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error("bm25_search_failed", error=str(e), exc_info=True)
            return []

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        k: int = 60,
    ) -> List[Dict]:
        """
        Merge vector and BM25 results using Reciprocal Rank Fusion

        RRF formula: score(d) = Σ_r (weight / (k + rank_r(d)))

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            vector_weight: Weight for vector results
            bm25_weight: Weight for BM25 results
            k: Constant for RRF (typically 60)

        Returns:
            Merged and re-ranked results
        """
        # Create chunk_id to result mapping
        chunk_scores = {}

        # Process vector results
        for rank, result in enumerate(vector_results, start=1):
            chunk_id = result.get("chunk_id")
            if chunk_id:
                rrf_score = vector_weight / (k + rank)
                chunk_scores[chunk_id] = {
                    "result": result,
                    "rrf_score": rrf_score,
                    "vector_rank": rank,
                    "vector_score": result.get("score", 0),
                }

        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = result.get("chunk_id")
            if chunk_id:
                rrf_score = bm25_weight / (k + rank)
                if chunk_id in chunk_scores:
                    # Chunk appears in both results - add scores
                    chunk_scores[chunk_id]["rrf_score"] += rrf_score
                    chunk_scores[chunk_id]["bm25_rank"] = rank
                    chunk_scores[chunk_id]["bm25_score"] = result.get("score", 0)
                else:
                    # New chunk from BM25 only
                    chunk_scores[chunk_id] = {
                        "result": result,
                        "rrf_score": rrf_score,
                        "bm25_rank": rank,
                        "bm25_score": result.get("score", 0),
                    }

        # Sort by RRF score
        sorted_results = sorted(
            chunk_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        # Format results
        merged_results = []
        for item in sorted_results:
            result = item["result"].copy()
            result["rrf_score"] = item["rrf_score"]
            result["vector_rank"] = item.get("vector_rank")
            result["bm25_rank"] = item.get("bm25_rank")
            result["vector_score"] = item.get("vector_score")
            result["bm25_score"] = item.get("bm25_score")
            merged_results.append(result)

        return merged_results
