import logging

import httpx

from app.core.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Calls a locally-running Ollama instance.
    Default model: llama3 (configured via OLLAMA_MODEL env var).
    """

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self._base_url = (base_url or settings.ollama_url).rstrip("/")
        self._model = model or settings.ollama_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except httpx.TimeoutException:
            logger.warning("Ollama generate timeout (model=%s)", self._model)
            return ""
        except Exception as exc:
            logger.error("Ollama generate error: %s", exc)
            return ""

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                # Confirm the configured model is pulled
                tags = [m.get("name", "") for m in resp.json().get("models", [])]
                return any(self._model in t for t in tags)
        except Exception:
            return False
