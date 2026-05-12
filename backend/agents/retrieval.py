"""
RETRIEVAL AGENT
Handles semantic search with hybrid approach
Combines cosine similarity (0.7) + BM25 keyword (0.3)
Returns top-5 chunks with source metadata
"""
import logging
import os
import re
from typing import List

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import chromadb

logger = logging.getLogger("rag-swarm.retrieval")

TOP_K = 5
SEMANTIC_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


class RetrievalAgent:
    """Hybrid semantic + keyword retrieval"""

    def __init__(self, persist_directory: str = "./vectorstore"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key,
        )
        self.persist_directory = persist_directory

        self.client = chromadb.PersistentClient(path=persist_directory)
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="rag_swarm_docs",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _bm25_score(self, query: str, documents: List[str]) -> List[float]:
        query_terms = query.lower().split()
        doc_lengths = [len(d.lower().split()) for d in documents]
        avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
        scores = []
        for doc in documents:
            doc_lower = doc.lower()
            doc_terms = doc_lower.split()
            doc_len = len(doc_terms)
            # Count term occurrences (word-boundary aware)
            tf = sum(1 for term in query_terms for _ in re.findall(r'\b' + re.escape(term) + r'\b', doc_lower))
            k1 = 1.5
            b = 0.75
            doc_len_norm = doc_len / avg_dl if avg_dl > 0 else 1
            score = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len_norm)) if tf > 0 else 0.0
            scores.append(score)
        return scores

    async def process(self, query: str) -> List[dict]:
        """Retrieve top-k relevant chunks with hybrid scoring"""
        logger.info(f"Retrieving for query: {query[:50]}...")

        query_embedding = self.embeddings.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=50,  # Large enough to find diverse content before dedup
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            logger.warning("No results found in vectorstore")
            return []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        semantic_scores = [1 - d for d in distances]

        keyword_scores = self._bm25_score(query, documents)

        combined_scores = []
        for i in range(len(documents)):
            combined = (
                SEMANTIC_WEIGHT * semantic_scores[i]
                + KEYWORD_WEIGHT * keyword_scores[i]
            )
            combined_scores.append((i, combined))

        combined_scores.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate by chunk_index metadata - one result per logical chunk
        seen_chunk_idxs = set()
        deduped = []
        for idx, score in combined_scores:
            chunk_idx = metadatas[idx].get("chunk_index", -1)
            if chunk_idx not in seen_chunk_idxs:
                seen_chunk_idxs.add(chunk_idx)
                deduped.append((idx, score))

        top_results = []
        for rank, (idx, score) in enumerate(deduped[:TOP_K]):
            top_results.append({
                "content": documents[idx],
                "metadata": metadatas[idx],
                "relevance_score": round(score, 4),
                "rank": rank + 1,
            })

        logger.info(f"Retrieved {len(top_results)} chunks")
        return top_results