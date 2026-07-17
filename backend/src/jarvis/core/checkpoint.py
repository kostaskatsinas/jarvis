"""LangGraph checkpointer lifecycle.

Postgres in real deployments (AsyncPostgresSaver); in-memory for tests and
any non-Postgres database URL.
"""

from contextlib import AsyncExitStack

from langgraph.checkpoint.memory import InMemorySaver

from jarvis.config import get_settings

_saver = None
_stack: AsyncExitStack | None = None


async def open_checkpointer():
    global _saver, _stack
    url = get_settings().database_url
    if url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn = url.replace("+psycopg", "", 1)
        _stack = AsyncExitStack()
        _saver = await _stack.enter_async_context(AsyncPostgresSaver.from_conn_string(conn))
        await _saver.setup()
    else:
        _saver = InMemorySaver()
    return _saver


async def close_checkpointer() -> None:
    global _saver, _stack
    if _stack is not None:
        await _stack.aclose()
    _saver = None
    _stack = None


def get_checkpointer():
    if _saver is None:
        raise RuntimeError("checkpointer not opened; call open_checkpointer() in app lifespan")
    return _saver
