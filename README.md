# Jarvis

Self-hosted, Dockerized multi-agent environment: LangGraph agents behind a
FastAPI backend and React dashboard, routed through LiteLLM to paid APIs or a
home-server Ollama, traced with self-hosted Langfuse, fronted by Caddy with
automatic HTTPS. Portable between a VPS and a home server by moving volumes
and repointing DNS.

- [Architecture](docs/architecture.md)
- [Repo structure & conventions](docs/repo-structure.md)
- [Deploy & hardening](docs/runbooks/hardening.md)
- [Migration VPS ↔ home server](docs/runbooks/migration.md)
- [Adding a new agent](docs/runbooks/adding-an-agent.md)
- [Backups & restore](docs/runbooks/backup.md)

## Quick start

```bash
cp .env.example .env
make secrets        # generate values, paste into .env, fill in domain + API keys
make prod           # VPS (no local models)
make prod-home      # home server (adds Ollama)
make dev            # local development at http://localhost:5173
```
