# Adding a New Agent (Deliverable 8)

Adding agent #4 (or #40) is a repeatable pattern, not a project. Everything
heavy — routing, memory, scheduling, checkpointing, tracing, run tracking,
the dashboard — is framework-level and inherited. An agent is: **tools it
needs (if new), a manifest, and prompts.** The research agent
(`backend/src/jarvis/agents/research/`) is the living reference.

## Step 1 — tools (only if the agent needs new ones)

Tools are plain functions in `backend/src/jarvis/tools/`, registered by
decorator. Type hints + docstring become the model-facing schema, so write
them for the model, not for yourself:

```python
# backend/src/jarvis/tools/rss.py
import asyncio, json
import httpx
from jarvis.core.registry import tool

@tool(scopes=("rss",))
async def fetch_feed(url: str, limit: int = 10) -> str:
    """Fetch an RSS/Atom feed and return its newest entries as a JSON list
    of {title, url, published}."""
    ...
```

Then add the module to `backend/src/jarvis/tools/__init__.py`:

```python
from jarvis.tools import memory, rss, web  # noqa: F401
```

Conventions:
- **Scope per capability** (`web`, `memory`, `rss`, `gmail`…), so agents are
  granted capabilities, not function lists.
- A tool shared by two agents lives in `tools/`, never inside an agent
  package. No exceptions — that's the rule that keeps this a framework.
- Raise on failure; the framework converts exceptions into `ERROR: …` tool
  results the model can react to.
- Return strings (or JSON-serializable values; they're dumped for you).

## Step 2 — the agent package

```
backend/src/jarvis/agents/digest/
├── __init__.py     # from jarvis.agents.digest import agent  # noqa: F401
├── prompts.py      # SYSTEM_PROMPT (+ prompts for scheduled runs)
└── agent.py        # the manifest, ~15 lines
```

```python
# agent.py
from jarvis.agents.digest.prompts import DAILY_PROMPT, SYSTEM_PROMPT
from jarvis.core.agent import AgentManifest, BaseAgent, Schedule, register_agent

digest_agent = register_agent(
    BaseAgent(
        AgentManifest(
            name="digest",
            description="Morning news digest from followed feeds",
            system_prompt=SYSTEM_PROMPT,
            model_alias="local-bulk",        # summarization = bulk work
            tool_scopes=("rss", "memory"),
            schedules=(Schedule(cron="0 7 * * *", prompt=DAILY_PROMPT),),
            max_iterations=10,
        )
    )
)
```

That's it. Discovery is automatic (`agents/__init__.py` imports every
subpackage at startup), the scheduler arms the cron, and the dashboard
shows the agent with a chat pane and run history on next restart.

### Manifest choices that matter

- **`model_alias`** — `smart` (reasoning, tool-heavy judgment), `fast`
  (cheap API), `local-bulk` (summaries/classification; falls back to `fast`
  automatically when the home server is off). Never name concrete models.
- **`tool_scopes` vs `tool_names`** — scopes for capabilities, names to
  cherry-pick a single tool without its whole scope. Unknown grants fail at
  startup, loudly.
- **`max_iterations`** — model↔tools round-trip budget. 8 default; raise for
  research-style agents, lower for single-shot ones.
- **Schedules** — 5-field cron, `TZ` timezone. Write the schedule `prompt`
  as a complete work order (see `JOB_SCAN_PROMPT` in the research agent):
  what to read from memory, what to do, what to write back, what to report.

### Memory conventions

Shared memory is namespaced key/value (`memory` scope tools operate on the
shared namespace). Prefix keys per concern: `profile/…`, `jobs/seen/…`,
`digest/feeds`. Document your agent's keys in its prompt so the model — and
future you — knows the layout.

### Agents calling agents

Expose an agent as a tool where you register it, then grant that scope:

```python
from jarvis.core.agent import expose_agent_as_tool
expose_agent_as_tool("research", scopes=("delegation",))
```

Any agent granted `delegation` gets `ask_research(request)`; the delegated
work runs as a normal tracked run (trigger `agent`) with its own history and
trace. Keep delegation shallow (one level) — two agents pinging each other
is a loop, not architecture.

### Custom graph topology (rarely needed)

The default tool-loop graph covers most agents. If one genuinely needs
structure (fixed pipeline stages, human-approval gates), subclass:

```python
class PipelineAgent(BaseAgent):
    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        # your nodes/edges; reuse registry.call_tool and get_router()
        return graph
```

Runner, checkpointing, events, and the dashboard all keep working — they
only see a compiled graph streaming state updates.

## Step 3 — tests

Copy the pattern from `tests/test_research_agent.py` (registration, tool
grants resolve, cron parses, graph compiles) and, for new tools,
`tests/test_agent_run.py`'s `FakeRouter` to run the loop without network:

```python
def test_digest_registered():
    load_agents()
    agent = get_agent("digest")
    assert {"fetch_feed", "memory_put"} <= {t.name for t in agent.tools()}
    for s in agent.manifest.schedules:
        CronTrigger.from_crontab(s.cron)
    agent.build_graph().compile()
```

## Step 4 — ship

```bash
cd backend && python -m pytest -q
make prod   # rebuilds the backend image; agent + schedule live on restart
```

## Checklist

- [ ] New tools in `tools/`, scoped, registered in `tools/__init__.py`
- [ ] Agent package under `agents/<name>/` with manifest + prompts
- [ ] Model alias chosen (not a concrete model)
- [ ] Schedule prompts are complete work orders; memory keys documented
- [ ] Registration test passes; `pytest -q` green
- [ ] Restart → agent visible in dashboard, cron in the manifest listing
