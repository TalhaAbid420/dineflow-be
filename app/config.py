from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for Dineflow, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Dineflow"
    environment: str = "development"
    log_level: str = "INFO"

    # --- LLM / Agent ---
    openai_api_key: str = ""
    openai_model: str = "gpt-5"
    openai_base_url: str | None = None

    # --- PostgreSQL: short-term memory + ordering + menu ---
    postgres_database_url: str = (
        "postgresql://dineflow:dineflow@localhost:5432/dineflow"
    )

    # --- MongoDB: long-term memories (preferences, personal details) ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "dineflow"

    # --- API ---
    backend_cors_origins: str = "http://localhost:3000"
    seed_menu_on_start: bool = True

    # --- Auth ---
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    chef_email: str = "chef@gmail.com"
    chef_password: str = "chef1234"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # The OpenAI Agents SDK / openai client read their config from
    # os.environ, so surface values loaded from .env into the process env.
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.openai_base_url:
        os.environ.setdefault("OPENAI_BASE_URL", settings.openai_base_url)
    return settings
