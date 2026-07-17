from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_")

    env: str = "prod"
    database_url: str = "postgresql+psycopg://jarvis:jarvis@localhost:5432/jarvis"
    secret_key: str = "dev-only-change-me"

    # Auth
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    admin_email: str = ""  # bootstraps the single user on first start
    admin_password: str = ""

    # LLM routing. Aliases (fast / smart / local-bulk) are what agents use;
    # concrete models are env-overridable without touching code.
    model_fast: str = "anthropic/claude-haiku-4-5"
    model_smart: str = "anthropic/claude-sonnet-5"
    model_local: str = "qwen2.5:7b"  # served by Ollama, only used when reachable
    ollama_base_url: str = Field(
        "", validation_alias=AliasChoices("OLLAMA_BASE_URL", "JARVIS_OLLAMA_BASE_URL")
    )
    ollama_timeout_seconds: int = 120

    timezone: str = Field("Europe/Athens", validation_alias=AliasChoices("TZ", "JARVIS_TZ"))

    # Personal agent: Gmail over IMAP with an app password (2FA required).
    gmail_address: str = Field(
        "", validation_alias=AliasChoices("GMAIL_ADDRESS", "JARVIS_GMAIL_ADDRESS")
    )
    gmail_app_password: str = Field(
        "", validation_alias=AliasChoices("GMAIL_APP_PASSWORD", "JARVIS_GMAIL_APP_PASSWORD")
    )

    # Sandboxed roots for the files/dev tools (volume mounts in compose).
    files_root: str = "/data/files"
    workspace_root: str = "/data/workspace"


@lru_cache
def get_settings() -> Settings:
    return Settings()
