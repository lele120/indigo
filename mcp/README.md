# Indigo MCP Server

Model Context Protocol (MCP) server for Indigo Document Intelligence, providing **10 tools** for document management and semantic search via **Streamable HTTP** transport.

## 🛠️ Available Tools

### 1. `list_documents`
List documents with optional filtering and pagination.

**Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 10, max: 100) - Documents per page
- `status` (str, optional) - Filter by status: pending, processing, completed, failed
- `tags` (str, optional) - Filter by comma-separated tags
- `search` (str, optional) - Search in document names

**Returns:** JSON with documents list and pagination info

**Example:**
```python
list_documents(page=1, page_size=20, status="completed", tags="research,ai")
```

---

### 2. `search`
Hybrid search across documents using vector similarity and BM25.

**Parameters:**
- `query` (str, required) - Search query text
- `limit` (int, default: 10, max: 100) - Maximum results
- `document_ids` (str, optional) - Comma-separated document IDs to filter by
- `use_hybrid` (bool, default: true) - Use hybrid search (vector + BM25) or vector only

**Returns:** JSON with search results ranked by relevance (RRF scores)

**Example:**
```python
search(query="machine learning embeddings", limit=5, use_hybrid=True)
```

---

### 3. `list_tags`
List all unique tags that have been assigned to at least one document.

**Parameters:** None

**Returns:** JSON with list of all tags and count

**Example:**
```python
list_tags()
# Returns: {"tags": ["ai", "research", "ml"], "total": 3}
```

---

### 4. `search_by_tag`
Search documents by tags.

**Parameters:**
- `tags` (str, required) - Comma-separated tags to search for
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 10, max: 100) - Documents per page

**Returns:** JSON with documents matching the tags

**Example:**
```python
search_by_tag(tags="ai,research", page=1, page_size=10)
```

---

### 5. `search_by_document`
Perform semantic search restricted to one or more specific documents.

**Parameters:**
- `query` (str, required) - Search query text
- `document_ids` (str, required) - Comma-separated document IDs or names to search within
- `limit` (int, default: 10, max: 100) - Maximum results
- `use_hybrid` (bool, default: true) - Use hybrid search (vector + BM25) or vector only

**Returns:** JSON with search results from specified documents only

**Example:**
```python
search_by_document(
    query="neural networks",
    document_ids="1dc64b57-6a27-4b34-8fdd-819e215772a8,abc123...",
    limit=5
)
```

---

### 6. `get_document`
Get a specific document by ID.

**Parameters:**
- `document_id` (str, required) - UUID of the document

**Returns:** JSON with document details including chunks and metadata

**Example:**
```python
get_document(document_id="1dc64b57-6a27-4b34-8fdd-819e215772a8")
```

---

### 7. `upload_document`
Upload a PDF document for processing.

**Parameters:**
- `file_path` (str, required) - Local path to the PDF file
- `tags` (str, optional) - Comma-separated tags

**Returns:** JSON with document_id, task_id, and upload status

**Example:**
```python
upload_document(file_path="/path/to/document.pdf", tags="research,ai,2024")
```

---

### 8. `update_document`
Update a document's name and/or tags.

**Parameters:**
- `document_id` (str, required) - UUID of the document
- `name` (str, optional) - New document name
- `tags` (str, optional) - New comma-separated tags

**Returns:** JSON with updated document details

**Example:**
```python
update_document(
    document_id="1dc64b57-6a27-4b34-8fdd-819e215772a8",
    name="Updated Document Name",
    tags="new,tags,here"
)
```

---

### 9. `delete_document`
Delete a document and all associated data (chunks, vectors, tasks).

**Parameters:**
- `document_id` (str, required) - UUID of the document to delete

**Returns:** JSON with deletion confirmation

**Example:**
```python
delete_document(document_id="1dc64b57-6a27-4b34-8fdd-819e215772a8")
```

---

### 10. `get_stats`
Get system statistics including document counts, tags, and collection info.

**Parameters:** None

**Returns:** JSON with system statistics:
- `total_documents` - Total number of documents
- `documents_pending` - Count of pending documents
- `documents_processing` - Count of processing documents
- `documents_completed` - Count of completed documents
- `documents_failed` - Count of failed documents
- `total_tags` - Total number of tags
- `tags` - List of all tags

**Example:**
```python
get_stats()
```

---

## 🚀 Usage

### HTTP Transport (Production)

The MCP server runs on **port 8001** with Streamable HTTP transport:

