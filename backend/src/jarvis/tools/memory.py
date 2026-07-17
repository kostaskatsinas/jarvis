"""Generic shared-memory tools (scope: "memory").

Any agent granted the "memory" scope can persist and recall facts across
runs and across agents.
"""

import json

from jarvis.core.memory import Memory
from jarvis.core.registry import tool

_shared = Memory()


@tool(scopes=("memory",))
async def memory_put(key: str, value: str) -> str:
    """Store a value in shared long-term memory under a key. Overwrites any existing value."""
    await _shared.put(key, value)
    return f"stored {key!r}"


@tool(scopes=("memory",))
async def memory_get(key: str) -> str:
    """Read a value from shared long-term memory. Returns 'null' if the key does not exist."""
    return json.dumps(await _shared.get(key), default=str)


@tool(scopes=("memory",))
async def memory_list(prefix: str = "") -> str:
    """List keys in shared long-term memory, optionally filtered by prefix."""
    return json.dumps(await _shared.keys(prefix))
