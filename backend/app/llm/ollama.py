import logging

import httpx

from app.core.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError)


class OllamaProvider(BaseLLMProvider):
    """
    Calls a locally-running Ollama instance.
    Default model: llama3 (configured via OLLAMA_MODEL env var).
    Retries on network timeouts; gives up immediately on HTTP errors.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self._base_url = (base_url or settings.ollama_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
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
            except _RETRYABLE as exc:
                logger.warning(
                    "Ollama generate retry %d/%d (model=%s): %s",
                    attempt, self._max_retries, self._model, exc,
                )
                if attempt == self._max_retries:
                    return ""
            except Exception as exc:
                logger.error("Ollama generate error: %s", exc)
                return ""
        return ""  # pragma: no cover

    async def list_models(self) -> list[str]:
        """Return names of all locally pulled models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code != 200:
                    return []
                return [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:
            return []

    async def health_check(self) -> bool:
        models = await self.list_models()
        return any(self._model in name for name in models)
