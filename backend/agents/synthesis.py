"""
SYNTHESIS AGENT
Generates answers using DeepSeek V3 via DeepInfra API
Maintains conversation history (last 10 turns)
"""
import logging
import os
from typing import List, Dict

import openai

logger = logging.getLogger("rag-swarm.synthesis")

DEEPINFRA_URL = "https://api.deepinfra.com/v1/openai/deepseek-ai/DeepSeek-V3"
MAX_HISTORY = 10


SYSTEM_PROMPT = """You are a helpful AI assistant answering questions based on provided documents.

RULES:
- Answer ONLY from the provided context
- Cite sources using [filename:chunk] format
- If the answer is not in the documents, say "I don't know" or "I couldn't find this in the documents"
- Be concise but thorough
- Format your citations as: [source:page]

CONTEXT FROM DOCUMENTS:
{context}

CONVERSATION HISTORY:
{history}

USER QUESTION: {query}

YOUR ANSWER:"""


class SynthesisAgent:
    """Generates answers using DeepSeek V3"""

    def __init__(self):
        api_key = os.getenv("DEEPINFRA_API_KEY")
        if not api_key:
            raise ValueError("DEEPINFRA_API_KEY not set in environment")

        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepinfra.com/v1/openai",
        )
        self.model = "deepseek-ai/DeepSeek-V3"

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
        """Format retrieved chunks as context"""
        if not retrieved_chunks:
            return "No relevant documents found."

        context_parts = []
        for chunk in retrieved_chunks:
            metadata = chunk.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            page = metadata.get("page_number", metadata.get("chunk_index", "?"))
            content = chunk.get("content", "")

            context_parts.append(f"[{filename}:{page}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that answers based only on provided documents."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            answer = response.choices[0].message.content

            sources = [
                {
                    "filename": chunk.get("metadata", {}).get("filename", "unknown"),
                    "page": chunk.get("metadata", {}).get("page_number", None),
                    "excerpt": chunk.get("content", "")[:200] + "...",
                    "relevance_score": chunk.get("relevance_score", 0),
                }
                for chunk in retrieved_chunks[:5]
            ]

            logger.info(f"Generated answer ({len(answer)} chars)")
            return {
                "answer": answer,
                "sources": sources,
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise