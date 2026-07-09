# RAG Swarm — Agent Guide (CLAUDE.md)

Guidance for AI coding agents working in this repo. Everything here is verified
against the real code — keep it that way when you change behaviour.

## What this is

A proprietary, production-oriented **Retrieval-Augmented Generation** system:
upload documents, ask questions, get answers grounded **only** in the corpus,
with source citations. A FastAPI backend fans work out to a small "swarm" of
single-responsibility agents; a React + Vite frontend drives it.

- **Repository**: https://github.com/Yohaaaaan/rag-swarm (private)
- **License**: Proprietary — All rights reserved (see `LICENSE`).

## CRITICAL: repo layout & symlinks

The git repo root is `/home/opc/rag-swarm/` and holds **only docs, config and
scripts**. The application code lives on a data partition and is exposed through
symlinks (created by `SETUP.sh`):

| Path in repo | Real target |
|--------------|-------------|
| `backend/`   | `/mnt/data/rag-swarm/backend/` |
| `frontend/`  | `/mnt/data/rag-swarm/frontend/` |
| `data/`      | `/mnt/data/rag-swarm/data/` |
| `logs/`      | `/mnt/data/rag-swarm-logs/logs/` |

Consequences for agents:
- **`git status` will not show edits to `backend/` or `frontend/`** — those trees
  are outside the repo working directory. They are **not version-controlled here.**
