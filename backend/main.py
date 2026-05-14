"""
RAG Swarm - FastAPI Backend
Production-ready RAG system with swarm architecture
"""
import asyncio
import logging
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from sse_starlette import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

from agents import OrchestratorAgent
from agents.graph import LangGraphOrchestrator

load_dotenv()

# Setup log directory
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging with file rotation + stdout
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()  # Clear any existing handlers

# File handler with rotation
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "rag-swarm.log"),
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
root_logger.addHandler(file_handler)

# Stream handler for stdout (visible in terminal)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
root_logger.addHandler(stream_handler)

logger = logging.getLogger("rag-swarm")

orchestrator: OrchestratorAgent | LangGraphOrchestrator | None = None
USE_GRAPH = os.getenv("USE_LANGGRAPH", "false").lower() in ("true", "1", "yes")

# Job tracking for async ingest progress
jobs: dict[str, dict] = {}

# Job event history for debugging
job_events: list[dict] = []  # [{timestamp, job_id, event, details}]


def add_job_event(job_id: str, event: str, details: str = ""):
    """Add event to job history"""
    job_events.append({
        "timestamp": datetime.now().isoformat(),
        "job_id": job_id,
        "event": event,
        "details": details,
    })
    # Keep only last 100 events
    if len(job_events) > 100:
        job_events.pop(0)


def update_job(job_id: str, **kwargs):
    """Update job fields atomically"""
    if job_id in jobs:
        jobs[job_id].update(kwargs)


async def run_ingest_job(job_id: str, file_bytes: bytes, filename: str):
    """Background task for document ingestion with progress reporting"""
    try:
        add_job_event(job_id, "STARTED", f"Starting ingest for {filename}")
        update_job(job_id, status="parsing", progress=0, step="Parsing document", message="Starting...")
        await asyncio.sleep(0.1)

        async def progress_callback(step: str, progress: float, message: str):
            update_job(job_id, step=step, progress=progress, message=message)
            add_job_event(job_id, step.upper(), message)
            await asyncio.sleep(0.05)

        result = await orchestrator.ingest_with_progress(file_bytes, filename, progress_callback)

        update_job(job_id, status="completed", progress=100, step="Complete",
                   message=f"Indexed {result['chunks_count']} chunks", result=result)
        add_job_event(job_id, "COMPLETED", f"Indexed {result['chunks_count']} chunks")
        logger.info(f"Job {job_id} completed: {result['chunks_count']} chunks")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job(job_id, status="failed", error=str(e), step="Error")
        add_job_event(job_id, "FAILED", str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    logger.info("Starting RAG Swarm backend...")
    if USE_GRAPH:
        logger.info("Using LangGraph Orchestrator (Self-RAG mode)")
        orchestrator = LangGraphOrchestrator()
    else:
        logger.info("Using standard OrchestratorAgent")
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded documents (accessible via URL)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


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
    """Start async ingest job, return job_id immediately"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        job_id = str(uuid.uuid4())
        filename = file.filename or "unknown"

        # Save file to uploads directory
        file_path = os.path.join(UPLOAD_DIR, filename)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Initialize job
        jobs[job_id] = {
            "job_id": job_id,
            "status": "started",
            "progress": 0,
            "step": "Initializing",
            "message": "Starting upload...",
            "filename": filename,
            "error": None,
            "result": None,
        }

        # Start background task
        asyncio.create_task(run_ingest_job(job_id, contents, filename))
        add_job_event(job_id, "UPLOADED", f"File saved, job started: {filename}")

        return {
            "job_id": job_id,
            "status": "started",
            "download_url": f"/uploads/{filename}",
        }
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ingest/{job_id}/stream")
async def ingest_stream(job_id: str):
    """SSE endpoint for progress updates"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_keepalive = asyncio.get_event_loop().time()
        while True:
            job = jobs.get(job_id)
            if not job:
                yield "event: error\ndata: Job not found\n\n"
                break

            status = job.get("status")
            if status == "completed":
                msg = job.get("message", "Done")
                yield f"event: complete\ndata: {msg}\n\n"
                break
            elif status == "failed":
                err = job.get("error", "Failed")
                yield f"event: error\ndata: {err}\n\n"
                break

            step = job.get("step", "Loading")
            progress = job.get("progress", 0)
            message = job.get("message", "")
            yield f"event: progress\ndata: {step}|{progress}|{message}\n\n"

            # Keep-alive every 5s to prevent Cloudflare/proxy timeouts
            now = asyncio.get_event_loop().time()
            if now - last_keepalive >= 5:
                yield ": keepalive\n\n"
                last_keepalive = now
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@app.get("/ingest/{job_id}/status")
async def ingest_status(job_id: str):
    """Get job status (polling fallback)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


# ==================== LOG ENDPOINTS ====================

@app.get("/logs")
async def get_logs():
    """Get recent log entries from file"""
    log_path = os.path.join(LOG_DIR, "rag-swarm.log")
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        # Return last 100 lines
        recent = lines[-100:] if len(lines) > 100 else lines
        return {
            "logs": [line.strip() for line in recent],
            "count": len(recent),
            "total": len(lines),
        }
    except FileNotFoundError:
        return {"logs": [], "count": 0, "total": 0, "error": "Log file not found"}


@app.get("/logs/jobs")
async def get_job_logs():
    """Get recent job events"""
    return {
        "events": job_events[-50:],  # Last 50 events
        "count": len(job_events),
    }


# =====================================================


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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)