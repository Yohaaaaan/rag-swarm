# RAG Swarm

**AI-powered document Q&A** — upload your documents and get instant, source-cited answers from a multi-agent Retrieval-Augmented Generation pipeline.

![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-Proprietary-red)

RAG Swarm is a production-oriented **Retrieval-Augmented Generation** system. Drop in a document (PDF, Word, TXT, HTML, Markdown), ask a question in plain language, and the system answers **only** from your documents — with exact source citations, relevance scores, and per-agent latency. Under the hood it runs a small "swarm" of specialised agents (ingestion, embedding, hybrid retrieval, cross-encoder reranking, synthesis) coordinated by an orchestrator, with an optional Self-RAG graph mode for higher-fidelity answers.

---

## Table of Contents

- [Why RAG Swarm](#why-rag-swarm)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Features](#features)
- [Project Structure](#project-structure)
- [Running the Demo](#running-the-demo)
- [License](#license)

---

## Why RAG Swarm

Large language models hallucinate when asked about private or niche content they were never trained on. RAG Swarm grounds every answer in **your** corpus: it retrieves the most relevant passages, reranks them, and only then asks the LLM to synthesise a response — returning the supporting sources alongside the answer so a human can verify.

**Representative use cases**

- Contract analysis — locate clauses, obligations, and deadlines
- Research paper Q&A — summarise, compare, and extract findings
- Internal knowledge bases — employee handbooks, SOPs, runbooks
- Financial document review — reports, filings, agreements

---

## Architecture

The backend is a FastAPI service that fans work out to purpose-built agents. An **orchestrator** owns the pipeline, logging latency and retrying on transient failures; an optional **LangGraph** orchestrator (`USE_LANGGRAPH=true`) runs a Self-RAG / Corrective-RAG state machine instead.

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                        │
│   Drag & drop upload  │  Chat interface  │  Lottie / WaveSurfer UI │
└──────────────────────────────────────────────────────────────────┘
                               │ HTTP (/api → :8000, proxied)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + Python)                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATOR                             │   │
│  │   Pipeline control • latency logging • retries • SSE jobs  │   │
│  └────────────────────────────────────────────────────────────┘   │
│      │          │          │            │            │            │
│      ▼          ▼          ▼            ▼            ▼            │
│  ┌────────┐ ┌────────┐ ┌─────────┐ ┌─────────┐ ┌────────────┐    │
│  │INGEST  │ │EMBED   │ │RETRIEVE │ │RERANK   │ │SYNTHESISE  │    │
│  │PDF/DOCX│ │OpenAI  │ │hybrid   │ │cross-   │ │Mistral     │    │
│  │→chunks │ │→vectors│ │cos+BM25 │ │encoder  │ │→answer+cite│    │
│  └────────┘ └────────┘ └─────────┘ └─────────┘ └────────────┘    │
│                            │                                       │
│                            ▼                                       │
│                     ┌─────────────┐   (optional: HyDE query        │
│                     │  ChromaDB   │    expansion • Mem0 memory •    │
│                     │ (persistent)│    LangGraph Self-RAG mode)     │
│                     └─────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

### Agent responsibilities

| Agent | Role | Details |
|-------|------|---------|
| **Ingestion** | Document processing | PDF / DOCX / TXT / HTML / MD → chunks (500 chars, 50 overlap) |
| **Embedding** | Vector generation | OpenAI `text-embedding-3-small` (1536 dims) → ChromaDB |
| **Retrieval** | Semantic search | Hybrid: cosine similarity (0.7) + BM25 keyword (0.3) |
| **Reranker** | Precision boost | Cross-encoder `ms-marco-MiniLM-L-6-v2` re-scores top candidates |
| **Synthesis** | Answer generation | Mistral `mistral-large-latest`, cites sources, keeps chat history |
| **HyDE** *(opt.)* | Query expansion | Hypothetical Document Embeddings for hard queries (~+11 s) |
| **Memory** *(opt.)* | Conversation memory | Mem0-backed context across turns |
| **Orchestrator** | Pipeline control | Error handling, retries, per-agent latency logging |

> A secondary **chatbot** layer (`/chatbot/*`) reuses the same ChromaDB together with an OpenRouter-hosted model (default `google/gemini-2.5-flash`) for a lightweight, torch-free assistant experience.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend framework | FastAPI + Uvicorn (Python 3.11+, dev tested on 3.13) |
| Vector database | ChromaDB (persistent) |
| Document loaders / RAG glue | LangChain + LangGraph |
| Embeddings | OpenAI `text-embedding-3-small` |
| Reranking | `rerankers` (cross-encoder, transformers) |
| Synthesis LLM | Mistral `mistral-large-latest` |
| Chatbot LLM | OpenRouter (default `google/gemini-2.5-flash`) |
| Conversation memory | Mem0 (`mem0ai`) |
| Streaming | Server-Sent Events (`sse-starlette`) |
| Frontend framework | React 18 |
| Build tool | Vite 5 |
| UI motion | `lottie-web`, `wavesurfer.js` |

---

## Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended for full cross-encoder support)
- Node.js 18+
- An OpenAI API key (embeddings)
- A Mistral API key (synthesis)
- *(optional)* An OpenRouter API key (chatbot layer)

### 1. Clone

```bash
git clone git@github.com:Yohaaaaan/rag-swarm.git
cd rag-swarm
```

### 2. Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                # then edit .env with your keys
uvicorn main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173 (Vite proxies `/api` → `http://localhost:8000`)

---

## Configuration

All configuration is via environment variables (loaded from `backend/.env`). See [`.env.example`](.env.example) for the full list. Highlights:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | ✅ | — | Embeddings (`text-embedding-3-small`) |
| `MISTRAL_API_KEY` | ✅ | — | Synthesis + HyDE (Mistral Large) |
| `OPENROUTER_API_KEY` | ⚪ | — | Chatbot layer (`/chatbot/*`) |
| `OPENROUTER_MODEL` | ⚪ | `google/gemini-2.5-flash` | Chatbot model id |
| `CHROMA_PERSIST_DIR` | ⚪ | project default | ChromaDB storage path |
| `USE_LANGGRAPH` | ⚪ | `false` | Enable Self-RAG / Corrective-RAG mode |
| `HYDE_ENABLED` | ⚪ | `false` | Enable HyDE query expansion (~+11 s latency) |
| `RETRIEVAL_TOP_K` | ⚪ | `10` | Chunks retrieved per query |
| `RETRIEVAL_SEMANTIC_WEIGHT` | ⚪ | `0.7` | Semantic vs. keyword balance (0.6–0.8) |
| `SYNTHESIS_TEMPERATURE` | ⚪ | `0.7` | Answer creativity (0.3 factual → 0.7 creative) |
| `PORT` | ⚪ | `8000` | Backend port |
| `LOG_LEVEL` | ⚪ | `INFO` | Logging verbosity |

> **Never commit real keys.** `.env` is git-ignored; only `.env.example` (placeholders) is tracked.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/ingest` | Upload a document → returns `{job_id}` (async) |
| `GET` | `/ingest/{job_id}/status` | Poll ingestion job status |
| `GET` | `/ingest/{job_id}/stream` | SSE progress stream |
| `POST` | `/chat` | Ask a question → `{answer, sources[], latency_ms}` |
| `GET` | `/documents` | List indexed documents |
| `DELETE` | `/documents/{id}` | Remove a document from the index |
| `GET` | `/logs` | Recent log lines |
| `GET` | `/logs/jobs` | Recent ingestion job events |
| `POST` | `/chatbot/chat` | Lightweight chatbot answer (OpenRouter) |
| `GET` | `/chatbot/health` | Chatbot layer health |
| `POST` | `/contact` | Log a contact-form submission |
| `POST` | `/callback-request` | Log a callback request |

### Example: chat request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the termination clause?", "history": []}'
```

```json
{
  "answer": "The termination clause (Section 7.2) states either party may terminate with 30 days written notice.",
  "sources": [
    {
      "filename": "contract.pdf",
      "page": 5,
      "excerpt": "7.2 Termination: Either party may terminate this agreement...",
      "relevance_score": 0.94
    }
  ],
  "latency_ms": { "retrieval": 127, "synthesis": 892 }
}
```

---

## Features

- **Document upload** — drag & drop, PDF/DOCX/TXT/HTML/MD, automatic chunking, real-time indexing progress.
- **Grounded chat** — conversational Q&A with context memory; answers derived only from your documents.
- **Source citations** — every answer lists filename, page, excerpt, and relevance score.
- **Hybrid retrieval + reranking** — cosine + BM25, then a cross-encoder for precision.
- **Optional Self-RAG** — LangGraph state machine for corrective retrieval (`USE_LANGGRAPH=true`).
- **Streaming progress (SSE)** — Parsing → Chunking → Embedding → Storing → Finalizing.
- **Document management** — list, inspect chunk counts, delete from the index.
- **Motion-rich UI** — Lottie animations and WaveSurfer audio-style visualisation, dark-mode design with CSS variables (no UI framework).
- **Logging & debugging** — rotating file logs (`backend/logs/rag-swarm.log`, 5 MB) plus `/logs` and `/logs/jobs` endpoints.

---

## Project Structure

```
rag-swarm/
├── backend/                     # FastAPI service (symlinked to a data partition)
│   ├── main.py                  # App + REST/SSE endpoints
│   ├── agents/
│   │   ├── ingestion.py         # Loading + chunking
│   │   ├── embedding.py         # OpenAI embeddings → ChromaDB
│   │   ├── retrieval.py         # Hybrid cosine + BM25
│   │   ├── reranker.py          # Cross-encoder reranking
│   │   ├── synthesis.py         # Mistral answer generation
│   │   ├── hyde.py              # Hypothetical Document Embeddings
│   │   ├── graph.py             # LangGraph Self-RAG orchestrator
│   │   ├── memory_agent.py      # Mem0 conversation memory
│   │   ├── openrouter_llm.py    # OpenRouter client (chatbot layer)
│   │   └── orchestrator.py      # Pipeline coordination + logging
│   ├── tests/                   # pytest suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # React + Vite app (symlinked to a data partition)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/          # ChatPanel, DocumentPanel, SourceCitation, WaveEffect
│   │   └── index.css            # Dark-mode CSS variables
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/                        # Design & performance notes
├── .env.example                 # Environment variable template
├── rag-nginx.conf               # Reference production reverse-proxy config
├── SETUP.sh                     # Partition-separation bootstrap
├── LICENSE
└── README.md
```

> **Note:** `backend/` and `frontend/` are symlinks into a data partition (`/mnt/data`) created by `SETUP.sh` — a deliberate partition-separation choice for this deployment. On a fresh machine, run `SETUP.sh` (or point the symlinks at your working copy) before starting the services.

---

## Running the Demo

1. Start the backend (`uvicorn main:app --reload --port 8000`).
2. Start the frontend (`npm run dev`) and open http://localhost:5173.
3. Drag a PDF/DOCX into the upload panel and watch the 5-step SSE progress.
4. Ask a question in the chat panel; inspect the cited sources beneath each answer.

For production, `rag-nginx.conf` shows a reference reverse-proxy layout serving the built frontend (`frontend/dist`) and proxying `/api` to the backend.

---

## License

**Proprietary — All rights reserved.** © 2026 Yohan Michau. See [LICENSE](LICENSE). This software is provided for evaluation and portfolio purposes only; no license to use, copy, modify, or distribute is granted without prior written permission.
