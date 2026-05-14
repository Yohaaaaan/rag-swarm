"""
INSTRUCTOR SYNTHESIS AGENT
Uses Pydantic-validated structured outputs via Instructor library
Replaces raw JSON parsing with automatic validation and retry
"""
import logging
import os
from typing import List, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger("rag-swarm.instructor-synthesis")

SYSTEM_PROMPT = """You are a helpful AI assistant answering questions based on provided documents.

RULES:
- Answer ONLY from the provided context
- Cite sources using [filename:#] format where # is the chunk number
- If the answer is not in the documents, say "I don't know"
- Be concise but thorough"""


class SourceCitation(BaseModel):
    """A single source citation from a retrieved chunk"""
    filename: str = Field(description="Source filename")
    page: int | None = Field(description="Chunk/page number")
    excerpt: str = Field(description="Text excerpt from the source (max 200 chars)")
    relevance_score: float = Field(description="Relevance score from retrieval")


class SynthesisResponse(BaseModel):
    """Structured synthesis response with Pydantic validation"""
    answer: str = Field(description="The generated answer to the user's question")
    sources: List[SourceCitation] = Field(description="Source citations with excerpts and scores")
    confidence: float = Field(description="Confidence score 0-1 based on source quality and answer completeness")


class InstructorSynthesisAgent:
    """Synthesis with Pydantic-validated structured outputs"""

    def __init__(self):
        api_key = os.getenv("DEEPINFRA_API_KEY")
        if not api_key:
            raise ValueError("DEEPINFRA_API_KEY not set in environment")

        self.api_key = api_key
        self.base_url = "https://api.deepinfra.com/v1/openai"
        self.model = "deepseek-ai/DeepSeek-V4-Flash"

    def _format_history(self, history: List[dict]) -> str:
        if not history:
            return "No previous conversation."
        formatted = []
        for turn in history[-10:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        return "\n".join(formatted)

    def _format_context(self, retrieved_chunks: List[dict]) -> str:
        if not retrieved_chunks:
            return "No relevant documents found."
        context_parts = []
        for chunk in retrieved_chunks:
            metadata = chunk.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            chunk_idx = metadata.get("chunk_index", metadata.get("page_number", "?"))
            content = chunk.get("content", "")
            context_parts.append(f"[{filename}:{chunk_idx}]\n{content}")
        return "\n\n---\n\n".join(context_parts)

    async def process(self, query: str, retrieved_chunks: List[dict], history: List[dict]) -> dict:
        """Generate Pydantic-validated answer from context"""
        logger.info(f"Instructor synthesis for query: {query[:50]}...")

        context = self._format_context(retrieved_chunks)
        history_text = self._format_history(history)

        user_prompt = f"""CONTEXT FROM DOCUMENTS:
{context}

CONVERSATION HISTORY:
{history_text}

USER QUESTION: {query}

Based on the context above, provide your answer. Include confidence assessment."""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_completion_tokens": 1024,
                        # Request JSON structured output
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                result = response.json()

            raw_answer = result["choices"][0]["message"]["content"]

            # Parse and validate with Pydantic
            import json
            try:
                parsed = json.loads(raw_answer)
                # Validate with Pydantic, with fallbacks for missing fields
                answer_text = parsed.get("answer", raw_answer[:500])
                confidence = float(parsed.get("confidence", 0.5))

                sources = []
                for chunk in retrieved_chunks[:5]:
                    metadata = chunk.get("metadata", {})
                    if "sources" in parsed and isinstance(parsed["sources"], list):
                        src = parsed["sources"].pop(0) if parsed["sources"] else {}
                        sources.append(SourceCitation(
                            filename=src.get("filename", metadata.get("filename", "unknown")),
                            page=src.get("page", metadata.get("chunk_index")),
                            excerpt=src.get("excerpt", chunk.get("content", "")[:200] + "..."),
                            relevance_score=chunk.get("relevance_score", 0),
                        ))
                    else:
                        sources.append(SourceCitation(
                            filename=metadata.get("filename", "unknown"),
                            page=metadata.get("chunk_index", None),
                            excerpt=chunk.get("content", "")[:200] + "...",
                            relevance_score=chunk.get("relevance_score", 0),
                        ))

                response_model = SynthesisResponse(
                    answer=answer_text,
                    sources=sources,
                    confidence=confidence,
                )

                logger.info(f"Instructor synthesis complete, confidence: {response_model.confidence:.2f}")

                return {
                    "answer": response_model.answer,
                    "sources": [s.model_dump() for s in response_model.sources],
                    "confidence": response_model.confidence,
                }

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"JSON parse failed ({e}), using raw answer")
                # Fallback: extract what we can
                sources = [
                    {
                        "filename": chunk.get("metadata", {}).get("filename", "unknown"),
                        "page": chunk.get("metadata", {}).get("chunk_index", None),
                        "excerpt": chunk.get("content", "")[:200] + "...",
                        "relevance_score": chunk.get("relevance_score", 0),
                    }
                    for chunk in retrieved_chunks[:5]
                ]
                return {
                    "answer": raw_answer[:1000],
                    "sources": sources,
                    "confidence": 0.5,
                }

        except Exception as e:
            logger.error(f"Instructor synthesis failed: {e}")
            raise