"""BaseAgent: the shared LangGraph scaffold every agent is built from.

An agent is: a manifest (name, prompt, model alias, tool grants, schedules)
plus the default tool-loop graph below. Agents needing a custom topology
subclass BaseAgent and override build_graph(); everything else (routing,
checkpointing, tracing, scheduling, run tracking) stays framework-provided.

Messages use OpenAI wire format (plain dicts) end to end — LiteLLM translates
per provider, and dicts checkpoint cleanly.
"""

import json
import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from jarvis.core import registry
from jarvis.core.llm import get_router
from jarvis.core.tracing import llm_metadata

log = structlog.get_logger()


class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    usage: Annotated[list[dict], operator.add]


@dataclass(frozen=True)
class Schedule:
    cron: str  # standard 5-field cron
    prompt: str  # the user message the scheduled run starts with


@dataclass(frozen=True)
class AgentManifest:
    name: str
    description: str
    system_prompt: str
    model_alias: str = "smart"
    tool_names: tuple[str, ...] = ()
    tool_scopes: tuple[str, ...] = ()
    schedules: tuple[Schedule, ...] = ()
    max_iterations: int = 8


class BaseAgent:
    def __init__(self, manifest: AgentManifest):
        self.manifest = manifest

    def tools(self) -> list[registry.ToolSpec]:
        return registry.resolve(self.manifest.tool_names, self.manifest.tool_scopes)

    def build_graph(self) -> StateGraph:
        tools = self.tools()
        schemas = [t.schema for t in tools]

        async def model_node(state: AgentState, config: RunnableConfig) -> dict:
            messages = [{"role": "system", "content": self.manifest.system_prompt}]
            messages += state["messages"]
            kwargs: dict[str, Any] = {}
            if schemas:
                kwargs["tools"] = schemas
            response = await get_router().acompletion(
                model=self.manifest.model_alias,
                messages=messages,
                metadata=llm_metadata(
                    self.manifest.name, config.get("configurable", {}).get("thread_id", "")
                ),
                **kwargs,
            )
            message = response.choices[0].message
            message = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else dict(message)
            usage = getattr(response, "usage", None)
            usage = usage.model_dump() if hasattr(usage, "model_dump") else (usage or {})
            return {"messages": [message], "usage": [usage]}

        async def tools_node(state: AgentState) -> dict:
            results = []
            for call in state["messages"][-1].get("tool_calls", []):
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    content = await registry.call_tool(name, args)
                except Exception as exc:  # tool errors go back to the model, not up the stack
                    log.warning("tool_error", tool=name, error=str(exc))
                    content = f"ERROR: {exc}"
                results.append(
                    {"role": "tool", "tool_call_id": call["id"], "name": name, "content": content}
                )
            return {"messages": results}

        def route(state: AgentState) -> str:
            return "tools" if state["messages"][-1].get("tool_calls") else END

        graph = StateGraph(AgentState)
        graph.add_node("model", model_node)
        graph.add_node("tools", tools_node)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", route, {"tools": "tools", END: END})
        graph.add_edge("tools", "model")
        return graph


_agents: dict[str, BaseAgent] = {}


def register_agent(agent: BaseAgent) -> BaseAgent:
    name = agent.manifest.name
    if name in _agents:
        raise ValueError(f"duplicate agent name: {name}")
    agent.tools()  # fail at registration time if a tool grant is unknown
    _agents[name] = agent
    log.info("agent_registered", agent=name)
    return agent


def get_agent(name: str) -> BaseAgent:
    return _agents[name]


def list_agents() -> list[BaseAgent]:
    return list(_agents.values())
