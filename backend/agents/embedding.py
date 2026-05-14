"""
EMBEDDING AGENT
Converts chunks to vectors using OpenAI text-embedding-3-small
Stores in ChromaDB with batch processing
"""
import logging
import os
from typing import List, Callable

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import chromadb

logger = logging.getLogger("rag-swarm.embedding")

BATCH_SIZE = 100
COLLECTION_NAME = "rag_swarm_docs"


class EmbeddingAgent:
    """Embeds document chunks and stores in ChromaDB"""

    def __init__(self, persist_directory: str = "./vectorstore"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key,
        )
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_directory)

        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def process_with_progress(self, documents: List[Document], doc_id: str,
                                     progress_callback: Callable) -> int:
        """Embed documents with progress reporting"""
        logger.info(f"Embedding {len(documents)} chunks for doc_id={doc_id}")

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = [f"{doc_id}_{i}" for i in range(len(documents))]

        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i : i + BATCH_SIZE]
            batch_metadatas = metadatas[i : i + BATCH_SIZE]
            batch_ids = ids[i : i + BATCH_SIZE]

            embeddings = self.embeddings.embed_documents(batch_texts)

            self.collection.add(
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )

            batch_num = i // BATCH_SIZE + 1
            chunks_done = min(i + BATCH_SIZE, len(texts))
            logger.info(f"Embedded batch {batch_num}/{total_batches} ({chunks_done}/{len(texts)} chunks)")

            if progress_callback:
                await progress_callback(batch_num, total_batches, chunks_done)

        logger.info(f"Successfully embedded {len(documents)} chunks")
        return len(documents)

    async def process(self, documents: List[Document], doc_id: str) -> int:
        """Embed documents and store in ChromaDB (no progress)"""
        logger.info(f"Embedding {len(documents)} chunks for doc_id={doc_id}")

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = [f"{doc_id}_{i}" for i in range(len(documents))]

        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i : i + BATCH_SIZE]
            batch_metadatas = metadatas[i : i + BATCH_SIZE]
            batch_ids = ids[i : i + BATCH_SIZE]

            embeddings = self.embeddings.embed_documents(batch_texts)

            self.collection.add(
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )

            logger.info(f"Embedded batch {i//BATCH_SIZE + 1} ({len(batch_texts)} chunks)")

        logger.info(f"Successfully embedded {len(documents)} chunks")
        return len(documents)

    def get_count(self) -> int:
        """Get total number of embedded chunks"""
        return self.collection.count()

    def delete_by_filename(self, filename: str) -> int:
        """Delete all chunks belonging to a given filename. Returns count deleted."""
        all_data = self.collection.get()
        ids_to_delete = [
            mid for mid, meta in zip(all_data["ids"], all_data["metadatas"])
            if meta.get("filename") == filename
        ]
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} chunks for {filename}")
        return len(ids_to_delete)