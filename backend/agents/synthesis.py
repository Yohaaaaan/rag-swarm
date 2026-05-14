"""
SYNTHESIS AGENT
Generates answers using DeepSeek V3 via DeepInfra API
Maintains conversation history (last 10 turns)
"""
import logging
import os
import re
from dataclasses import dataclass
from typing import List, Dict

import httpx


@dataclass
class VerifiedCitation:
    filename: str
    page: int | None
    excerpt: str
    relevance_score: float
    verified: bool


@dataclass
class UnverifiedCitation:
    filename: str
    chunk_idx: str
    reason: str


logger = logging.getLogger("rag-swarm.synthesis")

DEEPINFRA_URL = "https://api.deepinfra.com/v1/openai/deepseek-ai/DeepSeek-V4-Flash"
MAX_HISTORY = 10
TIMEOUT_SECONDS = 120.0


SYSTEM_PROMPT = """You are an expert research assistant answering questions from document chunks.

CRITICAL RULES:
- NEVER say "I don't know" or "IDK" or "Information not found" — if ANY chunk has relevant information, use it
- EXTRACT and COMBINE partial information from multiple chunks to form complete answers
- If a chunk mentions even ONE relevant fact, build your answer around it
- Do NOT say information is missing just because it's not a complete answer — give what you have
- Be aggressive in using chunks — paraphrase and combine freely
- Always provide 3-5 sentences even if information is partial
- Cite sources: [filename:#] at end of relevant statements
- Only cite chunks where information actually appears verbatim"""

TEMPERATURE = float(os.getenv("SYNTHESIS_TEMPERATURE", "0.5"))  # Increase from 0.3 for more creative synthesis


