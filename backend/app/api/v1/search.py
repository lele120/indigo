"""
Search API endpoints - Clean 3-layer architecture

Architecture:
- Controllers: HTTP handling, Pydantic validation
- Managers: Business logic orchestration (cache, enrichment, timing)
- Services: Pure data access (Qdrant, BM25)

Features:
- Pydantic request validation (automatic)
- Manager pattern (business logic separation)
- Async/await throughout
- Centralized exception handling
"""
from typing import Optional
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_async import get_async_db
from app.managers.search_manager import SearchManager
from app.schemas.requests import SearchDocumentsRequest
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter()


# Dependency to get manager
def get_search_manager(db: AsyncSession = Depends(get_async_db)) -> SearchManager:
    return SearchManager(db)


@router.post("", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest = Body(...),
    use_cache: bool = Query(True, description="Use cache for search results"),
    manager: SearchManager = Depends(get_search_manager),
):
    """
    Hybrid search across documents using vector similarity and BM25

    **New Features**:
    - Automatic request validation via Pydantic
    - Manager pattern for business logic
    - Full async/await stack
    - Centralized exception handling

    **Request Parameters** (auto-validated):
    - query: Search query text (required, 1-1000 chars)
    - limit: Maximum results (1-100, default: 10)
    - document_ids: Filter by specific document IDs (optional)
    - file_type: Filter by file type (optional)
    - author: Filter by author name (optional, partial match)
    - date_from: Filter documents after this date (optional)
    - date_to: Filter documents before this date (optional)
    - use_hybrid: Use hybrid search (default: true)
    - vector_weight: Weight for vector search (0.0-1.0, default: 0.5)
    - bm25_weight: Weight for BM25 search (0.0-1.0, default: 0.5)
    - use_cache: Use Redis cache for results (default: true)

    **Search Process** (handled by manager):
    1. Check cache for existing results
    2. Vector search using OpenAI embeddings (semantic similarity)
    3. BM25 keyword search (lexical matching)
    4. Reciprocal Rank Fusion (RRF) to merge results
    5. Optional cross-encoder reranking (if ENABLE_RERANKING=true)
    6. Enrich with document metadata (names, etc.)
    7. Apply filters (file_type, author, dates)
    8. Cache results for future queries

    **Returns**:
    - Search results ranked by relevance
    - Scores: RRF, vector, BM25, cross-encoder (if enabled)
    - Metadata: document name, page number, text preview
    - Search timing metrics

    **Example**:
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
    # Convert SearchRequest to SearchDocumentsRequest
    search_req = SearchDocumentsRequest(
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
    return await manager.search(search_req, use_cache=use_cache)


@router.get("", response_model=SearchResponse)
async def search_documents_get(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    document_ids: Optional[str] = Query(None, description="Comma-separated document IDs"),
    use_hybrid: bool = Query(True, description="Use hybrid search"),
    manager: SearchManager = Depends(get_search_manager),
):
    """
    Search documents (GET method for simple queries)

    **Simplified search interface** for quick queries without POST body.

    **Parameters**:
    - q: Search query text
    - limit: Maximum number of results (default: 10)
    - document_ids: Optional comma-separated document IDs
    - use_hybrid: Use hybrid search (default: true)
    """
    # Parse document IDs if provided
    doc_ids = None
    if document_ids:
        doc_ids = [did.strip() for did in document_ids.split(",") if did.strip()]

    # Create request object
    request = SearchDocumentsRequest(
        query=q,
        limit=limit,
        document_ids=doc_ids,
        use_hybrid=use_hybrid,
    )

    # Delegate to manager
    return await manager.search(request, use_cache=True)
