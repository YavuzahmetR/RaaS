"""LLM provider adapter layer.

Application code depends only on the abstract `LLMProvider` (base.py) and never
branches on provider identity. Provider selection happens in exactly one place:
`factory.get_provider()`, driven by the `LLM_PROVIDER` env var.
"""

from app.providers.base import (
    LLMProvider,
    LLMResponse,
    Message,
    TokenUsage,
    assistant,
    system,
    user,
)
from app.providers.factory import available_providers, get_provider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "Message",
    "TokenUsage",
    "assistant",
    "system",
    "user",
    "get_provider",
    "available_providers",
]
