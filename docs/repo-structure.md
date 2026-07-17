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
│   ├── Dockerfile              # runs `alembic upgrade head` before uvicorn
│   ├── pyproject.toml          # src layout, hatchling; deps grow per phase
│   ├── alembic.ini / alembic/  # migrations (URL from JARVIS_DATABASE_URL)
│   └── src/jarvis/
│       ├── main.py             # app factory, structlog setup, lifespan wiring
│       ├── config.py           # pydantic-settings, env-prefixed JARVIS_*
│       ├── api/                # routers: agents, runs, websocket (auth arrives phase 6)
│       ├── core/               # the shared framework — THE important package
│       │   ├── agent.py        #   AgentManifest + BaseAgent (LangGraph tool-loop scaffold)
│       │   ├── registry.py     #   global tool registry (@tool decorator, scopes)
│       │   ├── memory.py       #   namespaced shared memory over Postgres
│       │   ├── llm.py          #   LiteLLM Router: fast/smart/local-bulk aliases, fallbacks
│       │   ├── runner.py       #   run lifecycle: DB rows, events, WS pubsub
│       │   ├── scheduler.py    #   APScheduler wiring, manifest-declared cron triggers
│       │   ├── checkpoint.py   #   LangGraph Postgres checkpointer lifecycle
│       │   └── tracing.py      #   Langfuse wiring (LiteLLM callback)
│       ├── tools/              # shared tool implementations (memory now; web/gmail/git later)
│       ├── agents/             # one package per agent, auto-discovered at startup
│       │   ├── research/       #   (phase 5) manifest + prompts
│       │   ├── personal/       #   (later)
│       │   └── dev/            #   (later)
│       ├── db/                 # SQLAlchemy models (runs, run_events, memory, users), session
│       └── tests/              # sqlite-backed framework tests with a fake LLM router
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
