# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Document Intelligence Server** - A RAG (Retrieval-Augmented Generation) system with MCP (Model Context Protocol) server for semantic search across internal documents. Built for a financial services company to enable natural language queries across compliance policies, manuals, and internal documentation.

## Architecture

The system consists of **8 containerized services** orchestrated via Docker Compose:

1. **Backend (FastAPI)**: REST API for document management, validation, task queuing
2. **Celery Worker**: Async document processing (parsing, chunking, embedding, storage)
3. **MCP Server (FastMCP)**: Exposes **8 tools** via Streamable HTTP for semantic search
4. **Frontend (React + Vite + Tailwind + Zustand)**: Upload interface with progress tracking
5. **PostgreSQL**: Metadata storage (documents, tags, chunks, upload_tasks)
6. **Redis**: Cache + Celery broker + task results
7. **Qdrant**: Vector store for embeddings (1536-dim)
8. **Prometheus**: Metrics collection and monitoring

**Key Data Flow (Async)**:
1. Frontend uploads → Backend validates → Enqueues Celery task → Returns task_id
2. Celery Worker: PDF → **PyMuPDF4LLM (Markdown)** → LangChain chunking (1000 tokens, 200 overlap) → Batch OpenAI embeddings → Qdrant + PostgreSQL
3. Frontend polls `/api/documents/upload/{task_id}/status` for progress
4. MCP Server: **Hybrid search** (vector + BM25 w/ Markdown stripping + RRF + **cross-encoder reranking**) → Returns Markdown chunks with provenance

## Development Commands

### Running the Application

```bash
# Start all services
docker-compose up -d

# Start with rebuild
docker-compose up --build

# View logs
docker-compose logs -f [backend|mcp-server|frontend|qdrant]

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Backend Development

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run development server (outside Docker)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (when implemented)
pytest tests/
```

### MCP Server Development

```bash
cd mcp

# Install dependencies
pip install -r requirements.txt

# Run MCP server
uvicorn server:app --host 0.0.0.0 --port 8001
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Core Technical Decisions

### PDF Extraction with PyMuPDF4LLM

**Extraction Method**: PyMuPDF4LLM for Markdown-based document processing
- **Markdown output**: Documents extracted as Markdown for optimal LLM consumption
- **Structure preservation**: Headers, tables, lists maintain semantic structure
- **Multi-column handling**: Automatic reading order detection for complex layouts
- **Performance**: ~5 seconds for 9-page PDF (vs 38s for IBM Docling)
- **Table formatting**: Tables preserved as Markdown tables (`| col1 | col2 |`)
- **Heading extraction**: Explicit Markdown headers (`#`, `##`, `###`) replace font-size heuristics

**Benefits for RAG**:
- LLMs are trained on Markdown → better comprehension
- Section headings are explicit, improving chunk provenance
- Tables remain structured, enabling accurate financial data extraction
- BM25 search strips Markdown syntax for clean keyword matching

### Chunking Strategy

**Text**: LangChain RecursiveCharacterTextSplitter with Markdown-aware splitting:
- 1000 tokens per chunk (configurable via `CHUNK_SIZE`)
- 200 token overlap (20%) to prevent context loss
- Split on natural boundaries: `\n\n` (paragraphs) → `\n` (lines) → `. ` (sentences) → ` ` (words)
- Token counting uses `cl100k_base` (OpenAI GPT-3.5/4 tokenizer)

**Section Heading Detection**:
- Primary: Extract from Markdown headers (`^#{1,6}\s+(.+)$` regex)
- Fallback: Match headings from page metadata (PyMuPDF4LLM TOC items)
- Each chunk stores `section_heading` for provenance

**BM25 Indexing**:
- Markdown syntax stripped before indexing: `strip_markdown_syntax()` removes `#`, `**`, `*`, `|`, `[]()`
- Tokenization: Regex `\b\w+\b` extracts alphanumeric words only
- Prevents Markdown symbols from polluting BM25 scores

