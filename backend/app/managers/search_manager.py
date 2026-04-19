"""
Search Manager - Orchestrates hybrid search operations

Business logic:
- Cache management
- Reranking coordination
- Document metadata enrichment
- Timing metrics

Uses SearchService for data access (Qdrant, BM25, DB queries).
"""
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from app.models.document import Document
from app.schemas.requests import SearchDocumentsRequest
from app.schemas.search import SearchResponse, SearchResult
from app.services.search_service import SearchService
from app.services.cache_service import CacheService
from app.core.config import settings

logger = structlog.get_logger()


class SearchManager:
    """Manager for search operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.search_service = SearchService(db)  # Now fully async
        self.cache_service = CacheService()

    async def search(
        self,
        request: SearchDocumentsRequest,
        use_cache: bool = True
    ) -> SearchResponse:
        """
        Perform hybrid search with caching

        Steps:
        1. Check cache
        2. Perform vector + BM25 search
        3. Apply RRF
        4. Rerank if enabled
        5. Enrich with document metadata
        6. Cache results

        Args:
            request: Search parameters
            use_cache: Whether to use Redis cache

        Returns:
            SearchResponse with ranked results
        """
        import time
        start_time = time.time()

        logger.info(
            "search_request",
            query=request.query,
            limit=request.limit,
            use_hybrid=request.use_hybrid
        )

        # Check cache
        if use_cache:
            cached = self.cache_service.get(
                "search",
                query=request.query,
                limit=request.limit,
                document_ids=request.document_ids,
                file_type=request.file_type,
                use_hybrid=request.use_hybrid
            )
            if cached:
                logger.info("search_cache_hit", query=request.query)
                # Convert cached dicts to SearchResult objects
                results = [SearchResult(**r) for r in cached.get("results", [])]
                return SearchResponse(
                    query=cached["query"],
                    results=results,
                    total=cached["total"],
                    use_hybrid=cached["use_hybrid"],
                    search_time_ms=cached.get("search_time_ms")
                )

        # Perform search via async service
        raw_results = await self.search_service.search(
            query=request.query,
            limit=request.limit * 2 if settings.ENABLE_RERANKING else request.limit,  # Get more for reranking
            document_ids=request.document_ids,
            file_type=request.file_type,
            author=request.author,
            date_from=request.date_from,
            date_to=request.date_to,
            use_hybrid=request.use_hybrid,
            vector_weight=request.vector_weight,
            bm25_weight=request.bm25_weight,
        )

        # Apply cross-encoder reranking if enabled (business logic)
        if settings.ENABLE_RERANKING and raw_results:
            logger.info("applying_reranking", query=request.query, num_results=len(raw_results))
            from app.services.reranking_service import RerankingService
            reranking_service = RerankingService()
            raw_results = reranking_service.rerank(
                query=request.query,
                results=raw_results,
                top_k=request.limit
            )

        # Enrich with document names (async)
        enriched_results = []
        for result in raw_results:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == result["document_id"])
            )
            doc = doc_result.scalar_one_or_none()

            search_result = SearchResult(
                chunk_id=result.get("chunk_id", ""),
                document_id=result.get("document_id", ""),
                document_name=doc.name if doc else None,
                text=result.get("text", ""),
                text_preview=result.get("text_preview", ""),
                page_number=result.get("page_number"),
                chunk_type=result.get("chunk_type", "text"),
                rrf_score=result.get("rrf_score"),
                cross_encoder_score=result.get("cross_encoder_score"),
                vector_score=result.get("vector_score"),
                bm25_score=result.get("bm25_score"),
                vector_rank=result.get("vector_rank"),
                bm25_rank=result.get("bm25_rank"),
            )
            enriched_results.append(search_result)

        search_time_ms = (time.time() - start_time) * 1000

        response = SearchResponse(
            query=request.query,
            results=enriched_results,
            total=len(enriched_results),
            use_hybrid=request.use_hybrid,
            search_time_ms=search_time_ms,
        )

        # Cache results
        if use_cache:
            self.cache_service.set(
                "search",
                response.model_dump(),  # Pydantic v2 compatibility
                query=request.query,
                limit=request.limit,
                document_ids=request.document_ids,
                file_type=request.file_type,
                use_hybrid=request.use_hybrid
            )

        logger.info(
            "search_completed",
            query=request.query,
            results=len(enriched_results),
            time_ms=search_time_ms
        )

        return response
