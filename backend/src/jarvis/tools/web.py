"""Web research tools (scope: "web").

Search uses DuckDuckGo via the `ddgs` library — free and keyless, which fits
the cost constraint; if it ever gets rate-limited into uselessness, the
upgrade path is a self-hosted SearXNG container behind the same tool.
Fetching extracts main article text with trafilatura.
"""

import asyncio
import json

import httpx

from jarvis.core.registry import tool

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Jarvis/0.1 research-agent"


async def _fetch_html(url: str) -> str:
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _ddg_search(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


@tool(scopes=("web",))
async def web_search(query: str, max_results: int = 8) -> str:
    """Search the web. Returns a JSON list of results with title, url and snippet."""
    raw = await asyncio.to_thread(_ddg_search, query, max_results)
    results = [
        {
            "title": r.get("title"),
            "url": r.get("href") or r.get("url"),
            "snippet": r.get("body") or r.get("snippet"),
        }
        for r in raw
    ]
    return json.dumps(results, ensure_ascii=False)


@tool(scopes=("web",))
async def web_fetch(url: str, max_chars: int = 8000) -> str:
    """Fetch a web page and return its main text content (boilerplate stripped)."""
    import trafilatura

    html = await _fetch_html(url)
    text = trafilatura.extract(html, url=url, include_comments=False)
    if not text:
        return "ERROR: could not extract readable text from this page"
    return text[:max_chars]
