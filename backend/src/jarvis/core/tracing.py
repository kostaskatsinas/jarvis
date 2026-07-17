"""Langfuse wiring.

LLM-call tracing goes through LiteLLM's built-in Langfuse callback, which
reads LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY from the
environment (set in docker-compose.yml). Runs group into Langfuse sessions
by run id via the per-call metadata below.
"""

import os

import structlog

log = structlog.get_logger()


def init_tracing() -> bool:
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        log.info("tracing_disabled", reason="LANGFUSE_* env not set")
        return False
    import litellm

    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]
    log.info("tracing_enabled", host=os.environ.get("LANGFUSE_HOST", "cloud"))
    return True


def llm_metadata(agent_name: str, run_id: str) -> dict:
    return {
        "trace_name": agent_name,
        "session_id": run_id,
        "tags": [agent_name],
    }
