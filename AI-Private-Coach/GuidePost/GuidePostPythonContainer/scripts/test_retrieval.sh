#!/usr/bin/env bash
# Test RAG retrieval flow against the running Guidepost backend (default: http://localhost:8000).
# Usage: ./scripts/test_retrieval.sh [BASE_URL]

set -e
BASE_URL="${1:-http://localhost:8000}"

echo "=== 1. Health check ==="
curl -s "${BASE_URL}/health" | head -5
echo ""

echo "=== 2. RAG retrieve_context (query + topK) ==="
curl -s -X POST "${BASE_URL}/api/rag/retrieve_context" \
  -H "Content-Type: application/json" \
  -d '{"query": "coaching feedback and communication", "topK": 3}' | python3 -m json.tool 2>/dev/null || cat
echo ""

echo "=== 3. RAG extract_queries (from a short report) ==="
curl -s -X POST "${BASE_URL}/api/rag/extract_queries" \
  -H "Content-Type: application/json" \
  -d '{"report": "The conversation showed several coaching opportunities: clarity of goals, active listening, and follow-up on commitments."}' | python3 -m json.tool 2>/dev/null || cat
echo ""

echo "Done. If retrieve_context returned matches, retrieval is working."
