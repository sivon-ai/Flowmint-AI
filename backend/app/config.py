"""
Flowmint AI — Application Configuration.

Uses Pydantic BaseSettings for type-safe configuration with .env file support.
All secrets and environment-specific values are loaded from environment variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "flowmint-ai"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me"
    backend_cors_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://flowmint:flowmint_dev@localhost:5432/flowmint_db"
    database_url_sync: str = "postgresql://flowmint:flowmint_dev@localhost:5432/flowmint_db"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- Razorpay (TEST MODE) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # --- Rate Limiting ---
    rate_limit_per_minute: int = 60

    # --- Logging ---
    log_level: str = "INFO"

    # --- AI Settings (Phase 2A) ---
    ai_provider: str = "mock"  # mock, openai, anthropic, google
    ai_model: str = "mock-model"
    ai_temperature: float = 0.1
    ai_max_tokens: int = 1024
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # --- Embedding Settings (Phase 2A) ---
    embedding_provider: str = "mock"  # mock, openai
    embedding_model: str = "text-embedding-3-small"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
