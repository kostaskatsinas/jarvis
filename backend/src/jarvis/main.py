import structlog
from fastapi import FastAPI

from jarvis import __version__
from jarvis.config import get_settings

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Jarvis", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "env": settings.env}

    log.info("app_created", env=settings.env)
    return app


app = create_app()
