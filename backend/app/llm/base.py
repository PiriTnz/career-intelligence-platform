from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Contract every LLM provider must satisfy.
    LLM is used ONLY for human-readable explanations — never for scoring,
    ranking, or any decision that affects job ordering.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier shown in health checks and logs."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model name/id currently active on this provider."""

    @abstractmethod
    async def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        """
        Generate a completion for the given prompt.
        Must raise on hard failures; returns empty string on soft failures.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and the model is available."""
