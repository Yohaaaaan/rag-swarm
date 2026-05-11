# RAG Swarm - Project Memory

## Project Context

**Type**: Production-ready RAG (Retrieval-Augmented Generation) system
**Stack**: FastAPI + ChromaDB + LangChain (backend) | React 18 + Vite (frontend)
**LLM**: DeepSeek V3 via DeepInfra API | **Embedding**: OpenAI text-embedding-3-small
**Purpose**: Fiverr portfolio demo + service product for businesses

**Repository**: https://github.com/Yohaaaaan/rag-swarm

## Architecture

5-agent swarm:
- **INGESTION** → PDF/DOCX/TXT/HTML/MD → chunks (500 chars, 50 overlap)
- **EMBEDDING** → OpenAI text-embedding-3-small → ChromaDB
- **RETRIEVAL** → hybrid search (cosine 0.7 + BM25 0.3) → top-5
- **SYNTHESIS** → DeepSeek V3 via DeepInfra → answers with citations
- **ORCHESTRATOR** → pipeline coordination, retry (3x), latency logging

## Important Reminders

### README Maintenance (OBLIGATOIRE)

Ce projet nécessite une MAJ du README à chaque commit. Avant chaque commit :

1. Vérifier que le README reflète l'état actuel du code
2. Si modifications : mettre à jour README AVANT de commiter
3. Cette règle est permanente et s'applique à TOUS les contributeurs

**Pourquoi** : Le README sert de documentationlive pour les clients Fiverr et prospects. Un README obsolète = perte de crédibilité.

### API Keys Required

```
OPENAI_API_KEY=...        # Pour embeddings (text-embedding-3-small)
DEEPINFRA_API_KEY=...     # Pour DeepSeek V3
```

## File Structure

```
rag-swarm/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── agents/           # 5 agent modules
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/   # ChatPanel, DocumentPanel, SourceCitation
│   │   └── index.css      # Dark mode CSS
│   ├── package.json
│   └── vite.config.js
└── README.md             # MAJ OBLIGATOIRE à chaque commit
```

## Superpowers Skills

Ce projet utilise le plugin [superpowers](https://github.com/obra/superpowers) avec ses 14 skills. Ils sont chargés automatiquement au démarrage de session via un SessionStart hook.

**Auto-exécution:** OUI - via le hook `session-start` qui injecte `using-superpowers`. Ce skill ordonne d'invoquer TOUT skill pertinent AVANT toute action. C'est une exécution "soft" - l'agent décide selon le contexte.

| Skill | Quand l'invoquer | Auto? |
|-------|------------------|-------|
| `brainstorming` | Avant tout travail créatif (features, composants, modifications) | ✅ via hook |
| `test-driven-development` | Avant d'écrire du code | ✅ via hook |
| `systematic-debugging` | Quand bug, test failure, ou comportement inattendu | ✅ via hook |
| `verification-before-completion` | Avant de claimer "c'est fini" ou commit | ✅ via hook |
| `executing-plans` | Pour exécuter un plan écrit | Manuel |
| `subagent-driven-development` | Pour exécuter un plan avec subagents | Manuel |
| `finishing-a-development-branch` | À la fin d'un feature branch | Manuel |
| `requesting-code-review` | Avant de merger | Manuel |
| `receiving-code-review` | Quand on reçoit du feedback | Manuel |
| `dispatching-parallel-agents` | Pour 3+ tâches indépendantes | Manuel |
| `writing-plans` | Après brainstorming, avant code | Manuel |
| `writing-skills` | Pour créer/modifier un skill | Manuel |
| `using-git-worktrees` | Pour isoler le workspace | Manuel |
| `using-superpowers` | Bootstrap - chargé au startup | ✅ auto |

**Règle:** Si un skill a 1% de chance d'appliquer, je DOIS l'invoquer. Pas d'exception.

## Status

- Backend: fully implemented, validated (2 fixes during superval)
- Frontend: fully implemented, builds clean (147 kB JS)
- GitHub: 5 commits pushed
- Superval: PASS (10/10 acceptance criteria)

## Running

```bash
# Backend
cd backend && pip install -r requirements.txt && cp .env.example .env
# Edit .env with API keys
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```