"""Global tool registry.

Tools are plain Python functions (sync or async) with type hints and a
docstring; the OpenAI-format schema is derived automatically. Agents declare
which tools they get by name and/or scope in their manifest — tools are never
imported directly by agent code.
"""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.utils.function_calling import convert_to_openai_tool


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: Callable
    scopes: frozenset[str]
    schema: dict  # OpenAI "type: function" schema


_tools: dict[str, ToolSpec] = {}


def tool(func: Callable | None = None, *, name: str | None = None, scopes: tuple[str, ...] = ()):
    """Register a function as a tool: @tool or @tool(name=..., scopes=(...,))."""

    def register(f: Callable) -> Callable:
        schema = convert_to_openai_tool(f)
        tool_name = name or schema["function"]["name"]
        schema["function"]["name"] = tool_name
        if tool_name in _tools:
            raise ValueError(f"duplicate tool name: {tool_name}")
        _tools[tool_name] = ToolSpec(
            name=tool_name,
            description=schema["function"].get("description", ""),
            func=f,
            scopes=frozenset(scopes),
            schema=schema,
        )
        return f

    return register(func) if func is not None else register


def get_tool(name: str) -> ToolSpec:
    return _tools[name]


def resolve(names: tuple[str, ...] = (), scopes: tuple[str, ...] = ()) -> list[ToolSpec]:
    """Tools matching any given name or carrying any given scope."""
    wanted_scopes = set(scopes)
    out: dict[str, ToolSpec] = {}
    for n in names:
        out[n] = _tools[n]  # unknown name -> KeyError, fail loudly at startup
    for spec in _tools.values():
        if spec.scopes & wanted_scopes:
            out[spec.name] = spec
    return list(out.values())


def all_tools() -> list[ToolSpec]:
    return list(_tools.values())


async def call_tool(name: str, args: dict) -> str:
    """Execute a tool and stringify its result for the model."""
    spec = _tools[name]
    result = spec.func(**args)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str)