```bash
# Set environment variables
export BACKEND_URL=http://localhost:8000
export MCP_API_KEY=your_api_key_here
export PORT=8001

# Run the MCP server
python main.py
```

Server will start on `http://0.0.0.0:8001` with the following endpoints:

- **GET** `/` - Server information
- **GET** `/health` - Health check (no auth required)
- **GET** `/tools` - List all available tools (requires auth)
- **POST** `/call-tool` - Execute a tool (requires auth)
- **POST** `/call-tool-stream` - Execute a tool with SSE streaming (requires auth)

### Docker (Recommended)

```bash
# Build the MCP server
docker-compose build mcp-server

# Run the MCP server
docker-compose up -d mcp-server

# Check health
curl http://localhost:8001/health

# View logs
docker-compose logs -f mcp-server
```

### Testing with curl

```bash
# List all available tools
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8001/tools

# Call a tool
curl -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_tags",
    "arguments": {}
  }'

# Stream a tool call (SSE)
curl -N -X POST http://localhost:8001/call-tool-stream \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search",
    "arguments": {
      "query": "machine learning",
      "limit": 5
    }
  }'
```

## 🔐 Authentication

The MCP server uses **Bearer token authentication** via the `Authorization` header:

```bash
Authorization: Bearer <MCP_API_KEY>
```

- Set `MCP_API_KEY` in your `.env` file
- All tool endpoints require authentication
- Health endpoint (`/health`) does not require auth

## 📦 Dependencies

- **fastmcp** >=0.3.0 - FastMCP framework for tool definitions
- **fastapi** >=0.110.0 - HTTP server framework
- **uvicorn** >=0.27.0 - ASGI server
- **httpx** >=0.27.0 - HTTP client for backend API calls
- **structlog** >=24.1.0 - Structured logging
- **pydantic** >=2.0.0 - Data validation

## 🔄 MCP Protocol

This server implements the Model Context Protocol (MCP) using **Streamable HTTP** transport:

- **Transport**: Streamable HTTP (SSE for streaming)
- **Port**: 8001
- **Authentication**: Bearer token (MCP_API_KEY)
- **Protocol version**: MCP 1.0
- **Features**: Tool calling, SSE streaming, API key auth

AI assistants and MCP clients can connect to this server to interact with the Indigo document intelligence system.

## 📝 Notes

- All tools return JSON-formatted strings
- The server automatically handles authentication with the backend API
- Tools make synchronous HTTP calls to the backend REST API
- Error handling is built into each tool
- Structured logging provides detailed execution traces

## 🐛 Troubleshooting

### Connection Issues
```bash
# Check MCP server is running
curl http://localhost:8001/health

# Check backend is running
curl http://localhost:8000/health

# Check MCP server logs
docker-compose logs mcp-server --tail 50
```

### Authentication Errors
```bash
# Verify API key is set
echo $MCP_API_KEY

# Test authentication
curl -H "Authorization: Bearer $MCP_API_KEY" \
  http://localhost:8001/tools

# Should return list of tools, not 401 Unauthorized
```

### Tool Execution Errors
```bash
# Check tool execution logs
docker-compose logs mcp-server --follow

# Test a simple tool
curl -X POST http://localhost:8001/call-tool \
  -H "Authorization: Bearer $MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "list_tags", "arguments": {}}'
```

## 📖 Example Workflow

```python
# 1. Upload a document
result = upload_document(
    file_path="/documents/research_paper.pdf",
    tags="ai,research,2024"
)
document_id = json.loads(result)["document_id"]

# 2. Wait for processing (check status)
doc = get_document(document_id=document_id)

# 3. Search the document
results = search(
    query="neural networks and transformers",
    limit=5,
    use_hybrid=True
)

# 4. Get system statistics
stats = get_stats()

# 5. Update document metadata
update_document(
    document_id=document_id,
    tags="ai,research,2024,transformers"
)
```

## 🎯 Integration with Claude

When using with Claude Desktop or Claude CLI, the MCP server provides these tools automatically. Claude can use them to:
- Search through your document collection
- Upload and manage documents
- Get statistics and insights
- Update document metadata
- Delete outdated documents

---

## 📚 Additional Resources

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Indigo Backend API Docs](http://localhost:8000/docs)
- [Main Project README](../README.md)

---

**Version:** 1.0.0
**Protocol:** MCP (Streamable HTTP)
**Transport:** HTTP/SSE on port 8001
**Backend API:** Indigo REST API v1
**Authentication:** Bearer token (MCP_API_KEY)
