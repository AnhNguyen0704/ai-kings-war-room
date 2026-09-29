"""Application settings. All values can be overridden via environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI King's War Room"
    debug: bool = True

    # Empty REDIS_URL -> in-memory event bus (single process).
    database_url: str = "sqlite+aiosqlite:///./data/warroom.db"
    redis_url: str = ""

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://localhost:8080",
    ]

    # --- LLM provider API keys. Missing key -> provider falls back to Mock. ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    xai_api_key: str = ""
    moonshot_api_key: str = ""

    # "auto" -> first live provider, otherwise Mock.
    judge_provider: str = "auto"
    judge_model: str = ""

    # --- Debate tuning ---
    discussion_rounds: int = 2
    debate_timeout_seconds: int = 600
    agent_turn_timeout: int = 120
    transcript_window: int = 30

    # --- Mock provider pacing (seconds) ---
    mock_think_delay: float = 0.5
    mock_token_delay: float = 0.012

    # --- Default models used when a provider is picked as judge with no explicit model ---
    provider_default_models: dict[str, str] = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
        "google": "gemini-1.5-flash",
        "xai": "grok-2-latest",
        "moonshot": "moonshot-v1-8k",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
