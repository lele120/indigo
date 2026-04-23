"""
Indigo MCP Server - Document Intelligence Tools

Provides 10 tools for document management and search via MCP protocol.
"""
import os
import json
import uuid
import logging
from typing import Optional, List
import httpx
import structlog
from fastmcp import FastMCP
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

# Initialize FastMCP server
mcp = FastMCP("Indigo Document Intelligence")


# HTTP Client with authentication and retry logic
def get_client() -> httpx.Client:
    """Get authenticated HTTP client with timeout configuration.

    The backend now enforces Bearer auth on /api/v1/*, so every MCP->backend
    request carries the shared MCP_API_KEY as a Bearer token.
    """
    headers = {}
    if MCP_API_KEY:
        headers["Authorization"] = f"Bearer {MCP_API_KEY}"

    return httpx.Client(
        base_url=BACKEND_URL,
        headers=headers,
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def make_backend_request(method: str, endpoint: str, **kwargs):
    """
    Make HTTP request to backend with retry logic for transient failures.

    Args:
        method: HTTP method (get, post, patch, delete)
        endpoint: API endpoint path
        **kwargs: Additional arguments for httpx request

    Returns:
        Response object

    Raises:
        httpx.HTTPError: For non-retryable errors (4xx, 5xx)
    """
    correlation_id = str(uuid.uuid4())
    logger.info(
        "backend_request_start",
        correlation_id=correlation_id,
        method=method.upper(),
        endpoint=endpoint,
    )

    try:
        with get_client() as client:
            response = getattr(client, method)(endpoint, **kwargs)

            logger.info(
                "backend_request_success",
                correlation_id=correlation_id,
                status_code=response.status_code,
            )

            return response

    except httpx.TimeoutException as e:
        logger.warning(
            "backend_request_timeout",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise
    except httpx.HTTPStatusError as e:
        logger.error(
            "backend_request_http_error",
            correlation_id=correlation_id,
            status_code=e.response.status_code,
            error=str(e),
        )
        # Don't retry client errors (4xx) - they won't succeed
        raise
    except httpx.NetworkError as e:
        logger.warning(
            "backend_request_network_error",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise
    except Exception as e:
        logger.error(
            "backend_request_unexpected_error",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise


def format_error_for_llm(error: Exception, operation: str) -> str:
    """
    Format error messages in a way that's helpful for LLMs to understand.

    Args:
        error: The exception that occurred
        operation: Description of what operation failed

    Returns:
        JSON string with structured error information
    """
    error_type = type(error).__name__

    # Categorize errors for LLM
    if isinstance(error, httpx.TimeoutException):
        category = "timeout"
        suggestion = "The backend service is slow to respond. Try again in a moment or reduce the query scope."
    elif isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 404:
            category = "not_found"
            suggestion = "The requested resource does not exist. Verify the ID or name is correct."
        elif error.response.status_code == 400:
            category = "invalid_request"
            suggestion = "The request parameters are invalid. Check the input format and required fields."
        elif error.response.status_code >= 500:
            category = "server_error"
            suggestion = "The backend service encountered an error. Try again in a moment."
        else:
            category = "http_error"
            suggestion = "An HTTP error occurred. Check the error details below."
    elif isinstance(error, httpx.NetworkError):
        category = "network_error"
        suggestion = "Cannot connect to the backend service. The service may be down."
    else:
        category = "unknown_error"
        suggestion = "An unexpected error occurred. Check the error details below."

    return json.dumps({
        "error": True,
        "operation": operation,
        "category": category,
        "type": error_type,
        "message": str(error),
        "suggestion": suggestion,
    }, indent=2)


@mcp.tool()
def list_documents(
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    tags: Optional[str] = None,
    search: Optional[str] = None,
) -> str:
    """
    List documents with optional filtering and pagination.

    Args:
        page: Page number (default: 1)
        page_size: Number of documents per page (default: 10, max: 100)
        status: Filter by status (pending, processing, completed, failed)
        tags: Filter by comma-separated tags
        search: Search in document names

    Returns:
        JSON string with documents list and pagination info
    """
    operation = "list_documents"
    try:
        logger.info(f"{operation}_called", page=page, page_size=page_size)

        params = {
            "page": page,
            "page_size": min(page_size, 100),
        }

        if status:
            params["status"] = status
        if tags:
            params["tags"] = tags
        if search:
            params["search"] = search

        response = make_backend_request("get", "/api/v1/documents", params=params)
        data = response.json()

        logger.info(f"{operation}_success", count=data.get("total", 0))
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error(f"{operation}_failed", error=str(e))
        return format_error_for_llm(e, operation)


@mcp.tool()
def search(
    query: str,
    limit: int = 10,
    document_ids: Optional[str] = None,
    use_hybrid: bool = True,
) -> str:
    """
    Hybrid search across documents using vector similarity and BM25.

    Args:
        query: Search query text (required)
        limit: Maximum number of results (default: 10, max: 100)
        document_ids: Optional comma-separated document IDs to filter by
        use_hybrid: Use hybrid search (vector + BM25) or vector only (default: true)

    Returns:
        JSON string with search results ranked by relevance
    """
    operation = "search"
    try:
        logger.info(f"{operation}_called", query=query, limit=limit)

        payload = {
            "query": query,
            "limit": min(limit, 100),
            "use_hybrid": use_hybrid,
        }

        if document_ids:
            payload["document_ids"] = [did.strip() for did in document_ids.split(",")]

        response = make_backend_request("post", "/api/v1/search", json=payload)
        data = response.json()

        logger.info(f"{operation}_success", results_count=data.get("total", 0))
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error(f"{operation}_failed", error=str(e))
        return format_error_for_llm(e, operation)


@mcp.tool()
def list_tags() -> str:
    """
    List all unique tags that have been assigned to at least one document.

    Returns:
        JSON string with list of all tags
    """
    operation = "list_tags"
    try:
        logger.info(f"{operation}_called")

        response = make_backend_request("get", "/api/v1/documents/tags/all")
        tags_data = response.json()

        # Extract just tag names for cleaner response
        tags = [tag.get("name") for tag in tags_data] if isinstance(tags_data, list) else []

        result = {
            "tags": tags,
            "total": len(tags),
        }

        logger.info(f"{operation}_success", count=len(tags))
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"{operation}_failed", error=str(e))
        return format_error_for_llm(e, operation)


@mcp.tool()
def search_by_tag(
    query: str,
    tags: List[str],
    match_all: bool = False,
    limit: int = 10,
    use_hybrid: bool = True,
) -> str:
    """
    Perform semantic search restricted to documents that carry one or more of the given tags.

    Use this when the agent needs to scope a question to a domain (e.g. only
    "compliance" docs, or docs tagged both "compliance" AND "privacy").

    Args:
        query: Search query text (required).
        tags: List of tag names to filter by (at least one required).
        match_all: If true, only documents tagged with ALL listed tags are searched.
                   If false (default), documents with ANY of the tags are searched.
        limit: Maximum results to return (default 10, max 100).
        use_hybrid: Hybrid vector + BM25 retrieval with reranking (default true).

    Returns:
        JSON string with ranked search results (same shape as `search`), plus a
        `_filter` block reporting the resolved document set size.
    """
    try:
        logger.info("search_by_tag_called", query=query, tags=tags, match_all=match_all)

        if not tags:
            return format_error_for_llm(
                ValueError("at least one tag is required"),
                "search_by_tag",
            )

        # Resolve each tag -> set of document IDs via the backend listing.
        doc_id_sets: List[set] = []
        for tag in tags:
            resp = make_backend_request(
                "get",
                "/api/v1/documents",
                params={"tag": tag, "page_size": 100},
            )
            items = resp.json().get("items", [])
            doc_id_sets.append({d["id"] for d in items})

        if match_all:
            matching_ids = set.intersection(*doc_id_sets) if doc_id_sets else set()
        else:
            matching_ids = set.union(*doc_id_sets) if doc_id_sets else set()

        if not matching_ids:
            return json.dumps(
                {
                    "query": query,
                    "results": [],
                    "total": 0,
                    "use_hybrid": use_hybrid,
                    "_filter": {"tags": tags, "match_all": match_all, "matching_doc_count": 0},
                    "note": f"No documents match tags {tags} (match_all={match_all}).",
                },
                indent=2,
            )

        payload = {
            "query": query,
            "limit": min(limit, 100),
            "use_hybrid": use_hybrid,
            "document_ids": list(matching_ids),
        }
        resp = make_backend_request("post", "/api/v1/search", json=payload)
        data = resp.json()
        data["_filter"] = {
            "tags": tags,
            "match_all": match_all,
            "matching_doc_count": len(matching_ids),
        }

        logger.info("search_by_tag_success", results=data.get("total", 0), doc_count=len(matching_ids))
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error("search_by_tag_failed", error=str(e))
        return format_error_for_llm(e, "search_by_tag")


@mcp.tool()
def search_by_document(
    query: str,
    documents: List[str],
    limit: int = 10,
    use_hybrid: bool = True,
) -> str:
    """
    Perform semantic search restricted to one or more specific documents.

    Accepts a mix of document UUIDs and document names/filenames. Names are
    resolved to UUIDs against the current document set; unknown names are
    dropped with a warning in the response.

    Args:
        query: Search query text (required).
        documents: List of document identifiers — each item may be a UUID or a
                   document name (e.g. "nist-cybersecurity-framework-1.1.pdf").
                   At least one required.
        limit: Maximum results (default 10, max 100).
        use_hybrid: Hybrid vector + BM25 retrieval with reranking (default true).

    Returns:
        JSON string with ranked search results scoped to the resolved documents.
    """
    try:
        logger.info("search_by_document_called", query=query, documents=documents)

        if not documents:
            return format_error_for_llm(
                ValueError("at least one document is required"),
                "search_by_document",
            )

        import re
        uuid_pat = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        resolved_ids: List[str] = []
        unresolved: List[str] = []
        name_candidates: List[str] = []
        for d in documents:
            d = (d or "").strip()
            if not d:
                continue
            if uuid_pat.match(d):
                resolved_ids.append(d)
            else:
                name_candidates.append(d)

        if name_candidates:
            # Single listing call, then look up each name locally.
            resp = make_backend_request(
                "get", "/api/v1/documents", params={"page_size": 100}
            )
            items = resp.json().get("items", [])
            name_to_id = {d["name"]: d["id"] for d in items}
            for name in name_candidates:
                if name in name_to_id:
                    resolved_ids.append(name_to_id[name])
                else:
                    unresolved.append(name)

        if not resolved_ids:
            return json.dumps(
                {
                    "query": query,
                    "results": [],
                    "total": 0,
                    "use_hybrid": use_hybrid,
                    "note": f"No documents matched identifiers {documents}.",
                    "unresolved": unresolved,
                },
                indent=2,
            )

        payload = {
            "query": query,
            "limit": min(limit, 100),
            "use_hybrid": use_hybrid,
            "document_ids": resolved_ids,
        }
        resp = make_backend_request("post", "/api/v1/search", json=payload)
        data = resp.json()
        data["_filter"] = {
            "resolved_document_count": len(resolved_ids),
            "unresolved_names": unresolved,
        }

        logger.info(
            "search_by_document_success",
            results=data.get("total", 0),
            resolved=len(resolved_ids),
        )
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error("search_by_document_failed", error=str(e))
        return format_error_for_llm(e, "search_by_document")


@mcp.tool()
def get_document(document_id: str, format: Optional[str] = None) -> str:
    """
    Get a document by ID.

    Args:
        document_id: UUID of the document
        format: If provided, returns full reconstructed content in the given
            format: "text" (markdown stripped), "markdown" (preserves headings
            and tables, best for LLMs), or "json" (structured list of chunks
            with chunk_index, page_number, section_heading, text).
            If omitted, only metadata is returned (fast, no chunk load).

    Returns:
        JSON string with document metadata, or metadata + full content when
        format is specified.
    """
    try:
        logger.info("get_document_called", document_id=document_id, format=format)

        if format is None:
            response = make_backend_request(
                "get", f"/api/v1/documents/{document_id}"
            )
        else:
            if format not in ("text", "markdown", "json"):
                return json.dumps({
                    "error": f"Invalid format: {format!r}. Must be one of: text, markdown, json"
                })
            response = make_backend_request(
                "get",
                f"/api/v1/documents/{document_id}/content",
                params={"format": format},
            )

        data = response.json()
        logger.info("get_document_success", document_id=document_id, format=format)
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error("get_document_failed", document_id=document_id, error=str(e))
        return format_error_for_llm(e, "get_document")


@mcp.tool()
def upload_document(
    file_path: str,
    tags: Optional[str] = None,
) -> str:
    """
    Upload a PDF document for processing.

    Args:
        file_path: Local path to the PDF file
        tags: Optional comma-separated tags

    Returns:
        JSON string with document_id, task_id, and upload status
    """
    try:
        logger.info("upload_document_called", file_path=file_path)

        # Check if file exists
        if not os.path.exists(file_path):
            return json.dumps({"error": f"File not found: {file_path}"})

        # Prepare multipart form data
        files = {
            "file": (os.path.basename(file_path), open(file_path, "rb"), "application/pdf")
        }

        data = {}
        if tags:
            data["tags"] = tags

        response = make_backend_request(
            "post",
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )
        result = response.json()

        logger.info("upload_document_success", document_id=result.get("document_id"))
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"upload_document_failed", error=str(e))
        return format_error_for_llm(e, "upload_document")


@mcp.tool()
def update_document(
    document_id: str,
    name: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """
    Update a document's name and/or tags.

    Args:
        document_id: UUID of the document
        name: New document name (optional)
        tags: New comma-separated tags (optional)

    Returns:
        JSON string with updated document details
    """
    try:
        logger.info("update_document_called", document_id=document_id)

        payload = {}
        if name:
            payload["name"] = name
        if tags:
            payload["tags"] = [tag.strip() for tag in tags.split(",")]

        if not payload:
            return json.dumps({"error": "No updates provided. Specify name or tags."})

        response = make_backend_request(
            "patch",
            f"/api/v1/documents/{document_id}",
            json=payload,
        )
        data = response.json()

        logger.info("update_document_success", document_id=document_id)
        return json.dumps(data, indent=2)

    except Exception as e:
        logger.error(f"update_document_failed", document_id=document_id, error=str(e))
        return format_error_for_llm(e, "update_document")


@mcp.tool()
def delete_document(document_id: str) -> str:
    """
    Delete a document and all associated data (chunks, vectors, tasks).

    Args:
        document_id: UUID of the document to delete

    Returns:
        JSON string with deletion confirmation
    """
    try:
        logger.info("delete_document_called", document_id=document_id)

        response = make_backend_request("delete", f"/api/v1/documents/{document_id}")

        logger.info("delete_document_success", document_id=document_id)
        return json.dumps({
            "message": f"Document {document_id} deleted successfully",
            "document_id": document_id,
        }, indent=2)

    except Exception as e:
        logger.error(f"delete_document_failed", document_id=document_id, error=str(e))
        return format_error_for_llm(e, "delete_document")


@mcp.tool()
def get_stats() -> str:
    """
    Get system statistics including document counts, tags, and collection info.

    Returns:
        JSON string with system statistics
    """
    operation = "get_stats"
    try:
        logger.info(f"{operation}_called")

        # Single backend call to the authoritative stats endpoint — the
        # previous implementation looped over /documents?status=X, but
        # ListDocumentsRequest has no `status` filter, so every call
        # returned the full total and all counters collapsed to the same
        # number.
        stats_resp = make_backend_request("get", "/api/v1/documents/stats")
        s = stats_resp.json()

        stats = {
            "total_documents": s.get("total", 0),
            "documents_pending": s.get("pending", 0),
            "documents_processing": s.get("processing", 0),
            "documents_completed": s.get("completed", 0),
            "documents_failed": s.get("failed", 0),
            "tags": s.get("tags", []),
            "total_tags": len(s.get("tags", [])),
        }

        logger.info(f"{operation}_success", total_documents=stats["total_documents"])
        return json.dumps(stats, indent=2)

    except Exception as e:
        logger.error(f"{operation}_failed", error=str(e))
        return format_error_for_llm(e, operation)


# Run the MCP server
if __name__ == "__main__":
    logger.info("starting_mcp_server", backend_url=BACKEND_URL)
    mcp.run()
