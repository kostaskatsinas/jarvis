"""Run lifecycle: create a Run row, execute the agent's graph as an asyncio
task, persist every step as a RunEvent, stream events to WebSocket
subscribers, and finalize status/usage.
"""

import asyncio
import uuid
from typing import Any

import structlog

from jarvis.core.agent import BaseAgent, get_agent
from jarvis.core.checkpoint import get_checkpointer
from jarvis.db.models import Run, RunEvent, utcnow
from jarvis.db.session import get_sessionmaker

log = structlog.get_logger()

_tasks: dict[uuid.UUID, asyncio.Task] = {}
_subscribers: dict[uuid.UUID, set[asyncio.Queue]] = {}

RUN_FINISHED = "run_finished"


def subscribe(run_id: uuid.UUID) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(run_id, set()).add(queue)
    return queue


def unsubscribe(run_id: uuid.UUID, queue: asyncio.Queue) -> None:
    _subscribers.get(run_id, set()).discard(queue)


def _publish(run_id: uuid.UUID, event: dict) -> None:
    for queue in _subscribers.get(run_id, set()):
        queue.put_nowait(event)


async def _record_event(run_id: uuid.UUID, type_: str, payload: dict) -> None:
    async with get_sessionmaker()() as session:
        session.add(RunEvent(run_id=run_id, type=type_, payload=payload))
        await session.commit()
    _publish(run_id, {"type": type_, "payload": payload})


async def start_run(agent_name: str, message: str, trigger: str = "api") -> uuid.UUID:
    agent = get_agent(agent_name)  # KeyError -> caller maps to 404
    run_id = uuid.uuid4()
    async with get_sessionmaker()() as session:
        session.add(
            Run(id=run_id, agent_name=agent_name, trigger=trigger, input_text=message)
        )
        await session.commit()
    _tasks[run_id] = asyncio.create_task(_execute(run_id, agent, message))
    log.info("run_started", run_id=str(run_id), agent=agent_name, trigger=trigger)
    return run_id


async def wait(run_id: uuid.UUID) -> None:
    task = _tasks.get(run_id)
    if task is not None:
        await task


async def _execute(run_id: uuid.UUID, agent: BaseAgent, message: str) -> None:
    status, output, error = "succeeded", None, None
    usage_entries: list[dict] = []
    try:
        graph = agent.build_graph().compile(checkpointer=get_checkpointer())
        config = {
            "configurable": {"thread_id": str(run_id)},
            "recursion_limit": 2 * agent.manifest.max_iterations + 2,
        }
        state_in = {"messages": [{"role": "user", "content": message}], "usage": []}
        async for update in graph.astream(state_in, config, stream_mode="updates"):
            for node, out in update.items():
                out = out or {}
                usage_entries += out.get("usage", [])
                await _record_event(run_id, node, {"messages": out.get("messages", [])})
                for msg in out.get("messages", []):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        output = msg["content"]
    except Exception as exc:
        status, error = "failed", str(exc)
        log.error("run_failed", run_id=str(run_id), agent=agent.manifest.name, error=error)
        await _record_event(run_id, "error", {"error": error})
    finally:
        totals = _sum_usage(usage_entries)
        async with get_sessionmaker()() as session:
            run = await session.get(Run, run_id)
            run.status = status
            run.output_text = output
            run.error = error
            run.finished_at = utcnow()
            run.prompt_tokens = totals["prompt_tokens"]
            run.completion_tokens = totals["completion_tokens"]
            await session.commit()
        _publish(run_id, {"type": RUN_FINISHED, "payload": {"status": status}})
        _tasks.pop(run_id, None)
        log.info("run_finished", run_id=str(run_id), status=status, **totals)


def _sum_usage(entries: list[dict]) -> dict[str, Any]:
    return {
        "prompt_tokens": sum(e.get("prompt_tokens") or 0 for e in entries),
        "completion_tokens": sum(e.get("completion_tokens") or 0 for e in entries),
    }
