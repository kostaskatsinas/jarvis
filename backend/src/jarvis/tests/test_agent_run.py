"""End-to-end framework test: agent with a tool-calling loop through the
runner, against a fake LiteLLM router — verifies run rows, events, usage
accounting, and error handling."""

import uuid
from types import SimpleNamespace

from sqlalchemy import select

from jarvis.core import registry, runner
from jarvis.core.agent import AgentManifest, BaseAgent, register_agent
from jarvis.core.llm import set_router
from jarvis.db.models import Run, RunEvent
from jarvis.db.session import get_sessionmaker


@registry.tool(scopes=("test-agent",))
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class _Dump:
    def __init__(self, data: dict):
        self._data = data

    def model_dump(self, **_kw) -> dict:
        return self._data


def _response(message: dict, usage: dict):
    return SimpleNamespace(choices=[SimpleNamespace(message=_Dump(message))], usage=_Dump(usage))


class FakeRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def acompletion(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        return self.responses.pop(0)


AGENT = register_agent(
    BaseAgent(
        AgentManifest(
            name="test-agent",
            description="framework test agent",
            system_prompt="You are a calculator.",
            model_alias="fast",
            tool_scopes=("test-agent",),
        )
    )
)


async def test_tool_loop_run(checkpointer):
    router = FakeRouter(
        [
            _response(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "add", "arguments": '{"a": 2, "b": 3}'},
                        }
                    ],
                },
                {"prompt_tokens": 10, "completion_tokens": 5},
            ),
            _response(
                {"role": "assistant", "content": "The answer is 5"},
                {"prompt_tokens": 20, "completion_tokens": 7},
            ),
        ]
    )
    set_router(router)

    run_id = await runner.start_run("test-agent", "add 2 and 3", trigger="chat")
    await runner.wait(run_id)

    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        events = list(
            (
                await session.execute(
                    select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id)
                )
            ).scalars()
        )

    assert run.status == "succeeded"
    assert run.output_text == "The answer is 5"
    assert run.prompt_tokens == 30 and run.completion_tokens == 12

    assert [e.type for e in events] == ["model", "tools", "model"]
    tool_msg = events[1].payload["messages"][0]
    assert tool_msg == {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "add",
        "content": "5",
    }

    # System prompt prepended, alias routed, tool schema offered.
    first_call = router.calls[0]
    assert first_call["model"] == "fast"
    assert first_call["messages"][0] == {"role": "system", "content": "You are a calculator."}
    assert first_call["tools"][0]["function"]["name"] == "add"


async def test_failed_run_recorded(checkpointer):
    set_router(FakeRouter([RuntimeError("provider exploded")]))

    run_id = await runner.start_run("test-agent", "boom")
    await runner.wait(run_id)

    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
    assert run.status == "failed"
    assert "provider exploded" in run.error
    assert run.finished_at is not None


async def test_unknown_agent_rejected():
    try:
        await runner.start_run("does-not-exist", "hi")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


async def test_agent_as_tool(checkpointer):
    from jarvis.core.agent import expose_agent_as_tool

    expose_agent_as_tool("test-agent", scopes=("delegation",))
    set_router(FakeRouter([_response({"role": "assistant", "content": "delegated answer"}, {})]))

    result = await registry.call_tool("ask_test_agent", {"request": "do the thing"})
    assert result == "delegated answer"

    # The delegated work is a first-class tracked run.
    async with get_sessionmaker()() as session:
        runs = list((await session.execute(select(Run))).scalars())
    assert any(r.trigger == "agent" and r.output_text == "delegated answer" for r in runs)


async def test_run_id_is_thread_id(checkpointer):
    """The run id doubles as the LangGraph thread id for checkpointing."""
    router = FakeRouter([_response({"role": "assistant", "content": "ok"}, {})])
    set_router(router)
    run_id = await runner.start_run("test-agent", "hello")
    await runner.wait(run_id)
    assert isinstance(run_id, uuid.UUID)
    assert router.calls[0]["metadata"]["session_id"] == str(run_id)
