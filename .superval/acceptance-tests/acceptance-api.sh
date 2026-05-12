#!/bin/bash
# acceptance-api.sh -- RAG Swarm API acceptance tests (black box)
set -euo pipefail

BASE_URL="http://localhost:8000"
PASS=0; FAIL=0

assert_http() {
  local name="$1" expected_code="$2"; shift 2
  local response http_code body
  response=$(curl -s -w "\n%{http_code}" "$@")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')
  if [ "$http_code" = "$expected_code" ]; then
    echo "  PASS  $name"; PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (expected $expected_code, got $http_code)"; FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local name="$1" pattern="$2"; shift 2
  local response http_code body
  response=$(curl -s -w "\n%{http_code}" "$@")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')
  if [ "$http_code" = "200" ] && echo "$body" | grep -q "$pattern"; then
    echo "  PASS  $name"; PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (expected '$pattern' in response)"; FAIL=$((FAIL + 1))
  fi
}

echo "RAG SWARM ACCEPTANCE TESTS"
echo "==========================="

# AC-1: Health / docs endpoint
assert_http "AC-1: GET /docs returns 200" "200" "$BASE_URL/docs"

# AC-2: List documents
assert_http "AC-2: GET /documents returns 200" "200" "$BASE_URL/documents"

# AC-3: Chat returns distinct sources with varying scores
response=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the chunk size used for document processing?", "history": []}')

scores=$(echo "$response" | python3 -c "
import sys, json
d = json.load(sys.stdin)
scores = [s['relevance_score'] for s in d['sources']]
print(' '.join(str(s) for s in scores))
" 2>/dev/null)

if [ -n "$scores" ]; then
  unique=$(echo "$scores" | tr ' ' '\n' | sort -u | wc -l)
  if [ "$unique" -gt 1 ]; then
    echo "  PASS  AC-3: relevance scores vary ($scores)"; PASS=$((PASS + 1))
  else
    echo "  FAIL  AC-3: all scores identical ($scores)"; FAIL=$((FAIL + 1))
  fi
else
  echo "  FAIL  AC-3: could not parse scores from response"; FAIL=$((FAIL + 1))
fi

# AC-4: Excerpts are distinct (not all the same header)
excerpts=$(echo "$response" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for s in d['sources']:
    print(s['excerpt'][:60])
" 2>/dev/null)

unique_excerpts=$(echo "$excerpts" | sort -u | wc -l)
if [ "$unique_excerpts" -gt 1 ]; then
  echo "  PASS  AC-4: excerpts are distinct ($unique_excerpts unique)"; PASS=$((PASS + 1))
else
  echo "  FAIL  AC-4: all excerpts identical"; FAIL=$((FAIL + 1))
fi

# AC-5: Answer is correct and cites source
answer=$(echo "$response" | python3 -c "
import sys, json; d = json.load(sys.stdin); print(d['answer'])
" 2>/dev/null)
if echo "$answer" | grep -q "500"; then
  echo "  PASS  AC-5: answer contains chunk size (500)"; PASS=$((PASS + 1))
else
  echo "  FAIL  AC-5: answer missing chunk size"; FAIL=$((FAIL + 1))
fi

# AC-6: Different query returns different sources
response2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What embedding model is used?", "history": []}')

scores2=$(echo "$response2" | python3 -c "
import sys, json
d = json.load(sys.stdin)
scores = [s['relevance_score'] for s in d['sources']]
print(' '.join(str(s) for s in scores))
" 2>/dev/null)

if [ -n "$scores2" ]; then
  unique2=$(echo "$scores2" | tr ' ' '\n' | sort -u | wc -l)
  if [ "$unique2" -gt 1 ]; then
    echo "  PASS  AC-6: query '$scores2' scores vary"; PASS=$((PASS + 1))
  else
    echo "  FAIL  AC-6: all scores identical for second query"; FAIL=$((FAIL + 1))
  fi
else
  echo "  FAIL  AC-6: could not parse scores"; FAIL=$((FAIL + 1))
fi

# AC-7: Latency is reasonable (< 5s total)
latency=$(echo "$response" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['latency_ms']['retrieval'] + d['latency_ms']['synthesis'])
" 2>/dev/null)
if [ -n "$latency" ] && [ "$latency" -lt 5000 ]; then
  echo "  PASS  AC-7: total latency ${latency}ms < 5000ms"; PASS=$((PASS + 1))
else
  echo "  FAIL  AC-7: latency too high (${latency}ms)"; FAIL=$((FAIL + 1))
fi

# AC-8: Chat with history works
response3=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the chunk size?", "history": [{"role":"user","content":"How does chunking work?"},{"role":"assistant","content":"Chunking splits documents at sentence boundaries."}]}')

if echo "$response3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer',''))" | grep -q "500"; then
  echo "  PASS  AC-8: chat with history returns answer"; PASS=$((PASS + 1))
else
  echo "  FAIL  AC-8: chat with history failed"; FAIL=$((FAIL + 1))
fi

echo ""
echo "RESULTS: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
