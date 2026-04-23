# MCP Testing Guide

Complete guide to testing all 10 MCP tools exposed by the Indigo Document Intelligence Server.

## Prerequisites

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Verify MCP server is healthy**:
   ```bash
   curl -s http://localhost:8001/health
   # Expected: {"status":"healthy","tools_available":10}
   ```

3. **Authentication**: All requests require Bearer token:
   ```bash
   Authorization: Bearer mcp_secret_key_changeme
   ```

## Tool Testing Commands

### 1. list_documents
List documents with optional filtering and pagination.

**Parameters**:
- `page` (int): Page number (default: 1)
- `page_size` (int): Documents per page (default: 10, max: 100)
- `status` (optional): Filter by status (pending, processing, completed, failed)
- `tags` (optional): Filter by comma-separated tags
- `search` (optional): Search in document names

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_documents",
    "arguments": {
      "page": 1,
      "page_size": 5,
      "status": "completed"
    }
  }'
```

**Expected Output**: JSON with items array, total count, pagination info

---

### 2. search
Hybrid search across all documents using vector similarity + BM25.

**Parameters**:
- `query` (string, required): Search query text
- `limit` (int): Maximum results (default: 10, max: 100)
- `document_ids` (optional): Comma-separated document IDs to filter by
- `use_hybrid` (bool): Use hybrid search (default: true)

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search",
    "arguments": {
      "query": "machine learning",
      "limit": 3,
      "use_hybrid": true
    }
  }'
```

**Expected Output**: JSON with ranked results, scores (RRF, vector, BM25, cross-encoder), provenance (page_number, document_name)

**Performance**:
- First query: ~30s (loads cross-encoder model)
- Cached queries: ~200ms

---

### 3. list_tags
List all unique tags across all documents.

**Parameters**: None

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_tags",
    "arguments": {}
  }'
```

**Expected Output**: JSON with tags array and total count

---

### 4. search_by_tag
Search documents filtered by tags.

**Parameters**:
- `tags` (string, required): Comma-separated tags to search for
- `page` (int): Page number (default: 1)
- `page_size` (int): Documents per page (default: 10, max: 100)

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_by_tag",
    "arguments": {
      "tags": "test,mcp-test",
      "page": 1,
      "page_size": 5
    }
  }'
```

**Expected Output**: JSON with documents matching the tags, pagination info

---

### 5. search_by_document
Semantic search restricted to specific documents only.

**Parameters**:
- `query` (string, required): Search query text
- `document_ids` (string, required): Comma-separated document IDs
- `limit` (int): Maximum results (default: 10, max: 100)
- `use_hybrid` (bool): Use hybrid search (default: true)

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_by_document",
    "arguments": {
      "query": "embeddings",
      "document_ids": "5d9e27fb-aa75-4a2b-b59c-7edd8c1f6a5c",
      "limit": 2
    }
  }'
```

**Expected Output**: JSON with search results from specified documents only

---

### 6. get_document
Retrieve full details of a specific document by ID.

**Parameters**:
- `document_id` (string, required): UUID of the document

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_document",
    "arguments": {
      "document_id": "40c409fa-7652-4e14-9fcc-fedd68e58662"
    }
  }'
```

**Expected Output**: JSON with document details including metadata, tags, chunks

---

### 7. upload_document
Upload a PDF document for processing.

**Parameters**:
- `file_path` (string, required): Local path to the PDF file
- `tags` (optional): Comma-separated tags

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "upload_document",
    "arguments": {
      "file_path": "/app/test_files/sample.pdf",
      "tags": "test,uploaded-via-mcp"
    }
  }'
```

**Expected Output**: JSON with document_id, task_id, upload status

**Note**: File must be accessible from the MCP container filesystem

---

### 8. update_document
Update a document's name and/or tags.

**Parameters**:
- `document_id` (string, required): UUID of the document
- `name` (optional): New document name
- `tags` (optional): New comma-separated tags

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "update_document",
    "arguments": {
      "document_id": "40c409fa-7652-4e14-9fcc-fedd68e58662",
      "name": "updated_name.txt",
      "tags": "updated,modified"
    }
  }'
```

**Expected Output**: JSON with updated document details

---

### 9. delete_document
Delete a document and all associated data (chunks, vectors, tasks).

**Parameters**:
- `document_id` (string, required): UUID of the document to delete

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "delete_document",
    "arguments": {
      "document_id": "ee4db5f0-8266-4d7f-9c26-9ee9f86b7b3b"
    }
  }'
```

**Expected Output**: JSON with deletion confirmation and document_id

**Warning**: This operation is irreversible

---

### 10. get_stats
Get system statistics including document counts, tags, and status breakdown.

**Parameters**: None

**Example**:
```bash
curl -s -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer mcp_secret_key_changeme" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_stats",
    "arguments": {}
  }'
```

**Expected Output**: JSON with:
- `total_documents`: Total document count
- `documents_pending`: Documents in pending status
- `documents_processing`: Documents being processed
- `documents_completed`: Successfully processed documents
- `documents_failed`: Failed documents
- `total_tags`: Number of unique tags
- `tags`: Array of tag names

---

## Testing with Claude Desktop

To use the MCP server with Claude Desktop:

1. **Add to Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
   ```json
   {
     "mcpServers": {
       "indigo": {
         "url": "http://localhost:8001",
         "transport": "streamable-http",
         "headers": {
           "Authorization": "Bearer mcp_secret_key_changeme"
         }
       }
     }
   }
   ```

2. **Restart Claude Desktop**

3. **Test in Claude**:
   - "List all documents in the knowledge base"
   - "Search for 'machine learning concepts'"
   - "Get statistics about the document collection"
   - "Show me documents tagged with 'test'"

## Error Handling

All tools return structured error responses:

```json
{
  "error": true,
  "operation": "search",
  "category": "timeout|not_found|invalid_request|server_error|network_error|unknown_error",
  "type": "ExceptionType",
  "message": "Error details",
  "suggestion": "Actionable suggestion for fixing the issue"
}
```

## Performance Notes

- **Hybrid Search**: Vector + BM25 + RRF + optional cross-encoder reranking
- **First search query**: ~30s (loads cross-encoder model into memory)
- **Subsequent searches**: ~200ms (cached model)
- **Redis caching**: Search results cached with 1800s TTL
- **Recommended limit**: 10-20 results for optimal performance

## Testing Checklist

- [x] list_documents - ✅ Works
- [x] search - ✅ Works (hybrid search with reranking)
- [x] list_tags - ✅ Works
- [x] search_by_tag - ✅ Works
- [x] search_by_document - ✅ Works
- [x] get_document - ✅ Works
- [ ] upload_document - Requires file path accessible to container
- [ ] update_document - Requires existing document ID
- [ ] delete_document - Requires existing document ID
- [x] get_stats - ✅ Works (bug fixed: 2026-04-19)

## Recent Bug Fixes

### 2026-04-19: get_stats AttributeError
- **Issue**: `'list' object has no attribute 'get'` on line 547
- **Cause**: `/api/v1/documents/tags/all` returns list directly, not object with "tags" field
- **Fix**: Changed `tags_data.get("tags", [])` to direct list access
- **File**: `mcp/server.py:544-548`
- **Status**: ✅ Fixed and tested

## Additional Resources

- **Backend API Docs**: http://localhost:8000/docs
- **MCP Health Check**: http://localhost:8001/health
- **Prometheus Metrics**: http://localhost:8000/metrics
- **Qdrant Dashboard**: http://localhost:6333/dashboard
