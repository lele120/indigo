"""
Search API endpoints
"""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.services.search_service import SearchService
from app.services.cache_service import CacheService
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.models.document import Document
from app.core.config import settings

logger = structlog.get_logger()

router = APIRouter()


@router.post("", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    use_cache: bool = Query(True, description="Use cache for search results"),
):
    """
    Hybrid search across documents using vector similarity and BM25

    Args:
    - **query**: Search query text (required)
    - **limit**: Maximum number of results (1-100, default: 10)
    - **document_ids**: Optional list of document IDs to filter by
    - **file_type**: Filter by file type (pdf, docx, excel, csv, text, powerpoint)
    - **author**: Filter by author name (partial match, case-insensitive)
    - **date_from**: Filter documents uploaded after this date (ISO 8601: 2024-01-01T00:00:00)
    - **date_to**: Filter documents uploaded before this date (ISO 8601: 2024-12-31T23:59:59)
    - **use_hybrid**: Use hybrid search (vector + BM25) or vector only (default: true)
    - **vector_weight**: Weight for vector search results (0.0-1.0, default: 0.5)
    - **bm25_weight**: Weight for BM25 search results (0.0-1.0, default: 0.5)
    - **use_cache**: Use Redis cache for results (default: true)

    Search Process:
    1. Vector search using OpenAI embeddings (semantic similarity)
    2. BM25 keyword search (lexical matching)
    3. Reciprocal Rank Fusion (RRF) to merge results
    4. Optional cross-encoder reranking (if ENABLE_RERANKING=true)
    5. Apply filters (file_type, author, dates)

    Returns:
    - Search results ranked by relevance
    - Scores: RRF, vector, BM25, cross-encoder (if enabled)
    - Metadata: document name, page number, text preview

    Example:
    ```json
    {
      "query": "machine learning algorithms",
      "limit": 10,
      "file_type": "pdf",
      "author": "John",
      "date_from": "2024-01-01T00:00:00",
      "use_hybrid": true
    }
    ```
    """
    start_time = time.time()

    logger.info(
        "search_request",
        query=request.query,
        limit=request.limit,
        use_hybrid=request.use_hybrid,
        use_cache=use_cache,
    )

    # Try cache first if enabled
    cache_service = CacheService()
    cached_results = None

    if use_cache:
        cached_results = cache_service.get(
            "search",
            query=request.query,
            limit=request.limit,
            document_ids=request.document_ids,
            file_type=request.file_type,
            author=request.author,
            date_from=request.date_from,
            date_to=request.date_to,
            use_hybrid=request.use_hybrid,
            vector_weight=request.vector_weight,
            bm25_weight=request.bm25_weight,
        )

        if cached_results:
            logger.info("search_cache_hit", query=request.query)
            # Convert cached dict results back to SearchResult objects
            results_list = [SearchResult(**r) for r in cached_results.get("results", [])]
            return SearchResponse(
                query=cached_results["query"],
                results=results_list,
                total=cached_results["total"],
                use_hybrid=cached_results["use_hybrid"],
                search_time_ms=cached_results.get("search_time_ms"),
            )

    # Initialize search service
    search_service = SearchService(db)

    # Perform search
    results = search_service.search(
        query=request.query,
        limit=request.limit,
        document_ids=request.document_ids,
        file_type=request.file_type,
        author=request.author,
        date_from=request.date_from,
        date_to=request.date_to,
        use_hybrid=request.use_hybrid,
        vector_weight=request.vector_weight,
        bm25_weight=request.bm25_weight,
    )

    # Enrich results with document names
    enriched_results = []
    for result in results:
        # Get document name
        doc = db.query(Document).filter(
            Document.id == result["document_id"]
        ).first()

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

    # Calculate search time
    search_time_ms = (time.time() - start_time) * 1000

    logger.info(
        "search_completed",
        query=request.query,
        results_count=len(enriched_results),
        search_time_ms=search_time_ms,
    )

    response = SearchResponse(
        query=request.query,
        results=enriched_results,
        total=len(enriched_results),
        use_hybrid=request.use_hybrid,
        search_time_ms=search_time_ms,
    )

    # Cache results if enabled
    if use_cache:
        cache_service.set(
            "search",
            response.dict(),
            query=request.query,
            limit=request.limit,
            document_ids=request.document_ids,
            file_type=request.file_type,
            author=request.author,
            date_from=request.date_from,
            date_to=request.date_to,
            use_hybrid=request.use_hybrid,
            vector_weight=request.vector_weight,
            bm25_weight=request.bm25_weight,
        )

    return response


@router.get("", response_model=SearchResponse)
def search_documents_get(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    document_ids: Optional[str] = Query(None, description="Comma-separated document IDs"),
    use_hybrid: bool = Query(True, description="Use hybrid search"),
    db: Session = Depends(get_db),
):
    """
    Search documents (GET method for simple queries)

    - **q**: Search query text
    - **limit**: Maximum number of results (default: 10)
    - **document_ids**: Optional comma-separated document IDs
    - **use_hybrid**: Use hybrid search (default: true)
    """
    # Parse document IDs if provided
    doc_ids = None
    if document_ids:
        doc_ids = [did.strip() for did in document_ids.split(",") if did.strip()]

    # Create request
    request = SearchRequest(
        query=q,
        limit=limit,
        document_ids=doc_ids,
        use_hybrid=use_hybrid,
    )

    # Call POST handler
    return search_documents(request, db)
