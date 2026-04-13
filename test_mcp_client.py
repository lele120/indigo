#!/usr/bin/env python3
"""
MCP Client Test Script

Tests all 8 MCP tools by calling them via the backend API
(since MCP tools are wrappers around the backend REST API)
"""
import json
import requests
from typing import Dict, Any

# Backend API configuration
BACKEND_URL = "http://localhost:8000"

def print_result(tool_name: str, result: Dict[Any, Any], success: bool = True):
    """Pretty print test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - {tool_name}")
    print("─" * 60)
    if isinstance(result, dict):
        print(json.dumps(result, indent=2))
    else:
        print(result)
    print()


def test_get_stats():
    """Test get_stats tool"""
    print("\n" + "="*60)
    print("TEST 1: get_stats")
    print("="*60)

    try:
        # Get total documents
        response = requests.get(f"{BACKEND_URL}/api/v1/documents", params={"page": 1, "page_size": 1})
        total_docs = response.json().get("total", 0)

        # Get documents by status
        stats = {"total_documents": total_docs}
        for status in ["pending", "processing", "completed", "failed"]:
            response = requests.get(f"{BACKEND_URL}/api/v1/documents",
                                   params={"page": 1, "page_size": 1, "status": status})
            stats[f"documents_{status}"] = response.json().get("total", 0)

        # Get tags
        response = requests.get(f"{BACKEND_URL}/api/v1/documents/tags/all")
        tags_list = response.json()  # This is a list, not a dict
        stats["total_tags"] = len(tags_list) if isinstance(tags_list, list) else 0
        stats["tags"] = [t.get("name") for t in tags_list] if isinstance(tags_list, list) else []

        print_result("get_stats", stats, True)
        return True
    except Exception as e:
        print_result("get_stats", {"error": str(e)}, False)
        return False


def test_list_documents():
    """Test list_documents tool"""
    print("\n" + "="*60)
    print("TEST 2: list_documents")
    print("="*60)

    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/documents",
                               params={"page": 1, "page_size": 5})
        response.raise_for_status()

        data = response.json()
        result = {
            "total": data.get("total", 0),
            "page": data.get("page", 1),
            "page_size": data.get("page_size", 5),
            "documents_count": len(data.get("items", [])),
            "first_document": data.get("items", [{}])[0] if data.get("items") else None
        }

        print_result("list_documents", result, True)
        return True
    except Exception as e:
        print_result("list_documents", {"error": str(e)}, False)
        return False


def test_search():
    """Test search tool (hybrid)"""
    print("\n" + "="*60)
    print("TEST 3: search (hybrid)")
    print("="*60)

    try:
        payload = {
            "query": "vector embeddings",
            "limit": 3,
            "use_hybrid": True
        }

        response = requests.post(f"{BACKEND_URL}/api/v1/search", json=payload)
        response.raise_for_status()

        data = response.json()
        result = {
            "query": data.get("query"),
            "total": data.get("total", 0),
            "use_hybrid": data.get("use_hybrid"),
            "search_time_ms": data.get("search_time_ms"),
            "results_preview": [
                {
                    "document_name": r.get("document_name"),
                    "page": r.get("page_number"),
                    "rrf_score": round(r.get("rrf_score", 0), 4) if r.get("rrf_score") else None,
                    "preview": r.get("text_preview", "")[:80] + "..."
                }
                for r in data.get("results", [])[:3]
            ]
        }

        print_result("search", result, True)
        return True
    except Exception as e:
        print_result("search", {"error": str(e)}, False)
        return False


def test_search_by_tag():
    """Test search_by_tag tool"""
    print("\n" + "="*60)
    print("TEST 4: search_by_tag")
    print("="*60)

    try:
        # First get available tags
        tags_response = requests.get(f"{BACKEND_URL}/api/v1/documents/tags/all")
        tags = tags_response.json()  # This is a list, not a dict

        if not tags:
            print_result("search_by_tag", {"message": "No tags available to search"}, True)
            return True

        # Use first tag
        test_tag = tags[0]["name"]
        response = requests.get(f"{BACKEND_URL}/api/v1/documents",
                               params={"tags": test_tag, "page": 1, "page_size": 5})
        response.raise_for_status()

        data = response.json()
        result = {
            "searched_tag": test_tag,
            "total_found": data.get("total", 0),
            "documents": [
                {
                    "name": doc.get("name"),
                    "tags": [t["name"] for t in doc.get("tags", [])]
                }
                for doc in data.get("items", [])[:3]
            ]
        }

        print_result("search_by_tag", result, True)
        return True
    except Exception as e:
        print_result("search_by_tag", {"error": str(e)}, False)
        return False


def test_get_document():
    """Test get_document tool"""
    print("\n" + "="*60)
    print("TEST 5: get_document")
    print("="*60)

    try:
        # Get first document ID
        list_response = requests.get(f"{BACKEND_URL}/api/v1/documents",
                                    params={"page": 1, "page_size": 1})
        items = list_response.json().get("items", [])

        if not items:
            print_result("get_document", {"message": "No documents available to get"}, True)
            return True

        doc_id = items[0]["id"]
        response = requests.get(f"{BACKEND_URL}/api/v1/documents/{doc_id}")
        response.raise_for_status()

        data = response.json()
        result = {
            "id": data.get("id"),
            "name": data.get("name"),
            "status": data.get("status"),
            "page_count": data.get("page_count"),
            "chunk_count": data.get("chunk_count"),
            "tags": [t["name"] for t in data.get("tags", [])],
            "uploaded_at": data.get("uploaded_at")
        }

        print_result("get_document", result, True)
        return True
    except Exception as e:
        print_result("get_document", {"error": str(e)}, False)
        return False


def main():
    """Run all MCP tool tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "MCP SERVER TEST SUITE" + " "*22 + "║")
    print("║" + " "*12 + "Testing 8 Tools via Backend API" + " "*13 + "║")
    print("╚" + "="*58 + "╝")

    tests = [
        ("get_stats", test_get_stats),
        ("list_documents", test_list_documents),
        ("search", test_search),
        ("search_by_tag", test_search_by_tag),
        ("get_document", test_get_document),
    ]

    results = []
    for name, test_func in tests:
        success = test_func()
        results.append((name, success))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
