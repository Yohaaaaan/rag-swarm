# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in RAG Swarm, please report it
privately. **Do not open a public issue or pull request** for security
matters.

- **Email:** yohanmichau1@gmail.com
- **Subject:** `SECURITY: RAG Swarm`

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce (proof of concept if available).
- Affected component(s), endpoint(s), or file(s).
- Any suggested remediation.

You can expect an initial acknowledgement within **72 hours**. Please allow a
reasonable period for a fix to be developed and deployed before any public
disclosure.

## Scope

This policy covers the application code in this repository (FastAPI backend and
React/Vite frontend). Vulnerabilities in third-party dependencies or hosted
model providers (OpenAI, Mistral, OpenRouter) should be reported to those
vendors directly, though you are welcome to notify us as well.

## Handling secrets

- API keys and credentials must **never** be committed. Only `.env.example`
  (with placeholder values) is tracked; real `.env` files are git-ignored.
- If a secret is ever committed, rotate it immediately and notify
  yohanmichau1@gmail.com.
- The backend calls external LLM/embedding providers — treat all API keys as
  sensitive and store them only in environment variables.