**Tables & Images** (future enhancement):
- Tables: Currently embedded in Markdown chunks
- Images: PyMuPDF4LLM supports image extraction (disabled with `write_images=False`)
- OCR: PaddleOCR available for scanned PDFs (not yet integrated)

### Deduplication

Documents are deduplicated using `(filename, SHA256_hash)` as composite key:
- Existing documents with same name+hash trigger UPDATE (re-ingestion)
- New documents INSERT new record
- Qdrant uses `document_id + chunk_index` as point ID for upsert safety

### Enterprise Backend Architecture (2026-04-19 Update)

The backend follows a **clean 3-layer architecture** with **5 enterprise patterns**:

#### Three-Layer Architecture

1. **Controllers (HTTP Layer)** - backend/app/api/v1/*.py
   - Thin (5-10 lines per endpoint)
   - Pydantic validation via `Depends()`
   - Delegates all logic to managers
   - Example: `documents.py`, `search.py`

2. **Managers (Business Logic)** - backend/app/managers/*.py
   - Orchestrates services
   - Enforces business rules
   - Handles transactions with `@transactional` decorator
   - Example: `DocumentManager`, `UploadManager`, `SearchManager`, `TagManager`

3. **Services (Data Access)** - backend/app/services/*.py
   - Pure async operations with `AsyncSession`
   - No business logic
   - Reusable across managers
   - Example: `DocumentService`, `TagService`, `UploadTaskService`, `SearchService`

#### Enterprise Patterns

1. **Pydantic Request Validation** - backend/app/schemas/requests.py
   - 6 request schemas with field validators
   - Automatic validation at API boundary
   - Example: `UploadDocumentRequest`, `SearchDocumentsRequest`, `ListDocumentsRequest`

2. **Manager Pattern** - backend/app/managers/
   - Business logic extracted from controllers
   - 4 managers: Document (118 lines), Upload (254 lines), Search (162 lines), Tag (88 lines)
   - Controllers reduced 80% (220 → 40 lines avg)

3. **Transaction Management** - backend/app/core/transactions.py
   - `@transactional` decorator for automatic commit/rollback
   - ACID guarantees for multi-step operations
   - Used in: upload, update, delete, tag operations

4. **Full Async Migration** - backend/app/core/database_async.py
   - AsyncSession throughout
   - postgresql+asyncpg:// driver
   - async/await stack with lifespan events
   - Better concurrency under load

5. **Centralized Exception Handling** - backend/app/core/exceptions.py + exception_handlers.py
   - 15+ custom exceptions with automatic HTTP mapping
   - Structured error responses
   - No manual HTTPException raising needed

#### Key Files

**Controllers** (thin):
- `backend/app/api/v1/documents.py` (216 lines, 8 endpoints)
- `backend/app/api/v1/search.py` (124 lines, 2 endpoints)

**Managers** (business logic):
- `backend/app/managers/document_manager.py` (118 lines)
- `backend/app/managers/upload_manager.py` (254 lines)
- `backend/app/managers/search_manager.py` (162 lines)
- `backend/app/managers/tag_manager.py` (88 lines)

**Services** (data access):
- `backend/app/services/document_service.py` (178 lines, async CRUD)
- `backend/app/services/tag_service.py` (97 lines, JOIN for counts)
- `backend/app/services/upload_task_service.py` (78 lines, progress tracking)
- `backend/app/services/search_service.py` (407 lines, Qdrant + BM25 + async queries)

**Infrastructure**:
- `backend/app/core/database_async.py` (71 lines, AsyncSession setup)
- `backend/app/core/transactions.py` (113 lines, @transactional decorator)
- `backend/app/core/exceptions.py` (210 lines, custom exceptions)
- `backend/app/core/exception_handlers.py` (221 lines, HTTP mapping)
- `backend/app/schemas/requests.py` (293 lines, Pydantic validation)

#### Benefits

- **Type Safety**: Pydantic validation at API boundary
- **Testability**: Managers isolated from HTTP layer
- **ACID Guarantees**: @transactional ensures consistency
- **Performance**: Full async stack for better concurrency
- **Maintainability**: Clear separation of concerns
- **Error Handling**: Consistent JSON responses

See `IMPROVEMENTS_COMPLETED.md` section 6 for full implementation details.

## MCP Tool Interface

The MCP server exposes **8 tools** optimized for LLM consumption:

1. **list_documents**: Returns all documents with metadata, pagination (limit/offset)
2. **list_tags**: Returns unique tags across all documents
3. **search**: Global semantic search (hybrid: vector + BM25 + RRF)
4. **search_by_tag**: Search filtered by tags (supports match_all for AND logic)
5. **search_by_document**: Search within specific documents by ID or name
6. **get_document**: Retrieve full document content by ID (text/markdown/json formats)
7. **search_with_filters**: Advanced search with combined filters (tags + documents + date range)
8. **get_statistics**: Knowledge base stats (total docs, chunks, tag distribution, recent uploads)

**Design Rationale**:
- **8 tools** provide complete coverage: discovery, search, retrieval, statistics
- Tool names are verb-based for clarity
- Descriptions include usage guidance ("Use this when...")
- Input schemas have sensible defaults (top_k=5, min_score=0.0)
- Outputs include chunk type (text/table/image) so LLM can adapt explanations
- Provenance fields (page, source_document, chunk_id) enable citation
- `search_with_filters` unifies multiple filters (avoids multiple tool calls)
- `get_document` supports multiple output formats for flexibility
- **Hybrid search default**: Vector + BM25 + RRF (+30-40% recall vs vector-only)

## Authentication

- **Backend API**: Bearer token via `Authorization: Bearer <api_key>` header
- **MCP Server**: Same Bearer token mechanism
- Set `MCP_API_KEY` in `.env` file
- API key validation happens via FastAPI dependency injection

## Database Schema

**PostgreSQL**:
- `documents`: id (UUID), name, file_hash (SHA256), file_size, mime_type, page_count, chunk_count, **status** ('pending'|'processing'|'completed'|'failed'), error_message, timestamps
- `tags`: id (SERIAL), name (unique), created_at
- `document_tags`: junction table for many-to-many
- `chunks`: id (UUID), document_id, chunk_index, chunk_type, page_number, text_preview (first 200 chars), created_at
- `upload_tasks`: id (UUID), document_id, status, **progress** (0-100), error_message, started_at, completed_at

**Qdrant Collection**: `documents`
- Vectors: 1536 dimensions (text-embedding-3-small)
- Payload: text, type, page, document_id, document_name, tags, created_at

**Migrations**: Alembic for schema versioning

## Service Communication

| From → To | Protocol | Endpoint/Port | Purpose |
|-----------|----------|---------------|---------|
| Frontend → Backend | HTTP | `backend:8000` | REST API calls |
| Backend → PostgreSQL | TCP/SQL | `postgres:5432` | Metadata storage |
| Backend → Redis | TCP | `redis:6379` | Cache, sessions |
| Backend → Celery | Redis | `redis://redis:6379/0` | Task queue messaging |
| Celery → Qdrant | gRPC | `qdrant:6334` | Vector ops during ingestion |
| Backend → Qdrant | gRPC | `qdrant:6334` | Vector ops for search |
| MCP Server → PostgreSQL | TCP/SQL | `postgres:5432` | Metadata queries |
| MCP Server → Qdrant | gRPC | `qdrant:6334` | Hybrid search |
| MCP Server → Redis | TCP | `redis:6379` | Search result caching |
| Prometheus → All | HTTP | `:8000/metrics`, `:8001/metrics` | Metrics scraping |

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY`: For embeddings (text-embedding-3-small)
- `MCP_API_KEY`: Authentication for backend and MCP server
- `SECRET_KEY`: FastAPI secret (min 32 chars)
- `DB_PASSWORD`: PostgreSQL password
- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql://indigo:${DB_PASSWORD}@postgres:5432/indigo`)
- `REDIS_URL`: Redis connection string (default: `redis://redis:6379/0`)
- `QDRANT_HOST`: Hostname (default: `qdrant`)
- `QDRANT_GRPC_PORT`: Port (default: `6334`)
- `CELERY_BROKER_URL`: Redis URL for Celery (default: `redis://redis:6379/0`)
- `ENABLE_HYBRID_SEARCH`: Feature flag (default: `true`)
- `ENABLE_RERANKING`: Feature flag (default: `true`, adds ~200ms latency after model load, ~10s first query)
- `CHUNK_SIZE`: Token limit per chunk (default: `1000`)
- `CHUNK_OVERLAP`: Overlap in tokens (default: `200`)

## Implementation Phases (from PLAN.md - Revised)

**Full Implementation (36 hours)**:
1. **Infrastructure Setup** (3h): Docker Compose (Postgres, Redis, Qdrant, Prometheus), Alembic migrations
2. **Backend Core** (4h): PostgreSQL models, CRUD, Celery setup, input validation, metrics endpoint
3. **Async Upload Pipeline** (5h): Validation + queueing, Celery tasks, PyMuPDF + Tabula + PaddleOCR, LangChain chunking, batch embeddings, progress tracking
4. **Hybrid Search Engine** (5h): Vector + BM25 + RRF + optional reranking, Redis caching, filters (tags/documents/dates)
5. **MCP Server** (4h): FastMCP, 8 tools, auth middleware, testing
6. **Frontend** (4h): React + Vite + Tailwind + TypeScript + Zustand, upload with progress bar, dashboard
7. **Security & Monitoring** (3h): Rate limiting, file validation, structured logging, Prometheus metrics, CORS
8. **Testing** (4h): Unit tests, integration tests, E2E tests (Playwright), load testing
9. **Optimization** (2h): Embedding batching, BM25 cache warming, query optimization, resource limits
10. **Documentation** (2h): README, API docs, MCP examples, demo video, CLAUDE.md

**MVP (12 hours)**: Phases 1-2, simplified Phase 3 (sync upload), MCP with 5 tools, minimal frontend
**Complete (21 hours)**: Add Phases 4, 7, partial Phase 8

## Key Features

**Hybrid Search with Reranking (Default)**:
- Combines dense (vector) + sparse (BM25) retrieval
- Uses Reciprocal Rank Fusion (RRF): `RRF(d) = Σ 1/(k + rank(d))` where k=60
- **Cross-encoder reranking enabled by default** (sentence-transformers)
  - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - ~10s first query (model loading), ~200ms subsequent queries
  - Can disable via `ENABLE_RERANKING=false`
- **+30-40% recall** vs vector-only search
- Cached results in Redis (TTL: 1800s)

**Async Processing**:
- Celery workers handle PDF processing in background
- Progress tracking via polling endpoint
- No timeouts on large files (100+ page PDFs)
- Automatic retry on failure

**Chunk Provenance**:
- Each chunk includes page number, section heading (if available), document name
- Enables precise citation in LLM responses

**Production Features**:
- Rate limiting (10 uploads/hour, 100 searches/min)
- Structured logging (structlog)
- Prometheus metrics
- Input validation (file type, size, magic numbers)
- CORS policy
- Health checks with dependencies

## Key Files to Understand

- `PLAN.md`: Comprehensive 21-hour implementation plan with detailed architecture diagrams
- `specification.txt`: Original assignment requirements from indigo.ai
- `docker-compose.yaml`: Service orchestration configuration
- `.env.example`: Environment variable template
- `backend/config.py`: Pydantic settings management
- `backend/app/services/`: PDF parsing (PyMuPDF4LLM), chunking, embedding, search logic
- `mcp/server.py`: FastMCP tool definitions and implementations
- `frontend/src/`: React components for document management UI
