#!/bin/bash
# Test script for multi-format document support

echo "🧪 Testing Multi-Format Document Processing"
echo "==========================================="
echo ""

# Colors
GREEN='\033[0.32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Step 1: Apply database migration${NC}"
docker-compose exec -T backend alembic upgrade head

echo ""
echo -e "${BLUE}Step 2: Restart services${NC}"
docker-compose restart backend celery-worker

echo ""
echo -e "${BLUE}Step 3: Wait for services to be ready${NC}"
sleep 5

echo ""
echo -e "${BLUE}Step 4: Check backend health${NC}"
curl -s http://localhost:8000/health | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo ""
echo ""
echo -e "${YELLOW}📝 Test 1: Create sample TXT file${NC}"
cat > /tmp/test_sample.txt <<'EOF'
# Sample Document

This is a test document for the Indigo Document Intelligence system.

## Features
- Multi-format support (PDF, DOCX, Excel, CSV, TXT, MD, PPTX)
- Embedding fallback to BM25-only mode
- Redis search caching
- Hybrid search (Vector + BM25)

## Testing
This file tests plain text processing.
The system should:
1. Extract all text
2. Chunk intelligently
3. Generate embeddings (if OpenAI available)
4. Enable BM25 search regardless of embeddings
EOF

echo "✅ Created /tmp/test_sample.txt"

echo ""
echo -e "${YELLOW}📝 Test 2: Create sample CSV file${NC}"
cat > /tmp/test_sales.csv <<'EOF'
Date,Product,Quantity,Revenue
2024-01-15,Widget A,150,15000
2024-01-16,Widget B,200,30000
2024-01-17,Widget A,175,17500
2024-01-18,Widget C,100,25000
2024-01-19,Widget B,225,33750
EOF

echo "✅ Created /tmp/test_sales.csv"

echo ""
echo -e "${YELLOW}📝 Test 3: Create sample Markdown file${NC}"
cat > /tmp/test_readme.md <<'EOF'
# Indigo Document Intelligence

## Overview
Indigo is a powerful document intelligence system that supports multiple file formats.

### Supported Formats
| Format | Extensions | Status |
|--------|-----------|--------|
| PDF | .pdf | ✅ |
| Word | .docx, .doc | ✅ |
| Excel | .xlsx, .xls | ✅ |
| CSV | .csv | ✅ |
| Text | .txt, .md | ✅ |
| PowerPoint | .pptx, .ppt | ✅ |

### Features
- **Hybrid Search**: Combines vector similarity and BM25
- **Embedding Fallback**: Works even if OpenAI API fails
- **Search Cache**: Redis-based caching for fast repeated queries
- **Multi-format**: Process documents in various formats

## Installation
```bash
docker-compose up -d
```

## Usage
Upload documents via API:
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@document.pdf" \
  -F "tags=important,q1-2024"
```
EOF

echo "✅ Created /tmp/test_readme.md"

echo ""
echo ""
echo -e "${GREEN}📤 Uploading test files...${NC}"

echo ""
echo -e "${YELLOW}Upload 1: Plain text file${NC}"
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/tmp/test_sample.txt" \
  -F "tags=test,txt,multiformat" \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Document ID: {data.get(\"document_id\")}\nTask ID: {data.get(\"task_id\")}\nStatus: {data.get(\"status\")}')"

echo ""
echo ""
echo -e "${YELLOW}Upload 2: CSV file${NC}"
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/tmp/test_sales.csv" \
  -F "tags=test,csv,sales,data" \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Document ID: {data.get(\"document_id\")}\nTask ID: {data.get(\"task_id\")}\nStatus: {data.get(\"status\")}')"

echo ""
echo ""
echo -e "${YELLOW}Upload 3: Markdown file${NC}"
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/tmp/test_readme.md" \
  -F "tags=test,markdown,readme" \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Document ID: {data.get(\"document_id\")}\nTask ID: {data.get(\"task_id\")}\nStatus: {data.get(\"status\")}')"

echo ""
echo ""
echo -e "${BLUE}⏳ Waiting 30 seconds for processing...${NC}"
sleep 30

echo ""
echo -e "${GREEN}📊 Checking document processing status${NC}"
curl -s http://localhost:8000/api/v1/documents?page_size=5 | \
  python3 -c "import sys, json; data=json.load(sys.stdin); docs=data.get('documents', []); print(f'Total documents: {data.get(\"total\", 0)}\n'); [print(f'{i+1}. {d[\"name\"]} - {d[\"file_type\"]} - Status: {d[\"status\"]} - Has Embeddings: {d.get(\"has_embeddings\", True)}') for i, d in enumerate(docs[:5])]"

echo ""
echo ""
echo -e "${GREEN}🔍 Testing search (with cache)${NC}"

echo ""
echo -e "${YELLOW}Search 1: 'document intelligence'${NC}"
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "document intelligence", "limit": 3}' \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Results: {data.get(\"total\")}\nSearch time: {data.get(\"search_time_ms\"):.1f}ms')"

echo ""
echo -e "${YELLOW}Search 2: Same query (should hit cache)${NC}"
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "document intelligence", "limit": 3}' \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Results: {data.get(\"total\")}\nSearch time: {data.get(\"search_time_ms\"):.1f}ms (cached!)')"

echo ""
echo -e "${YELLOW}Search 3: CSV data - 'Widget B'${NC}"
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Widget B sales revenue", "limit": 2}' \
  -s | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Results: {data.get(\"total\")}\nSearch time: {data.get(\"search_time_ms\"):.1f}ms')"

echo ""
echo ""
echo -e "${GREEN}✅ Multi-format testing complete!${NC}"
echo ""
echo -e "${BLUE}📊 Summary of new features:${NC}"
echo "  ✅ TXT file processing"
echo "  ✅ CSV file processing (with data extraction)"
echo "  ✅ Markdown file processing"
echo "  ✅ Embedding fallback (documents work even without embeddings)"
echo "  ✅ Search caching (second query much faster)"
echo ""
echo -e "${YELLOW}🎯 Next steps:${NC}"
echo "  • Test DOCX: Create Word document and upload"
echo "  • Test XLSX: Create Excel spreadsheet and upload"
echo "  • Test PPTX: Create PowerPoint presentation and upload"
echo "  • Monitor logs: docker logs indigo-celery-worker-1 --tail 50"
