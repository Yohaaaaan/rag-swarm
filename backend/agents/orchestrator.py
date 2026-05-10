"""
ORCHESTRATOR AGENT
Coordinates the RAG pipeline: ingest → embed → retrieve → synthesize
Handles errors, retries, and latency logging
"""
import logging
import uuid
import time
from typing import List, Dict, Optional

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

    async def ingest(self, file: UploadFile) -> dict:
        """Ingest a document: load → chunk → embed → store"""
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

    async def chat(self, query: str, history: List[Dict]) -> dict:
        """Process a chat query: retrieve → synthesize"""
        logger.info(f"[ORCH] Processing chat query: {query[:50]}...")

        t0 = time.time()
        retrieved = await self._retry(self.retrieval.process, query)
        retrieval_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Retrieval completed in {retrieval_time:.0f}ms")

        t0 = time.time()
        result = await self._retry(self.synthesis.process, query, retrieved, history)
        synthesis_time = (time.time() - t0) * 1000
        logger.info(f"[ORCH] Synthesis completed in {synthesis_time:.0f}ms")

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "latency_ms": {
                "retrieval": round(retrieval_time),
                "synthesis": round(synthesis_time),
            },
        }

    def list_documents(self) -> List[dict]:
        """List all indexed documents"""
        return list(self.documents.values())

    def delete_document(self, doc_id: str) -> dict:
        """Delete a document from the index"""
        if doc_id in self.documents:
            del self.documents[doc_id]
            return {"status": "deleted", "id": doc_id}
        return {"status": "not_found", "id": doc_id}