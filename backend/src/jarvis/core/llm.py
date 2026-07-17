"""The single gateway for model calls: a LiteLLM Router behind aliases.

Agents never name concrete models — they ask for an alias:
  fast        cheap API model for quick/simple steps
  smart       reasoning-grade API model
  local-bulk  home-server Ollama for bulk work, silent fallback to `fast`

When OLLAMA_BASE_URL is unset/unreachable, local-bulk degrades to the API.
"""

from litellm.router import Router

from jarvis.config import get_settings

_router: Router | None = None


def build_router() -> Router:
    s = get_settings()
    model_list = [
        {"model_name": "fast", "litellm_params": {"model": s.model_fast}},
        {"model_name": "smart", "litellm_params": {"model": s.model_smart}},
    ]
    fallbacks: list[dict] = []
    if s.ollama_base_url:
        model_list.append(
            {
                "model_name": "local-bulk",
                "litellm_params": {
                    "model": f"ollama_chat/{s.model_local}",
                    "api_base": s.ollama_base_url,
                    "timeout": s.ollama_timeout_seconds,
                },
            }
        )
        fallbacks.append({"local-bulk": ["fast"]})
    else:
        # No local models configured: local-bulk is just the cheap API tier.
        model_list.append({"model_name": "local-bulk", "litellm_params": {"model": s.model_fast}})
    return Router(model_list=model_list, fallbacks=fallbacks, num_retries=1)


def get_router() -> Router:
    global _router
    if _router is None:
        _router = build_router()
    return _router


def set_router(router) -> None:
    """Test seam: inject a fake router."""
    global _router
    _router = router
