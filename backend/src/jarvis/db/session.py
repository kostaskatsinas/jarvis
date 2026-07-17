from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from jarvis.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker | None = None


def configure(url: str | None = None) -> None:
    """(Re)build the engine. Tests call this with a sqlite URL."""
    global _engine, _sessionmaker
    _engine = create_async_engine(url or get_settings().database_url)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    if _engine is None:
        configure()
    return _engine


def get_sessionmaker() -> async_sessionmaker:
    if _sessionmaker is None:
        configure()
    return _sessionmaker
