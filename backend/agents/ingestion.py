"""
INGESTION AGENT
Handles document loading and preprocessing
Accepts: PDF, DOCX, TXT, HTML, Markdown
"""
import logging
from typing import List
from pathlib import Path
from io import BytesIO

from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    TextLoader,
    BSHTMLLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("rag-swarm.ingestion")

CHUNK_SIZE = 300
CHUNK_OVERLAP = 80


class IngestionAgent:
    """Loads documents and splits into chunks with metadata"""

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n\n", "\n\n", "; ", ", ", " ", ""],
            length_function=len,
        )
        self.loaders = {
            ".pdf": PyPDFLoader,
            ".docx": UnstructuredWordDocumentLoader,
            ".doc": UnstructuredWordDocumentLoader,
            ".txt": TextLoader,
            ".html": BSHTMLLoader,
            ".htm": BSHTMLLoader,
        }

    def _get_loader(self, file_path: Path):
        ext = file_path.suffix.lower()
        loader_class = self.loaders.get(ext)
        if not loader_class:
            raise ValueError(f"Unsupported file type: {ext}")
        return loader_class

    async def process(self, file_bytes: bytes, filename: str) -> List[Document]:
        """Load and chunk a document"""
        logger.info(f"Ingesting document: {filename}")

        file_path = Path(filename)
        ext = file_path.suffix.lower()

        if ext not in self.loaders:
            raise ValueError(f"Unsupported file type: {ext}")

        loader_class = self._get_loader(file_path)

        try:
            with BytesIO(file_bytes) as f:
                temp_path = f"/tmp/{filename}"
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(file_bytes)
                loader = loader_class(temp_path)

            documents = loader.load()

            chunks = []
            for doc_idx, doc in enumerate(documents):
                pdf_page = doc.metadata.get("page", 0) if "page" in doc.metadata else 0

                chunked = self.text_splitter.split_documents([doc])

                for chunk_idx, chunk in enumerate(chunked):
                    chunk.metadata = {
                        "filename": filename,
                        "page_number": pdf_page,  # real PDF page number
                        "chunk_index": chunk_idx,  # index within this page's chunks
                        "source": f"{filename}:p{pdf_page}:{chunk_idx}",
                    }
                    chunks.append(chunk)

            logger.info(f"Ingested {filename}: {len(chunks)} chunks created")
            return chunks

        except Exception as e:
            logger.error(f"Failed to ingest {filename}: {e}")
            raise