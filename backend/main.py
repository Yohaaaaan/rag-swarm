"""
RAG Swarm - FastAPI Backend
Production-ready RAG system with swarm architecture
"""
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from agents import OrchestratorAgent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rag-swarm")

orchestrator: OrchestratorAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    logger.info("Starting RAG Swarm backend...")
    orchestrator = OrchestratorAgent()
    yield
    logger.info("Shutting down RAG Swarm backend...")


app = FastAPI(
    title="RAG Swarm",
    description="Production-ready RAG system with swarm architecture",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.0f}ms)")
    return response


@app.get("/")
async def root():
    return {"status": "ok", "service": "RAG Swarm", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        result = await orchestrator.ingest(file)
        return result
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    history: list[dict] | None = None


@app.post("/chat")
async def chat(request: ChatRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    if not request.query:
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        result = await orchestrator.chat(request.query, request.history or [])
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        documents = orchestrator.list_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        result = orchestrator.delete_document(doc_id)
        return result
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)