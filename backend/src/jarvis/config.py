from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_")

    env: str = "prod"
    database_url: str = "postgresql+psycopg://jarvis:jarvis@localhost:5432/jarvis"
    secret_key: str = "dev-only-change-me"

    # Auth
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
