# Contributing to RAG Swarm

RAG Swarm is **proprietary software** (see [LICENSE](LICENSE)). It is not an
open-source project and does not accept unsolicited public contributions.
This document describes the workflow for authorised collaborators.

## Before you start

Contributions are accepted only from people who have received prior written
authorisation from the owner. If you would like to collaborate, email
**yohanmichau1@gmail.com** first.

## Development workflow

1. **Branch** off `master` for every change:
   ```bash
   git checkout -b feat/short-description
   ```
2. **Set up** the backend and frontend as described in the [README](README.md#quick-start).
3. **Keep secrets out of git.** Never commit `.env`, API keys, or credentials.
   Only `.env.example` (placeholders) is tracked.
4. **Update the README** whenever behaviour, endpoints, configuration, or the
   tech stack change — the README is treated as living documentation.
5. **Run the tests** before opening a pull request:
   ```bash
   cd backend && pytest
   ```
6. **Open a pull request** into `master` with a clear description of the change
   and its motivation.

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add cross-encoder reranking to retrieval pipeline
fix: correct SSE progress percentage on large PDFs
docs: document OpenRouter chatbot configuration
chore: bump chromadb to 0.4.24
```

## Code style

- **Python** — follow PEP 8; keep agent modules single-responsibility.
- **JavaScript / React** — functional components and hooks; keep components
  focused and colocate component-specific CSS.

## Reporting bugs

Open an issue (if you have repository access) or email
**yohanmichau1@gmail.com** with reproduction steps, expected vs. actual
behaviour, and relevant logs (`backend/logs/rag-swarm.log`). For anything
security-related, follow [SECURITY.md](SECURITY.md) instead of filing a public
issue.
