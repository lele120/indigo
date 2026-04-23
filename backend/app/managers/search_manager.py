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

from uuid import UUID

from app.models.document import Document, Chunk
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

        # Perform search via async service. When reranking is on, fetch a
        # capped pool of candidates — on CPU the cross-encoder costs
        # ~700ms per candidate, so 6 is the sweet spot between recall and
        # latency for a demo environment.
        rerank_pool = min(max(request.limit * 2, request.limit), 6)
        raw_results = await self.search_service.search(
            query=request.query,
            limit=rerank_pool if settings.ENABLE_RERANKING else request.limit,
            document_ids=request.document_ids,
            file_type=request.file_type,
            author=request.author,
            date_from=request.date_from,
            date_to=request.date_to,
            use_hybrid=request.use_hybrid,
            vector_weight=request.vector_weight,
            bm25_weight=request.bm25_weight,
        )

        # Apply cross-encoder reranking if enabled (business logic).
        # The underlying model.predict is CPU-bound; run in the default
        # executor so it doesn't block the asyncio loop.
        if settings.ENABLE_RERANKING and raw_results:
            import asyncio
            logger.info("applying_reranking", query=request.query, num_results=len(raw_results))
            from app.services.reranking_service import RerankingService
            reranking_service = RerankingService()
            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(
                None,
                lambda: reranking_service.rerank(
                    query=request.query,
                    results=raw_results,
                    top_k=request.limit,
                ),
            )

        # Batch-enrich with document names and missing chunk metadata in a
        # single round-trip each, instead of N+1 queries per result.
        enriched_results = await self._build_enriched_results(raw_results)

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

    async def _build_enriched_results(self, raw_results: List[Dict]) -> List[SearchResult]:
        """Attach document names and fill missing chunk metadata in two batched queries.

        Qdrant payloads written before the schema change may lack chunk_index /
        section_heading. We backfill them from PostgreSQL once per search so
        the UI shows correct provenance even for pre-fix data.
        """
        if not raw_results:
            return []

        document_ids = {r["document_id"] for r in raw_results if r.get("document_id")}
        chunk_ids_needing_meta = [
            r["chunk_id"]
            for r in raw_results
            if r.get("chunk_id")
            and (r.get("chunk_index") is None or r.get("section_heading") is None)
        ]

        doc_name_by_id: Dict[str, str] = {}
        if document_ids:
            doc_rows = await self.db.execute(
                select(Document.id, Document.name).where(
                    Document.id.in_([UUID(d) for d in document_ids])
                )
            )
            doc_name_by_id = {str(row[0]): row[1] for row in doc_rows.all()}

        chunk_meta_by_id: Dict[str, Dict] = {}
        if chunk_ids_needing_meta:
            chunk_rows = await self.db.execute(
                select(Chunk.id, Chunk.chunk_index, Chunk.section_heading).where(
                    Chunk.id.in_([UUID(c) for c in chunk_ids_needing_meta])
                )
            )
            chunk_meta_by_id = {
                str(row[0]): {"chunk_index": row[1], "section_heading": row[2]}
                for row in chunk_rows.all()
            }

        enriched: List[SearchResult] = []
        for result in raw_results:
            chunk_id = result.get("chunk_id", "")
            meta = chunk_meta_by_id.get(chunk_id, {})
            enriched.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=result.get("document_id", ""),
                    document_name=doc_name_by_id.get(result.get("document_id", "")),
                    text=result.get("text", ""),
                    text_preview=result.get("text_preview", ""),
                    page_number=result.get("page_number"),
                    chunk_index=result.get("chunk_index") if result.get("chunk_index") is not None else meta.get("chunk_index"),
                    section_heading=result.get("section_heading") or meta.get("section_heading"),
                    chunk_type=result.get("chunk_type", "text"),
                    rrf_score=result.get("rrf_score"),
                    cross_encoder_score=result.get("cross_encoder_score"),
                    vector_score=result.get("vector_score"),
                    bm25_score=result.get("bm25_score"),
                    vector_rank=result.get("vector_rank"),
                    bm25_rank=result.get("bm25_rank"),
                )
            )
        return enriched
