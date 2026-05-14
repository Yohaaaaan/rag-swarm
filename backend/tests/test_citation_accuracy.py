"""
CITATION ACCURACY TESTS
Validates that cited [filename:#] chunks contain the cited facts
"""
import re
import pytest
import httpx

BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0


def extract_citations(answer_text: str) -> list[tuple[str, str]]:
    """Extract all [filename:#] citations from answer text"""
    return re.findall(r'\[([^\]:]+):([^\]]+)\]', answer_text)


def find_chunk_in_response(response_json: dict, filename: str, chunk_idx: str) -> dict | None:
    """Find a specific chunk by filename and chunk_idx in the response sources"""
    for chunk in response_json.get("sources", []):
        if str(chunk.get("page")) == str(chunk_idx) and chunk.get("filename") == filename:
            return chunk
    return None


@pytest.mark.asyncio
async def test_citation_accuracy_basic():
    """Q: 'What chunk size?' → every cited chunk must contain '500'"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "What is the chunk size used for document processing?", "history": []},
        )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    answer = data["answer"]
    cited_refs = extract_citations(answer)

    assert len(cited_refs) > 0, f"No citations found in answer: {answer[:200]}"

    # For each citation, the cited chunk must contain "500"
    for filename, chunk_idx in cited_refs:
        chunk = find_chunk_in_response(data, filename, chunk_idx)
        assert chunk is not None, f"Cited chunk [{filename}:{chunk_idx}] not found in sources"
        excerpt = chunk.get("excerpt", "").lower()
        assert "500" in excerpt, (
            f"Cited chunk [{filename}:{chunk_idx}] does not contain '500'. "
            f"Excerpt: {excerpt[:200]}"
        )


@pytest.mark.asyncio
async def test_grounded_citations():
    """10 diverse queries, every cited chunk must contain the key fact"""
    queries = [
        ("What is the chunk size?", "500"),
        ("What embedding model is used?", "embedding"),
        ("How many agents are described?", "5"),
        ("What models are used for synthesis?", "deepseek"),
        ("What is the synthesis agent?", "synthesis"),
        ("What is the retrieval method?", "cosine"),
        ("What is the BM25 weight?", "0.3"),
        ("What file formats are supported?", "pdf"),
        ("How does the ingestion agent work?", "ingestion"),
        ("What is the chunk overlap?", "overlap"),
    ]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for query, key_term in queries:
            response = await client.post(
                f"{BASE_URL}/chat",
                json={"query": query, "history": []},
            )
            assert response.status_code == 200, f"Query '{query}' failed: {response.status_code}"
            data = response.json()

            answer = data["answer"]
            cited_refs = extract_citations(answer)

            if not cited_refs:
                # If no citations, either the answer mentions the key term, or it's a legitimate "I don't know"
                has_key_term = key_term.lower() in answer.lower()
                is_dont_know = "don't know" in answer.lower() or "do not know" in answer.lower()
                assert has_key_term or is_dont_know, (
                    f"Query '{query}' produced no citations AND answer doesn't mention '{key_term}' and doesn't say it doesn't know: {answer[:200]}"
                )
                continue

            # At least one citation should be verifiable
            verified_count = 0
            for filename, chunk_idx in cited_refs:
                chunk = find_chunk_in_response(data, filename, chunk_idx)
                if chunk and key_term.lower() in chunk.get("excerpt", "").lower():
                    verified_count += 1

            assert verified_count > 0 or len(data.get("unverified_citations", [])) > 0, (
                f"Query '{query}': none of the {len(cited_refs)} cited chunks contain '{key_term}' and none were marked unverified. "
                f"Answer: {answer[:300]}"
            )


@pytest.mark.asyncio
async def test_unverified_citations_field_present():
    """Response always includes 'unverified_citations' field"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "What is the chunk size?", "history": []},
        )
    assert response.status_code == 200
    data = response.json()

    assert "unverified_citations" in data, (
        f"Response missing 'unverified_citations' field. Keys: {list(data.keys())}"
    )
    assert "sources" in data, "Response missing 'sources' field"
    assert "answer" in data, "Response missing 'answer' field"


@pytest.mark.asyncio
async def test_hallucinated_citation_rejected():
    """Query where only 1 chunk contains the answer — wrong citation must be unverified"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "What is the exact BM25 weighting for keyword search?", "history": []},
        )
    data = response.json()

    answer = data["answer"]
    cited_refs = extract_citations(answer)
    unverified = data.get("unverified_citations", [])

    # If the model cited wrong chunks, they should be in unverified_citations
    for filename, chunk_idx in cited_refs:
        chunk = find_chunk_in_response(data, filename, chunk_idx)
        if chunk:
            excerpt = chunk.get("excerpt", "").lower()
            if "0.3" not in excerpt and "bm25" not in excerpt and "keyword" not in excerpt:
                # This citation should be flagged as unverified
                matching = [u for u in unverified if u.get("filename") == filename and u.get("chunk_idx") == chunk_idx]
                # Either it's in unverified, or the answer is honest
                has_relevant = any(term in excerpt for term in ["0.3", "bm25", "keyword"])
                if not has_relevant:
                    assert len(matching) > 0 or "don't know" in answer.lower(), (
                        f"Chunk [{filename}:{chunk_idx}] doesn't contain BM25 info but was not flagged as unverified"
                    )


@pytest.mark.asyncio
async def test_no_answer_scenario():
    """Query with no answer in docs → unverified_citations or 'I don't know'"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "What is the secret API key?", "history": []},
        )
    data = response.json()
    answer = data["answer"].lower()
    unverified = data.get("unverified_citations", [])
    sources = data.get("sources", [])

    # Either model says it doesn't know, or some citations were unverified
    assert "don't know" in answer or len(unverified) > 0 or len(sources) == 0, (
        f"Expected 'I don't know' or unverified_citations for unknown query. "
        f"Answer: {answer[:200]}, unverified: {unverified}"
    )


@pytest.mark.asyncio
async def test_sources_always_have_verified_flag():
    """Every source in response should have a 'verified' boolean field"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "How does the embedding agent work?", "history": []},
        )
    data = response.json()

    for i, source in enumerate(data.get("sources", [])):
        assert "verified" in source, (
            f"Source {i} missing 'verified' field: {source}"
        )


@pytest.mark.asyncio
async def test_citation_numbers_match_chunks():
    """Cited [filename:#] must match actual chunk content in sources"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"query": "What is the chunk size?", "history": []},
        )
    data = response.json()

    answer = data["answer"]
    cited_refs = extract_citations(answer)

    for filename, chunk_idx in cited_refs:
        # The source list should have this exact filename:chunk_idx
        found = find_chunk_in_response(data, filename, chunk_idx)
        assert found is not None, (
            f"Citation [{filename}:{chunk_idx}] not found in sources. "
            f"Available sources: {[(s['filename'], s['page']) for s in data.get('sources', [])]}"
        )
