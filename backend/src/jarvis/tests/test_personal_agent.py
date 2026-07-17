import email
import email.policy
import json

import pytest
from apscheduler.triggers.cron import CronTrigger

import jarvis.tools  # noqa: F401  (registers all tool modules)
from jarvis.agents import load_agents
from jarvis.config import get_settings
from jarvis.core import registry
from jarvis.core.agent import get_agent
from jarvis.tools.gmail import build_draft_mime, extract_text_body, summarize_headers


def test_personal_agent_registered():
    load_agents()
    agent = get_agent("personal")
    tool_names = {t.name for t in agent.tools()}
    assert {"email_list", "email_read", "email_draft", "file_move", "memory_put"} <= tool_names
    assert "ask_research" not in tool_names  # no delegation scope granted
    for schedule in agent.manifest.schedules:
        CronTrigger.from_crontab(schedule.cron)
    agent.build_graph().compile()


def test_summarize_headers():
    raw = b"From: Alice <a@example.com>\r\nTo: me@example.com\r\nSubject: Hi\r\nDate: Mon, 1 Jan 2026 10:00:00 +0200\r\n\r\n"
    summary = summarize_headers("42", raw)
    assert summary["uid"] == "42"
    assert "a@example.com" in summary["from"]
    assert summary["subject"] == "Hi"


def test_extract_text_body_prefers_plain():
    raw = (
        b"From: a@example.com\r\nTo: b@example.com\r\nSubject: x\r\n"
        b'Content-Type: multipart/alternative; boundary="B"\r\n\r\n'
        b"--B\r\nContent-Type: text/plain\r\n\r\nplain words\r\n"
        b"--B\r\nContent-Type: text/html\r\n\r\n<p>html words</p>\r\n--B--\r\n"
    )
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert extract_text_body(msg) == "plain words"


def test_build_draft_mime_threads_replies():
    draft = build_draft_mime(
        "me@example.com", "a@example.com", "Re: Hi", "sounds good", orig_message_id="<orig@id>"
    )
    assert draft["From"] == "me@example.com"
    assert draft["In-Reply-To"] == "<orig@id>"
    assert draft["References"] == "<orig@id>"
    assert draft.get_content().strip() == "sounds good"


async def test_gmail_tools_error_without_credentials(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    get_settings.cache_clear()
    # Raised here; inside an agent run the framework turns this into an
    # "ERROR: ..." tool result the model can read and report.
    with pytest.raises(RuntimeError, match="not configured"):
        await registry.call_tool("email_list", {})


async def test_files_tools_sandboxed(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_FILES_ROOT", str(tmp_path / "files"))
    get_settings.cache_clear()

    await registry.call_tool("file_mkdir", {"path": "inbox"})
    (tmp_path / "files" / "inbox" / "a.txt").write_text("hello")

    listing = json.loads(await registry.call_tool("file_list", {"path": "inbox"}))
    assert listing == [{"name": "a.txt", "type": "file", "size": 5}]

    assert await registry.call_tool("file_read", {"path": "inbox/a.txt"}) == "hello"

    await registry.call_tool("file_move", {"src": "inbox/a.txt", "dest": "archive/2026/a.txt"})
    assert (tmp_path / "files" / "archive" / "2026" / "a.txt").read_text() == "hello"

    with pytest.raises(ValueError, match="escapes"):
        await registry.call_tool("file_read", {"path": "../../etc/passwd"})
