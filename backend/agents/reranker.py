"""
RERANKER AGENT
Cross-encoder reranking after hybrid retrieval
Uses AnswerDotAI/rerankers to reorder retrieved chunks by relevance
"""
import logging
from typing import List

logger = logging.getLogger("rag-swarm.reranker")

# Model options: cross-encoder/ms-marco-MiniLM-L-6-v2, cross-encoder/ms-marco-MiniLM-L-12-v2,
# cross-encoder/ms-marco-cohere condenser, etc.
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankerAgent:
    """Reranks retrieved chunks using cross-encoder model"""

    def __init__(self, model: str = DEFAULT_MODEL):
        try:
            from rerankers import Reranker
        except ImportError:
            logger.warning("rerankers not installed, skipping reranking")
            self.reranker = None
            return
        except OSError as e:
            if "torch" in str(e).lower() or "libtorch" in str(e).lower():
                logger.warning("torch not properly installed, skipping reranking")
                self.reranker = None
                return
            raise

        logger.info(f"Initializing reranker with model: {model}")
        try:
            self.reranker = Reranker(model, verbose=False)
        except Exception as e:
            if "torch" in str(e).lower() or "libtorch" in str(e).lower():
                logger.warning("torch not properly installed, skipping reranking")
                self.reranker = None
                return
            raise

    async def process(self, query: str, chunks: List[dict], top_k: int = 5) -> List[dict]:
        """Rerank chunks by cross-encoder relevance to query"""
        if not self.reranker:
            logger.info("Reranker not available, returning original order")
            return chunks[:top_k]

        if not chunks:
            return []

        logger.info(f"Reranking {len(chunks)} chunks with cross-encoder for query: {query[:50]}...")

        try:
            docs = [c["content"] for c in chunks]
            results = self.reranker.rank(query, docs)

            # Build doc -> original chunk index map
            doc_to_idx = {c["content"]: i for i, c in enumerate(chunks)}

            reranked = []
            for i, result in enumerate(results):
                doc_content = result.document
                original_idx = doc_to_idx.get(doc_content, i)
                chunk = chunks[original_idx].copy()
                chunk["rerank_score"] = result.score
                chunk["rerank_position"] = i + 1
                reranked.append(chunk)

            logger.info(f"Reranking complete, top score: {reranked[0]['rerank_score']:.4f}")
            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Reranking failed: {e}, returning original chunks")
            return chunks[:top_k]