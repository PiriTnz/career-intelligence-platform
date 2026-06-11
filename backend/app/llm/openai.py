"""
OpenAI provider — drop-in replacement for OllamaProvider.
Requires: pip install openai>=1.0
Activate by setting OPENAI_API_KEY in .env.
"""
import logging

from app.core.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._client = None
        if settings.openai_api_key:
            try:
                from openai import AsyncOpenAI  # lazy import — optional dependency

                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.warning("openai package not installed — OpenAIProvider unavailable")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        if self._client is None:
            logger.error("OpenAIProvider: client not initialised")
            return ""
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("OpenAI generate error: %s", exc)
            return ""

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.models.retrieve(self._model)
            return True
        except Exception:
            return False
