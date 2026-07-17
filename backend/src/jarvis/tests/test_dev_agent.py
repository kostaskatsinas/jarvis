import asyncio
import json

import pytest

import jarvis.tools  # noqa: F401  (registers all tool modules)
from jarvis.agents import load_agents
from jarvis.config import get_settings
from jarvis.core import registry
from jarvis.core.agent import get_agent


def test_dev_agent_registered():
    load_agents()
    agent = get_agent("dev")
    tool_names = {t.name for t in agent.tools()}
    assert {"git_clone", "repo_list", "repo_read", "repo_search", "repo_write", "repo_diff"} <= tool_names
    assert "ask_research" in tool_names  # delegation scope
    assert agent.manifest.schedules == ()
    agent.build_graph().compile()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE_ROOT", str(tmp_path / "ws"))
    get_settings.cache_clear()
    return tmp_path


async def _make_source_repo(tmp_path) -> str:
    """A local origin repo to clone from (no network in tests)."""
    src = tmp_path / "origin"
    src.mkdir()
    (src / "hello.py").write_text('GREETING = "hello world"\n')
    git = lambda *a: asyncio.create_subprocess_exec(  # noqa: E731
        "git", "-c", "user.email=t@t", "-c", "user.name=t", *a, cwd=src,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "init")):
        process = await git(*args)
        assert await process.wait() == 0
    return str(src)


async def test_dev_tools_roundtrip(workspace):
    url = await _make_source_repo(workspace)

    assert "cloned" in await registry.call_tool("git_clone", {"url": url, "name": "proj"})
    assert json.loads(await registry.call_tool("repo_list", {})) == ["proj"]

    tree = json.loads(await registry.call_tool("repo_tree", {"repo": "proj"}))
    assert "hello.py" in tree

    content = await registry.call_tool("repo_read", {"repo": "proj", "path": "hello.py"})
    assert "hello world" in content

    matches = await registry.call_tool("repo_search", {"repo": "proj", "pattern": "GREETING"})
    assert "hello.py:1:" in matches
    assert (
        await registry.call_tool("repo_search", {"repo": "proj", "pattern": "nope_zzz"})
        == "(no matches)"
    )

    await registry.call_tool(
        "repo_write", {"repo": "proj", "path": "scripts/run.sh", "content": "#!/bin/sh\necho hi\n"}
    )
    diff = await registry.call_tool("repo_diff", {"repo": "proj"})
    assert "scripts/run.sh" in diff


async def test_dev_tools_sandboxed(workspace):
    url = await _make_source_repo(workspace)
    await registry.call_tool("git_clone", {"url": url, "name": "proj2"})

    with pytest.raises(ValueError, match="escapes"):
        await registry.call_tool("repo_read", {"repo": "proj2", "path": "../../etc/passwd"})
    with pytest.raises(ValueError, match="invalid repo name"):
        await registry.call_tool("repo_read", {"repo": "../proj2", "path": "hello.py"})
    with pytest.raises(ValueError, match="unknown repo"):
        await registry.call_tool("repo_tree", {"repo": "ghost"})