- Editing files under `backend/`/`frontend/` edits the live `/mnt/data` copies.
- Do **not** try to `git add` application code from this repo; only docs/config
  (`README.md`, `CLAUDE.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `.env.example`, `rag-nginx.conf`, `SETUP.sh`, `docs/`) are tracked.
- On a fresh machine, run `SETUP.sh` (or repoint the symlinks) before starting.

## Tech stack (real)

- **Backend**: FastAPI + Uvicorn, Python (live venv is **3.11**; requirements
  header aspires to 3.13 for cross-encoder/torch). Raw `httpx` for LLM calls
  (no `mistralai` SDK).
- **Vector DB**: ChromaDB persistent, at `backend/vectorstore/`. Two collections:
  `rag_swarm_docs` (main RAG) and `solenta` (chatbot layer).
- **Embeddings**: OpenAI `text-embedding-3-small` (1536 dims).
- **Synthesis (default `/chat`)**: **Mistral `mistral-large-latest`** via
  `agents/synthesis.py`. Needs `MISTRAL_API_KEY`.
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` via the `rerankers` lib.
  **Needs `torch`, which is NOT in `requirements.txt`** → at runtime the reranker
  self-disables (`self.reranker = None`) and reranking is silently skipped.
- **Chatbot layer (`/chatbot/*`)**: OpenRouter, default `google/gemini-2.5-flash`.
- **Frontend**: React 18 + Vite 5, plain `fetch`, hand-written dark CSS
  (no UI framework).

## Commands

```bash
# Backend (from repo root)
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # root .env.example is the good template; the
                                 # backend/.env.example is STALE — do not use it
uvicorn main:app --reload --port 8000     # http://localhost:8000, docs at /docs
pytest                           # test suite (see caveats below)

# Frontend (from repo root)
cd frontend
npm install
npm run dev                      # http://localhost:5173 (proxies /api → :8000)
npm run build                    # → frontend/dist  (no lint script exists)
```

Production reference: `rag-nginx.conf` serves `frontend/dist` and proxies
`/rag/api/` → `127.0.0.1:8000`.

## Architecture / pipeline

`backend/main.py` builds the FastAPI app and, in its lifespan, picks the
orchestrator from `USE_LANGGRAPH` (default false).

- **Default path** (`OrchestratorAgent`, `agents/orchestrator.py`):
  `retrieve → optional rerank(top_k=5) → optional HyDE re-retrieve → Mistral synthesis`,
  with 3× retry + backoff and per-agent latency logging.
- **Optional Self-RAG path** (`LangGraphOrchestrator`, `agents/graph.py`,
  `USE_LANGGRAPH=true`): LangGraph `StateGraph`
  `retrieve → rerank → synthesize → reflect → (retry)`. **This path swaps synthesis
  to `InstructorSynthesisAgent`**, which despite its name is a **DeepInfra
  `deepseek-ai/DeepSeek-V4-Flash`** client and **requires `DEEPINFRA_API_KEY`**
  (absent from the shipped `.env`) — so this path is effectively broken unless you
  add that key; it falls back to Mistral on failure. `langgraph` core is also not
  pinned in requirements (only `langgraph-sdk`), so `LANGGRAPH_AVAILABLE` may be false.

Agents (`backend/agents/`): `ingestion` (loaders + `RecursiveCharacterTextSplitter`,
**chunk 300 / overlap 80**), `embedding`, `retrieval` (hybrid cosine + hand-rolled
BM25, `SEMANTIC_WEIGHT=0.7`, `TOP_K` default 5 / `.env` 10), `reranker`, `synthesis`
(Mistral), `instructor_synthesis` (DeepInfra), `hyde`, `memory_agent` (Mem0, only in
the LangGraph path), `graph`, `orchestrator`. **Dead code**: `openrouter_llm.py` and
`chatbot_synthesis.py` are not imported — the `/chatbot/chat` route inlines the same
OpenRouter logic in `main.py`.

## API surface (backend, all under `/api` via the Vite proxy)

`GET /` · `GET /health` · `POST /ingest` (multipart, async → `{job_id}`) ·
`GET /ingest/{id}/stream` (**SSE**) · `GET /ingest/{id}/status` (polling) ·
`GET /logs` · `GET /logs/jobs` · `POST /chat` (`{query, history}` →
`{answer, sources[], unverified_citations[], latency_ms}`) · `GET /documents` ·
`DELETE /documents/{id}` · `POST /chatbot/chat` · `GET /chatbot/health` ·
`POST /contact` · `POST /callback-request` (contact/callback only **log**; no
storage/email).

Frontend note: the UI shows a 5-step ingest progress
(Parsing → Chunking → Embedding → Storing → Finalizing) but consumes it by
**polling `/api/ingest/{id}/status` every second** — it does **not** use the SSE
endpoint or `EventSource` (there is a vestigial unused `eventSourceRef` in `App.jsx`).

## Config / env

No `config.py` — config is scattered `os.getenv`. Root `.env.example` is the
source of truth. Keys/vars actually read: `OPENAI_API_KEY` (required),
`MISTRAL_API_KEY` (required), `OPENROUTER_API_KEY`/`OPENROUTER_MODEL`/
`OPENROUTER_API_BASE` (chatbot), `DEEPINFRA_API_KEY` (LangGraph only),
`CHROMA_PERSIST_DIR`, `HYDE_ENABLED` (`.env`=false, code default true),
`RETRIEVAL_TOP_K`, `RETRIEVAL_SEMANTIC_WEIGHT`, `USE_LANGGRAPH`, `PORT`.
`SYNTHESIS_TEMPERATURE` and `LOG_LEVEL` are **read but not wired in** (synthesis
hardcodes temperature 0.5; logging is fixed at INFO with a 5 MB
`RotatingFileHandler`, `backupCount=3`, at `backend/logs/rag-swarm.log`).

## Gotchas / pitfalls (verified)

- **Symlinks**: `backend/`/`frontend/` edits are invisible to `git` here and live
  on `/mnt/data`. Never `git add -A` from this repo.
- **`.claude/AGENTS.md`** is an untracked user file — **never stage or modify it.**
- **`backend/.env.example` is stale** (only `OPENAI_API_KEY`/`DATABASE_URL`/
  `LOG_LEVEL`, none of which reflect the real vars). Use the **root** `.env.example`.
- **Reranker** needs `torch` (not in requirements) → usually inactive.
- **LangGraph/DeepInfra**: `USE_LANGGRAPH=true` needs `DEEPINFRA_API_KEY`; without
  it the Self-RAG path errors and falls back to Mistral.
- **Tests are partly stale**: `tests/test_ingestion.py` uses 500/50 chunking (prod is
  300/80); `tests/test_synthesis.py` asserts a DeepInfra base URL and skips unless
  `DEEPINFRA_API_KEY` is set, but the real `SynthesisAgent` uses Mistral. Fix tests
  to match code, not the reverse, unless changing behaviour deliberately.
- **Ingestion** writes each upload to `/tmp/{filename}` before loading (collision/
  security consideration for multi-tenant use).
- **Secrets**: never commit `.env` or real keys. Only `.env.example` placeholders
  are tracked. Keep `git ls-files | grep -Ei '\.env$|\.key|\.pem|credential'` empty.

## Documentation rule (permanent)

The README is treated as **living documentation** (it is the client/portfolio face
of the project). If you change behaviour, endpoints, models, config, or the tech
stack, **update `README.md` (and this file) in the same change** before committing.
Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `perf:`, `test:`).
