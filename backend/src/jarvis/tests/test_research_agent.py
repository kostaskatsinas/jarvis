import json

from apscheduler.triggers.cron import CronTrigger

from jarvis.agents import load_agents
from jarvis.core import registry
from jarvis.core.agent import get_agent
from jarvis.tools import web


def test_research_agent_registered():
    load_agents()
    agent = get_agent("research")
    tool_names = {t.name for t in agent.tools()}
    assert {"web_search", "web_fetch", "memory_get", "memory_put", "memory_list"} <= tool_names
    for schedule in agent.manifest.schedules:
        CronTrigger.from_crontab(schedule.cron)  # invalid cron would raise
    agent.build_graph().compile()  # graph topology is sound


async def test_web_search_normalizes_results(monkeypatch):
    monkeypatch.setattr(
        web,
        "_ddg_search",
        lambda query, max_results: [
            {"title": "A", "href": "https://a.example", "body": "alpha"},
            {"title": "B", "url": "https://b.example", "snippet": "beta"},
        ],
    )
    results = json.loads(await registry.call_tool("web_search", {"query": "x"}))
    assert results == [
        {"title": "A", "url": "https://a.example", "snippet": "alpha"},
        {"title": "B", "url": "https://b.example", "snippet": "beta"},
    ]


async def test_web_fetch_extracts_and_truncates(monkeypatch):
    paragraph = (
        "The actual article content sits inside this paragraph. It carries "
        "several full sentences so the extractor treats it as the main body "
        "of the page rather than boilerplate. Navigation menus, footers and "
        "cookie banners should all be stripped away by the extraction step, "
        "leaving only this readable text for the model to work with."
    )
    html = (
        "<html><head><title>t</title></head><body>"
        "<nav>home | about | contact</nav>"
        f"<article><p>{paragraph}</p></article>"
        "<footer>copyright</footer></body></html>"
    )

    async def fake_fetch(url: str) -> str:
        return html

    monkeypatch.setattr(web, "_fetch_html", fake_fetch)

    full = await registry.call_tool("web_fetch", {"url": "https://a.example"})
    assert "actual article content" in full
    assert "home | about" not in full

    truncated = await registry.call_tool(
        "web_fetch", {"url": "https://a.example", "max_chars": 60}
    )
    assert len(truncated) == 60
