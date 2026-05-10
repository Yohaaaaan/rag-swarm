# RAG Swarm

**AI-powered document Q&A system** — upload your documents and get instant answers with cited sources.

![Status](https://img.shields.io/badge/status-production--ready-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

## What is RAG Swarm?

RAG Swarm is a production-ready **Retrieval-Augmented Generation** system. Upload any document (PDF, Word, TXT, HTML, Markdown), and ask questions. The AI answers based only on your documents, citing exact sources.

**Demo use cases:**
- Contract analysis (find clauses, obligations, deadlines)
- Research paper Q&A (summarize, compare, extract findings)
- Internal knowledge bases (employee handbooks, procedures)
- Financial document review (reports, filings, agreements)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                     │
│    Document Upload (drag & drop)  │  Chat Interface (messages)     │
└─────────────────────────────────────────────────────────────────────┘
                                  │ HTTP
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + Python)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              ORCHESTRATOR AGENT                            │    │
│  │    Coordinates pipeline • Logs latency • Retries (3x)      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │              │              │              │              │
│         ▼              ▼              ▼              ▼              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐         │
│  │ INGESTION│  │EMBEDDING │  │RETRIEVAL │  │  SYNTHESIS   │         │
│  │ Agent    │  │ Agent    │  │ Agent    │  │  Agent       │         │
│  │          │  │          │  │          │  │              │         │
│  │PDF/DOCX  │  │OpenAI    │  │ChromaDB  │  │DeepSeek V3   │         │
│  │→ chunks  │  │→ vectors │  │hybrid    │  │→ answer      │         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘         │
│                         │                                           │
│                         ▼                                           │
│                  ┌─────────────┐                                    │
│                  │  ChromaDB   │                                    │
│                  │ (persistent)│                                    │
│                  └─────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Role | Details |
|-------|------|---------|
| **INGESTION** | Document processing | PDF/DOCX/TXT/HTML/MD → chunks (500 chars, 50 overlap) |
| **EMBEDDING** | Vector generation | OpenAI `text-embedding-3-small` (1536 dims) → ChromaDB |
| **RETRIEVAL** | Semantic search | Hybrid: cosine similarity (70%) + BM25 (30%) → top-5 |
| **SYNTHESIS** | Answer generation | DeepSeek V3 via DeepInfra, cites sources, max 10-turn history |
| **ORCHESTRATOR** | Pipeline control | Error handling, retries, latency logging per agent |

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend Framework | FastAPI | 0.109+ |
| Python | Python | 3.11+ |
| Vector Database | ChromaDB | 0.4+ |
| Document Loaders | LangChain | 0.1+ |
| Embedding Model | OpenAI text-embedding-3-small | - |
| LLM | DeepSeek V3 (DeepInfra) | - |
| Frontend Framework | React | 18+ |
| Build Tool | Vite | 5+ |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (for embeddings)
- DeepInfra API key (for DeepSeek V3 — free tier available)

### 1. Clone & Setup

```bash
git clone https://github.com/Yohaaaaan/rag-swarm.git
cd rag-swarm
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add:
#   OPENAI_API_KEY=sk-...
#   DEEPINFRA_API_KEY=...

# Start server
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend runs at: http://localhost:5173

## API Endpoints

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| POST | `/ingest` | Upload document | `multipart/form-data` with `file` | `{document_id, filename, chunks_count, status}` |
| POST | `/chat` | Ask question | `{query: string, history?: []}` | `{answer, sources[], latency_ms}` |
| GET | `/documents` | List documents | - | `{documents: [{id, filename, uploaded_at, chunks_count}]}` |
| DELETE | `/documents/{id}` | Remove document | - | `{status, id}` |

### Example: Chat Request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the termination clause?", "history": []}'
```

**Response:**
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
  "latency_ms": {
    "retrieval": 127,
    "synthesis": 892
  }
}
```

## Features

### ✅ Document Upload
- Drag & drop or click to upload
- Supports PDF, DOCX, TXT, HTML, Markdown
- Automatic chunking (500 chars, 50 overlap)
- Real-time indexing progress

### ✅ Chat Interface
- Conversational Q&A with context memory
- Last 10 conversation turns preserved
- "Thinking..." indicator during processing
- Message bubbles (user right, AI left)

### ✅ Source Citations
- Every answer cites exact sources
- Shows: filename, page number, relevance score
- Excerpt preview of source text
- Click to verify the context

### ✅ Document Management
- View all indexed documents
- See chunk count per document
- Delete documents from index
- Refresh document list

### ✅ Dark Mode UI
- Clean, minimal design
- CSS variables (no UI library)
- Responsive grid layout
- Professional color palette

## Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...        # OpenAI API key for embeddings
DEEPINFRA_API_KEY=...        # DeepInfra API key for DeepSeek V3

# Optional
PORT=8000                   # Backend port (default: 8000)
```

## Project Structure

```
rag-swarm/
├── backend/
│   ├── main.py              # FastAPI app + 4 endpoints
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── ingestion.py     # Document loading + chunking
│   │   ├── embedding.py     # OpenAI embeddings → ChromaDB
│   │   ├── retrieval.py     # Hybrid search (cosine + BM25)
│   │   ├── synthesis.py     # DeepSeek V3 answer generation
│   │   └── orchestrator.py  # Pipeline coordination + logging
│   ├── vectorstore/          # ChromaDB persistent storage (gitignored)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main layout
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx     # Chat UI + messages
│   │   │   ├── DocumentPanel.jsx # Upload + file list
│   │   │   └── SourceCitation.jsx # Source display
│   │   ├── main.jsx
│   │   └── index.css        # Dark mode CSS variables
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .claude/
│   └── CLAUDE.md            # Project memory (MAJ à chaque commit)
├── .gitignore
├── README.md                # This file (MAJ à chaque commit)
└── LICENSE
```

## Validation

| Check | Status |
|-------|--------|
| Structural (21 files) | ✅ PASS |
| Wiring (import chains) | ✅ PASS |
| Behavioral (2 fixes applied) | ✅ PASS |
| Superval acceptance | 10/10 ✅ |

See [.superval/report.md](.superval/report.md) for full validation details.

## License

MIT — use freely for portfolio, demos, and commercial projects.