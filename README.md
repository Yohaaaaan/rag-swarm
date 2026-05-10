# RAG Swarm

A production-ready RAG (Retrieval-Augmented Generation) system using a swarm of specialized agents. Built as a Fiverr portfolio demo and service product.

## Architecture

```
Frontend (React + Vite) → FastAPI Backend → Orchestrator → [Ingestion | Embedding | Retrieval | Synthesis] → ChromaDB
```

### Agents

- **INGESTION AGENT**: Handles PDF, DOCX, TXT, HTML, Markdown uploads. Chunks content (500 chars, 50 overlap).
- **EMBEDDING AGENT**: Converts chunks to vectors using OpenAI text-embedding-3-small.
- **RETRIEVAL AGENT**: Hybrid search (semantic + BM25) returning top-5 relevant chunks.
- **SYNTHESIS AGENT**: Generates answers using DeepSeek V3 via DeepInfra API.
- **ORCHESTRATOR AGENT**: Coordinates the pipeline with latency logging and error handling.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Python |
| Vector DB | ChromaDB (local, persistent) |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | DeepSeek V3 (DeepInfra) |
| Frontend | React 18 + Vite |

## Quick Start

### 1. Backend Setup

```bash
cd rag-swarm/backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your API keys
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd rag-swarm/frontend
npm install
npm run dev
```

### 3. Open Browser

- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

## Environment Variables

```env
OPENAI_API_KEY=sk-...      # For embeddings
DEEPINFRA_API_KEY=...      # For DeepSeek V3 LLM
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Upload and index documents |
| POST | `/chat` | Ask a question, get cited answer |
| GET | `/documents` | List indexed documents |
| DELETE | `/documents/{id}` | Remove document from index |

## Screenshot Placeholder

[Screenshot of the application will be added here]

## License

MIT