class SynthesisAgent:
    """Generates answers using DeepSeek V3"""

    def __init__(self):
        api_key = os.getenv("DEEPINFRA_API_KEY")
        if not api_key:
            raise ValueError("DEEPINFRA_API_KEY not set in environment")

        self.api_key = api_key
        self.base_url = "https://api.deepinfra.com/v1/openai"
        self.model = "deepseek-ai/DeepSeek-V4-Flash"

    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history for prompt"""
        if not history:
            return "No previous conversation."

        formatted = []
        for turn in history[-MAX_HISTORY:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            formatted.append(f"{role.upper()}: {content}")

        return "\n".join(formatted)

    def _format_context(self, retrieved_chunks: List[dict]) -> str:
        """Format retrieved chunks with explicit chunk boundary markers"""
        if not retrieved_chunks:
            return "No relevant documents found."
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            metadata = chunk.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            chunk_idx = metadata.get("chunk_index", metadata.get("page_number", "?"))
            content = chunk.get("content", "")
            context_parts.append(
                f"[CHUNK {i+1}] {filename}:{chunk_idx}\n{content}\n[END CHUNK {i+1}]"
            )
        return "\n\n---\n\n".join(context_parts)

    def _extract_citations_from_answer(self, answer_text: str) -> list[tuple]:
        """Extract all [filename:#] citations from answer text"""
        return re.findall(r'\[([^\]:]+):([^\]]+)\]', answer_text)

    def _extract_key_facts(self, answer_text: str, query: str) -> list[str]:
        """Extract key factual claims from answer for verification"""
        # Remove common phrases
        text = answer_text.lower()
        text = re.sub(r'\[.*?\]', '', text)  # remove citations
        text = re.sub(r'\b(the|a|an|is|are|was|were|has|have|can|could|would|should)\b', ' ', text)
        # Extract numbers and specific terms
        facts = re.findall(r'\b\d+\s*(?:characters?|bytes?|tokens?|chunks?|agents?|models?|seconds?|ms)\b', text)
        facts += re.findall(r'\b(?:openai|deepseek|chromadb|bm25|cosine|text-embedding|deepseek-v3)\b', text)
        facts += re.findall(r'\b\d+\b', text)
        return list(set(facts))[:5]

    def _verify_citation(self, filename: str, chunk_idx: str, key_facts: list[str], chunk_map: dict) -> tuple:
        """Verify a citation against chunk content"""
        key = (filename, chunk_idx)
        chunk = chunk_map.get(key)
        if not chunk:
            return (None, {"filename": filename, "chunk_idx": chunk_idx, "reason": "chunk_not_found"})

        content = chunk.get("content", "").lower()
        # Check if any key fact appears in chunk content
        for fact in key_facts:
            if fact.lower() in content:
                return (chunk, None)
        return (None, {"filename": filename, "chunk_idx": chunk_idx, "reason": "fact_not_in_chunk", "cited_facts": key_facts})

    async def process(self, query: str, retrieved_chunks: List[dict], history: List[Dict]) -> dict:
        """Generate answer from context and history"""
        logger.info(f"Synthesizing answer for query: {query[:50]}...")

        context = self._format_context(retrieved_chunks)
        history_text = self._format_history(history)

        prompt = SYSTEM_PROMPT.format(
            context=context,
            history=history_text,
            query=query,
        )

        try:
            # Build a clear prompt with context, rules, and query
            user_prompt = f"""Answer the question using the document chunks below. Extract and combine information from ALL relevant chunks.

DOCUMENT CHUNKS:
{context}

QUESTION: {query}

Give a complete 3-5 sentence answer using the chunks. Never say "I don't know" — synthesize what you have. Cite sources: [filename:#]"""

            async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.5,
                        "max_completion_tokens": 4096,
                    },
                )
                response.raise_for_status()
                result = response.json()

            raw_answer = result["choices"][0]["message"]["content"]

            # Extract citations from the answer text
            cited_refs = self._extract_citations_from_answer(raw_answer)
            key_facts = self._extract_key_facts(raw_answer, query)

            # Build chunk map for lookup
            chunk_map = {
                (c.get("metadata", {}).get("filename", ""), str(c.get("metadata", {}).get("chunk_index", "")))
                : c for c in retrieved_chunks
            }

            # Verify each citation
            verified_sources = []
            unverified_citations = []

            for filename, chunk_idx in cited_refs:
                chunk, unverified = self._verify_citation(filename, chunk_idx, key_facts, chunk_map)
                if chunk:
                    content = chunk.get("content", "")
                    excerpt = content[:350]
                    verified_sources.append({
                        "filename": chunk.get("metadata", {}).get("filename", "unknown"),
                        "page": chunk.get("metadata", {}).get("chunk_index", None),
                        "excerpt": excerpt + "..." if len(content) > 350 else excerpt,
                        "relevance_score": chunk.get("relevance_score", 0),
                        "verified": True,
                    })
                else:
                    unverified_citations.append(unverified)

            # If no citations were verified, fall back to top retrieved chunks
            if not verified_sources:
                verified_sources = [
                    {
                        "filename": c.get("metadata", {}).get("filename", "unknown"),
                        "page": c.get("metadata", {}).get("chunk_index", None),
                        "excerpt": c.get("content", "")[:350] + "...",
                        "relevance_score": c.get("relevance_score", 0),
                        "verified": False,
                    }
                    for c in retrieved_chunks[:5]
                ]

            logger.info(f"Generated answer ({len(raw_answer)} chars)")
            return {
                "answer": raw_answer,
                "sources": verified_sources,
                "unverified_citations": unverified_citations,
                "can_answer": True,
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise

    async def quick_answer(self, query: str, retrieved_chunks: List[dict], history: List[dict]) -> dict:
        """Fast check if we can answer the query - returns can_answer flag and short answer"""
        context = self._format_context(retrieved_chunks)

        user_prompt = f"""Answer the question using ONLY the provided document chunks.
If the chunks contain ANY relevant information, give a 2-3 sentence answer.
If the chunks are completely irrelevant OR the question can't be answered from them, say EXACTLY: IDK

DOCUMENT CHUNKS:
{context}

QUESTION: {query}

Remember: Only say IDK if the chunks are truly unrelated. Otherwise, provide the answer."""

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a helpful research assistant. Always try to answer from the chunks. Use IDK only when chunks are irrelevant."},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                        "max_completion_tokens": 200,
                    },
                )
                response.raise_for_status()
                result = response.json()

            raw_answer = result["choices"][0]["message"]["content"].strip()

            # Only trigger HyDE if model explicitly says IDK or answer is very short/uninformative
            is_dont_know = raw_answer.upper() == "IDK" or raw_answer.upper().startswith("I DON'T KNOW")
            too_short = len(raw_answer) < 30

            can_answer = not is_dont_know and not too_short

            return {
                "can_answer": can_answer,
                "quick_answer": raw_answer if can_answer else None,
            }
        except Exception as e:
            logger.error(f"Quick answer check failed: {e}")
            return {"can_answer": False, "quick_answer": None}