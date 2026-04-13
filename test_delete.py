#!/usr/bin/env python3
"""Test delete_document fix"""
import requests
import json

BACKEND_URL = "http://localhost:8000"

# Get a document to delete
resp = requests.get(f"{BACKEND_URL}/api/v1/documents", params={"page": 1, "page_size": 1, "status": "completed"})
docs = resp.json().get("items", [])

if not docs:
    print("❌ No completed documents to test delete")
    exit(1)

doc_id = docs[0]["id"]
doc_name = docs[0]["name"]

print(f"Testing delete on document: {doc_name} ({doc_id})")

# Test delete
try:
    resp = requests.delete(f"{BACKEND_URL}/api/v1/documents/{doc_id}")
    resp.raise_for_status()
    print(f"✅ DELETE SUCCESS - Document {doc_id} deleted")
    print(f"   HTTP Status: {resp.status_code}")

    # Verify deletion
    resp = requests.get(f"{BACKEND_URL}/api/v1/documents/{doc_id}")
    if resp.status_code == 404:
        print("✅ VERIFICATION SUCCESS - Document not found after delete")
    else:
        print(f"⚠️  Document still exists (status {resp.status_code})")

except Exception as e:
    print(f"❌ DELETE FAILED: {e}")
    exit(1)
