from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://jh:changeme@localhost:5432/jobhunter"

    # Security (Phase 3)
    secret_key: str = "changeme_secret_minimum_32_characters_long_replace_this"
    access_token_expire_minutes: int = 1440

    # Ollama
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3"

    # Job source APIs
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # OpenAI fallback
    openai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
