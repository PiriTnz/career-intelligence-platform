from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider


def get_provider() -> BaseLLMProvider:
    """
    Return the active LLM provider.
    Prefers OpenAI when OPENAI_API_KEY is set, falls back to Ollama.
    Called per-request — no singleton needed (providers are stateless).
    """
    if settings.openai_api_key:
        return OpenAIProvider()
    return OllamaProvider()


__all__ = ["BaseLLMProvider", "OllamaProvider", "OpenAIProvider", "get_provider"]
