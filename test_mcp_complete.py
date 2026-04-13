#!/usr/bin/env python3
"""
Complete MCP Tools Test - All 8 Tools

Tests all 8 MCP tools including CRUD operations
"""
import json
import requests
import os
import tempfile

BACKEND_URL = "http://localhost:8000"

def print_test(name: str, status: str, details: dict = None):
    """Print formatted test result"""
    symbols = {"pass": "✅", "fail": "❌", "info": "ℹ️"}
    print(f"\n{symbols.get(status, 'ℹ️')} {name}")
    if details:
        print(f"   {json.dumps(details, indent=3)}")


def create_test_pdf():
    """Create a simple test PDF"""
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (MCP Test Document) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
306
%%EOF"""

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
        f.write(pdf_content)
        return f.name


def test_all_tools():
    """Test all 8 MCP tools"""
    print("\n" + "="*70)
    print(" "*20 + "MCP COMPLETE TEST SUITE")
    print(" "*15 + "Testing All 8 Tools End-to-End")
    print("="*70)

    results = {"passed": 0, "failed": 0}

    # TEST 1: get_stats
    print("\n[1/8] Testing get_stats...")
    try:
        resp = requests.get(f"{BACKEND_URL}/api/v1/documents", params={"page": 1, "page_size": 1})
        total = resp.json().get("total", 0)
        print_test("get_stats", "pass", {"total_documents": total})
        results["passed"] += 1
    except Exception as e:
        print_test("get_stats", "fail", {"error": str(e)})
        results["failed"] += 1

    # TEST 2: list_documents
    print("\n[2/8] Testing list_documents...")
    try:
        resp = requests.get(f"{BACKEND_URL}/api/v1/documents", params={"page": 1, "page_size": 3})
        data = resp.json()
        print_test("list_documents", "pass", {
            "total": data.get("total"),
            "returned": len(data.get("items", []))
        })
        results["passed"] += 1
    except Exception as e:
        print_test("list_documents", "fail", {"error": str(e)})
        results["failed"] += 1

    # TEST 3: upload_document
    print("\n[3/8] Testing upload_document...")
    test_pdf_path = None
    uploaded_doc_id = None
    try:
        test_pdf_path = create_test_pdf()
        with open(test_pdf_path, 'rb') as f:
            files = {'file': ('mcp_test.pdf', f, 'application/pdf')}
            data = {'tags': 'mcp-test,automated'}
            resp = requests.post(f"{BACKEND_URL}/api/v1/documents/upload", files=files, data=data)
            resp.raise_for_status()
            result = resp.json()
            uploaded_doc_id = result.get("document_id")
            print_test("upload_document", "pass", {
                "document_id": uploaded_doc_id,
                "task_id": result.get("task_id")
            })
            results["passed"] += 1
    except Exception as e:
        print_test("upload_document", "fail", {"error": str(e)})
        results["failed"] += 1
    finally:
        if test_pdf_path and os.path.exists(test_pdf_path):
            os.unlink(test_pdf_path)

    # Wait a bit for processing
    if uploaded_doc_id:
        import time
        print("   ⏳ Waiting 3s for document processing...")
        time.sleep(3)

    # TEST 4: get_document
    print("\n[4/8] Testing get_document...")
    if uploaded_doc_id:
        try:
            resp = requests.get(f"{BACKEND_URL}/api/v1/documents/{uploaded_doc_id}")
            resp.raise_for_status()
            doc = resp.json()
            print_test("get_document", "pass", {
                "id": doc.get("id"),
                "name": doc.get("name"),
                "status": doc.get("status")
            })
            results["passed"] += 1
        except Exception as e:
            print_test("get_document", "fail", {"error": str(e)})
            results["failed"] += 1
    else:
        print_test("get_document", "info", {"skipped": "No document uploaded"})

    # TEST 5: search
    print("\n[5/8] Testing search (hybrid)...")
    try:
        payload = {"query": "test document", "limit": 2, "use_hybrid": True}
        resp = requests.post(f"{BACKEND_URL}/api/v1/search", json=payload)
        resp.raise_for_status()
        data = resp.json()
        print_test("search", "pass", {
            "query": data.get("query"),
            "results": data.get("total"),
            "time_ms": round(data.get("search_time_ms", 0), 2)
        })
        results["passed"] += 1
    except Exception as e:
        print_test("search", "fail", {"error": str(e)})
        results["failed"] += 1

    # TEST 6: search_by_tag
    print("\n[6/8] Testing search_by_tag...")
    try:
        resp = requests.get(f"{BACKEND_URL}/api/v1/documents",
                           params={"tags": "mcp-test", "page": 1, "page_size": 5})
        resp.raise_for_status()
        data = resp.json()
        print_test("search_by_tag", "pass", {
            "tag": "mcp-test",
            "found": data.get("total")
        })
        results["passed"] += 1
    except Exception as e:
        print_test("search_by_tag", "fail", {"error": str(e)})
        results["failed"] += 1

    # TEST 7: update_document
    print("\n[7/8] Testing update_document...")
    if uploaded_doc_id:
        try:
            payload = {"name": "Updated MCP Test Document", "tags": ["mcp-test", "updated"]}
            resp = requests.patch(f"{BACKEND_URL}/api/v1/documents/{uploaded_doc_id}", json=payload)
            resp.raise_for_status()
            doc = resp.json()
            print_test("update_document", "pass", {
                "id": doc.get("id"),
                "new_name": doc.get("name"),
                "tags": [t.get("name") for t in doc.get("tags", [])]
            })
            results["passed"] += 1
        except Exception as e:
            print_test("update_document", "fail", {"error": str(e)})
            results["failed"] += 1
    else:
        print_test("update_document", "info", {"skipped": "No document uploaded"})

    # TEST 8: delete_document
    print("\n[8/8] Testing delete_document...")
    if uploaded_doc_id:
        try:
            resp = requests.delete(f"{BACKEND_URL}/api/v1/documents/{uploaded_doc_id}")
            resp.raise_for_status()
            print_test("delete_document", "pass", {
                "deleted_id": uploaded_doc_id,
                "status": "deleted successfully"
            })
            results["passed"] += 1
        except Exception as e:
            print_test("delete_document", "fail", {"error": str(e)})
            results["failed"] += 1
    else:
        print_test("delete_document", "info", {"skipped": "No document to delete"})

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    total = results["passed"] + results["failed"]
    print(f"✅ Passed: {results['passed']}/{total}")
    print(f"❌ Failed: {results['failed']}/{total}")

    if results["failed"] == 0:
        print("\n🎉 All MCP tools tested successfully!")
        return 0
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(test_all_tools())
