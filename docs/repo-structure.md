# Repo Structure (Deliverable 2)

Monorepo, one compose stack, one `.env`. Directories marked *(phase 4+)* are
where later deliverables land — they don't exist yet.

```
jarvis/
├── docker-compose.yml          # prod-shaped base stack
├── docker-compose.dev.yml      # dev override: hot reload, Vite dev server, exposed ports
├── .env.example                # every variable documented; copy to .env (git-ignored)
├── Makefile                    # make prod | prod-home | dev | down | logs | secrets
│
├── docs/
│   ├── architecture.md         # deliverable 1
│   ├── repo-structure.md       # this file
│   └── runbooks/               # (phases 6–9) hardening, migration, backup, adding-an-agent
│
├── deploy/
│   ├── caddy/
│   │   ├── Dockerfile          # multi-stage: build frontend → bake into Caddy image
│   │   └── Caddyfile           # TLS, SPA serving, /api + /ws proxy, traces subdomain
│   └── postgres/
│       └── init-langfuse.sh    # creates Langfuse's DB in the shared instance
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml          # src layout, hatchling; deps grow per phase
│   └── src/jarvis/
│       ├── main.py             # app factory, structlog setup, /api/health
│       ├── config.py           # pydantic-settings, env-prefixed JARVIS_*
│       ├── api/                # (phase 4+) routers: auth, agents, runs, websocket
│       ├── core/               # (phase 4) the shared framework — THE important package
│       │   ├── agent.py        #   BaseAgent scaffold (LangGraph graph builder)
│       │   ├── registry.py     #   tool registry + agent-as-tool
│       │   ├── memory.py       #   namespaced shared memory over Postgres
│       │   ├── llm.py          #   LiteLLM Router: aliases, local-first, fallbacks
│       │   ├── scheduler.py    #   APScheduler wiring, manifest-declared cron triggers
│       │   └── tracing.py      #   Langfuse instrumentation helpers
│       ├── tools/              # (phase 4+) shared tool implementations (web, gmail, files, git)
│       ├── agents/             # (phase 5+) one package per agent
│       │   ├── research/       #   graph.py + manifest.py + agent-specific prompts
│       │   ├── personal/
│       │   └── dev/
│       ├── db/                 # (phase 4) SQLAlchemy models, session, alembic migrations
│       └── tests/
│
└── frontend/
    ├── package.json            # React 18 + Vite 5 + TypeScript
    ├── vite.config.ts          # dev proxy for /api and /ws
    └── src/                    # dashboard: agent status, chat, run history (grows per phase)
```

## Conventions

- **Framework vs. agents:** anything two agents would both need goes in
  `core/` or `tools/`, never inside an agent package. An agent package
  contains only its graph, its manifest (name, description, tool scopes,
  cron triggers, model aliases), and its prompts.
- **Config:** all runtime config via environment (`pydantic-settings`),
  all env vars documented in `.env.example`. No config files inside images.
- **Migrations:** schema changes only via Alembic; `alembic upgrade head`
  runs on backend startup.
- **Images:** frontend is compiled into the Caddy image (no Node in prod);
  backend is a single image reused by dev (with source bind-mounted and
  `--reload`) and prod.

## Day-one commands

```bash
cp .env.example .env && make secrets   # paste generated values into .env
make dev                               # local: http://localhost:5173
make prod                              # VPS:   https://jarvis.<domain>
make prod-home                         # home server: same + Ollama
```
