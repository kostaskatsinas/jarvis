"""Namespaced key/value memory shared across agents, backed by Postgres.

Values are JSON-serializable. Agents get this either through the framework
(`Memory("research")`) or through the generic memory tools in
jarvis.tools.memory (scope "memory").
"""

from typing import Any

from sqlalchemy import delete, select

from jarvis.db.models import MemoryEntry
from jarvis.db.session import get_sessionmaker

SHARED = "shared"


class Memory:
    def __init__(self, namespace: str = SHARED):
        self.namespace = namespace

    async def get(self, key: str, default: Any = None) -> Any:
        async with get_sessionmaker()() as session:
            entry = await session.get(MemoryEntry, (self.namespace, key))
            return entry.value if entry is not None else default

    async def put(self, key: str, value: Any) -> None:
        async with get_sessionmaker()() as session:
            await session.merge(MemoryEntry(namespace=self.namespace, key=key, value=value))
            await session.commit()

    async def delete(self, key: str) -> None:
        async with get_sessionmaker()() as session:
            await session.execute(
                delete(MemoryEntry).where(
                    MemoryEntry.namespace == self.namespace, MemoryEntry.key == key
                )
            )
            await session.commit()

    async def keys(self, prefix: str = "") -> list[str]:
        async with get_sessionmaker()() as session:
            stmt = select(MemoryEntry.key).where(MemoryEntry.namespace == self.namespace)
            if prefix:
                stmt = stmt.where(MemoryEntry.key.startswith(prefix))
            return list((await session.execute(stmt)).scalars())
