"""
ORCHESTRATOR AGENT
Coordinates the RAG pipeline: ingest → embed → retrieve → synthesize
Handles errors, retries, and latency logging
"""
import logging
import os
import uuid
import time
from typing import List, Dict, Optional, Callable

from fastapi import UploadFile

from .ingestion import IngestionAgent
from .embedding import EmbeddingAgent
from .retrieval import RetrievalAgent
from .synthesis import SynthesisAgent

logger = logging.getLogger("rag-swarm.orchestrator")

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class OrchestratorAgent:
    """Coordinates all agents in the RAG pipeline"""

    def __init__(self, vectorstore_path: str = "./vectorstore"):
        self.ingestion = IngestionAgent()
        self.embedding = EmbeddingAgent(persist_directory=vectorstore_path)
        self.retrieval = RetrievalAgent(persist_directory=vectorstore_path)
        self.synthesis = SynthesisAgent()

        # Optional enhancement agents
        self.reranker = None
        self.hyde = None
        self.memory = None

        try:
            from .reranker import RerankerAgent
            self.reranker = RerankerAgent()
        except Exception:
            pass

        try:
            from .hyde import HyDEAgent
            self.hyde = HyDEAgent()
        except Exception:
            pass

        try:
            from .memory_agent import MemoryAgent
            self.memory = MemoryAgent()
        except Exception:
            pass

        self.documents: Dict[str, dict] = {}

    def _retry(self, func, *args, **kwargs):
        """Retry with exponential backoff"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES} after {delay}s: {e}")
                    time.sleep(delay)
        raise last_error

    async def ingest_with_progress(self, file_bytes: bytes, filename: str, progress_callback: Callable) -> dict:
        """Ingest a document with progress reporting via callback"""
        doc_id = str(uuid.uuid4())
        logger.info(f"[ORCH] Starting ingest for {filename} (id={doc_id})")

        # Step 1: Parsing (10%)
        await progress_callback("parsing", 5, f"Reading {len(file_bytes)} bytes")
        await progress_callback("parsing", 10, "Parsing document structure")

        # Step 2: Ingestion (10-30%)
        await progress_callback("chunking", 15, "Loading document")
        t0 = time.time()
        chunks = await self._retry(self.ingestion.process, file_bytes, filename)
        ingestion_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Ingestion completed in {ingestion_time:.0f}ms ({len(chunks)} chunks)")

        # Step 3: Embedding (30-90%) - with batch progress
        total_chunks = len(chunks)
        await progress_callback("embedding", 30, f"Starting embedding {total_chunks} chunks")

        async def embedding_progress(batch_num: int, total_batches: int, chunks_done: int):
            pct = 30 + (50 * chunks_done // total_chunks)
            await progress_callback("embedding", pct,
                f"Embedding batch {batch_num}/{total_batches} ({chunks_done}/{total_chunks} chunks)")

        t0 = time.time()
        await self._retry(self.embedding.process_with_progress, chunks, doc_id, embedding_progress)
        embedding_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Embedding completed in {embedding_time:.0f}ms")

        # Step 4: Storing (90-95%)
        await progress_callback("storing", 92, "Saving to vector database")

        # Step 5: Finalizing (95-100%)
        self.documents[doc_id] = {
            "id": doc_id,
            "filename": filename,
            "uploaded_at": time.time(),
            "chunks_count": len(chunks),
        }

        await progress_callback("finalizing", 98, "Finalizing index")
        await progress_callback("complete", 100, f"Indexed {len(chunks)} chunks")

        return {
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks),
            "status": "indexed",
        }

    async def ingest(self, file: UploadFile) -> dict:
        """Ingest a document: load → chunk → embed → store (legacy, no progress)"""
        doc_id = str(uuid.uuid4())
        filename = file.filename or "unknown"

        logger.info(f"[ORCH] Starting ingest for {filename} (id={doc_id})")

        file_bytes = await file.read()

        t0 = time.time()
        chunks = await self._retry(self.ingestion.process, file_bytes, filename)
        ingestion_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Ingestion completed in {ingestion_time:.0f}ms")

        t0 = time.time()
        await self._retry(self.embedding.process, chunks, doc_id)
        embedding_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Embedding completed in {embedding_time:.0f}ms")

        self.documents[doc_id] = {
            "id": doc_id,
            "filename": filename,
            "uploaded_at": time.time(),
            "chunks_count": len(chunks),
        }

        return {
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks),
            "status": "indexed",
        }

    async def chat(self, query: str, history: List[Dict], use_hyde_fallback: bool = True) -> dict:
        """Process a chat query: retrieve → optional HyDE → synthesize"""
        logger.info(f"[ORCH] Processing chat query: {query[:50]}...")

        t0 = time.time()
        retrieved = await self._retry(self.retrieval.process, query)
        retrieval_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Retrieval completed in {retrieval_time:.0f}ms")

        # Optional cross-encoder reranking
        rerank_time = 0
        if self.reranker and self.reranker.reranker and retrieved:
            t0 = time.time()
            retrieved = await self.reranker.process(query, retrieved, top_k=5)
            rerank_time = (time.time() - t0) * 1000
            logger.info(f"[ORCH] Reranking completed in {rerank_time:.0f}ms")

        # Optional HyDE query expansion for complex/ambiguous queries
        hyde_embedding = None
        use_hyde = use_hyde_fallback and os.getenv("HYDE_ENABLED", "true").lower() != "false"
        if use_hyde and self.hyde:
            try:
                hyde_result = await self.hyde.process(query)
                hyde_embedding = hyde_result.get("hypothetical_embedding")
                if hyde_embedding:
                    logger.info("[ORCH] HyDE expansion done, re-retrieving with hypothetical embedding")
                    t0 = time.time()
                    retrieved = await self._retry(self.retrieval.process, query, hyde_embedding=hyde_embedding)
                    retrieval_time += (time.time() - t0) * 1000
                    if self.reranker and self.reranker.reranker and retrieved:
                        retrieved = await self.reranker.process(query, retrieved, top_k=5)
            except Exception as e:
                logger.warning(f"[ORCH] HyDE failed: {e}")

        # Full synthesis for all cases (direct or after HyDE)
        t0 = time.time()
        result = await self._retry(self.synthesis.process, query, retrieved, history)
        synthesis_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Synthesis completed in {synthesis_time:.0f}ms")

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "unverified_citations": result.get("unverified_citations", []),
            "latency_ms": {
                "retrieval": round(retrieval_time),
                "rerank": round(rerank_time) if rerank_time else None,
                "synthesis": round(synthesis_time),
            },
        }

    def list_documents(self) -> List[dict]:
        """List all indexed documents"""
        return list(self.documents.values())

    def delete_document(self, doc_id: str) -> dict:
        """Delete a document from the index"""
        if doc_id not in self.documents:
            return {"status": "not_found", "id": doc_id}

        filename = self.documents[doc_id]["filename"]
        deleted = self.embedding.delete_by_filename(filename)
        del self.documents[doc_id]
        return {"status": "deleted", "id": doc_id, "chunks_deleted": deleted}