# CLAUDE.md

Guidance for AI coding agents (Claude Code and others) working in this repository.

**The full agent guide lives in [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — read it first.**

Fast facts (see `.claude/CLAUDE.md` for the details and gotchas):

- **What**: a proprietary RAG system — FastAPI backend "swarm" of agents + React 18 / Vite 5 frontend. See [`README.md`](README.md).
- **Symlinks (important)**: `backend/` and `frontend/` are **symlinks into `/mnt/data`** (`/mnt/data/rag-swarm/...`), created by `SETUP.sh`. That code is **not tracked in this repo** — `git status` won't show edits to it, and you must never `git add -A`/`.` here. Only docs & config are versioned.
- **Stack**: OpenAI `text-embedding-3-small` → ChromaDB; synthesis = **Mistral `mistral-large-latest`** (`/chat`); cross-encoder reranker (`rerankers`, needs `torch`); chatbot layer (`/chatbot/*`) = **OpenRouter `google/gemini-2.5-flash`**. Optional HyDE + Mem0 + LangGraph Self-RAG (the LangGraph path needs `DEEPINFRA_API_KEY`).
- **Run**: backend `cd backend && uvicorn main:app --reload --port 8000`; frontend `cd frontend && npm run dev` (Vite proxies `/api` → `:8000`). Copy the **root** `.env.example` to `backend/.env` (the `backend/.env.example` is stale).
- **Do not touch** the untracked user file `.claude/AGENTS.md`.
- **Docs rule**: update `README.md` and `.claude/CLAUDE.md` in the same change as any behaviour/API/model/config change. Conventional Commits.
