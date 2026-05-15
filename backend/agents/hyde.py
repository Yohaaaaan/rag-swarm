"""
HYDE AGENT
Hypothetical Document Embeddings - Query Expansion
Generates a hypothetical answer document, embeds it, and uses it for retrieval
Paper: https://arxiv.org/abs/2212.10496
"""
import logging
import os

logger = logging.getLogger("rag-swarm.hyde")

HYDE_SYSTEM_PROMPT = """You are a research assistant. Generate a hypothetical document that would
correctly answer the user's question. Write 2-3 paragraphs as if you were providing
the actual answer based on authoritative sources. Be specific and detailed.
Do NOT use placeholder text like "according to the document" - write as if the
document exists and contains this information."""


class HyDEAgent:
    """Hypothetical Document Embeddings for query expansion"""

    def __init__(self):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            logger.warning("MISTRAL_API_KEY not set, HyDE will be disabled")
            self.api_key = None
            return
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.model = "mistral-large-latest"

    async def generate_hypothetical_document(self, query: str) -> str | None:
        """Generate a hypothetical document answering the query"""
        if not self.api_key:
            return None

        import httpx

        user_prompt = f"Question: {query}\n\nHypothetical Answer Document:"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.7,
                        "max_completion_tokens": 512,
                    },
                )
                response.raise_for_status()
                result = response.json()

            hypothetical_doc = result["choices"][0]["message"]["content"]
            logger.info(f"Generated hypothetical document ({len(hypothetical_doc)} chars)")
            return hypothetical_doc

        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            return None

    async def embed_text(self, text: str) -> list[float] | None:
        """Embed text using OpenAI embeddings"""
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            logger.error("langchain-openai not installed")
            return None

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set")
            return None

        try:
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
            embedding = await embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    async def process(self, query: str) -> dict:
        """
        Generate hypothetical document and its embedding for HyDE retrieval.
        Returns: {"query": original query, "hypothetical_doc": doc, "hypothetical_embedding": embedding}
        """
        logger.info(f"Processing HyDE for query: {query[:50]}...")

        hypothetical_doc = await self.generate_hypothetical_document(query)

        if not hypothetical_doc:
            return {"query": query, "hypothetical_doc": None, "hypothetical_embedding": None}

        hypothetical_embedding = await self.embed_text(hypothetical_doc)

        return {
            "query": query,
            "hypothetical_doc": hypothetical_doc,
            "hypothetical_embedding": hypothetical_embedding,
        }