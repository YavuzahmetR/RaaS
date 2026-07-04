"""Provider-agnostic LLM interface.

Every concrete provider (DeepSeek, Gemini, Bedrock, Azure) implements this
interface. Application code depends ONLY on `LLMProvider` and never branches on
the provider name — switching providers is done exclusively through the
`LLM_PROVIDER` env var, resolved once in `factory.get_provider()`.

All value objects are frozen dataclasses: responses are immutable snapshots of a
single call, safe to pass around, log and trace without hidden mutation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


def system(content: str) -> Message:
    return Message("system", content)


def user(content: str) -> Message:
    return Message("user", content)


def assistant(content: str) -> Message:
    return Message("assistant", content)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: TokenUsage
    cost_usd: float
    latency_ms: float
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract text-generation provider.

    Embeddings are intentionally NOT part of this interface — they run locally
    via sentence-transformers (app/rag/embeddings.py), keeping inference free and
    fully provider-independent.
    """

    #: stable identifier used for cost lookup, tracing and logs
    name: str = "base"

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        """Return a completion plus measured token usage, cost and latency."""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{type(self).__name__}(model={self.model!r})"
