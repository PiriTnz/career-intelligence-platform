from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_MARKERS = ("changeme", "change-me", "replace_this", "replace-this", "secret")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Deployment environment — set to "production" in production containers
    app_env: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://jh:changeme@localhost:5432/jobhunter"

    # Security
    secret_key: str = "changeme_secret_minimum_32_characters_long_replace_this"
    access_token_expire_minutes: int = 1440

    # CORS — comma-separated list of allowed origins
    # Example: CORS_ORIGINS=https://app.example.com,https://www.example.com
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

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

    @field_validator("secret_key")
    @classmethod
    def _secret_key_must_be_set(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "staging")

    def has_insecure_defaults(self) -> list[str]:
        problems: list[str] = []
        sk_lower = self.secret_key.lower()
        if any(m in sk_lower for m in _INSECURE_MARKERS):
            problems.append("SECRET_KEY contains an insecure default value")
        db_lower = self.database_url.lower()
        if any(m in db_lower for m in _INSECURE_MARKERS):
            problems.append("DATABASE_URL contains an insecure default password")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
