from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from jarvis import __version__
from jarvis.api import agents as agents_api
from jarvis.api import runs as runs_api
from jarvis.api import ws as ws_api
from jarvis.config import get_settings
from jarvis.core.checkpoint import close_checkpointer, open_checkpointer
from jarvis.core.scheduler import start_scheduler
from jarvis.core.tracing import init_tracing

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import jarvis.tools  # noqa: F401  (registers shared tools)
    from jarvis.agents import load_agents

    load_agents()
    init_tracing()
    await open_checkpointer()
    scheduler = start_scheduler()
    log.info("startup_complete")
    yield
    scheduler.shutdown(wait=False)
    await close_checkpointer()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Jarvis",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(agents_api.router)
    app.include_router(runs_api.router)
    app.include_router(ws_api.router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "env": settings.env}

    return app


app = create_app()
