"""Azure OpenAI provider — PROD-READY STUB.

Same contract as every other provider; raises on `generate()` because no live
Azure endpoint is wired up (no credits budget). Going live means implementing
`generate()` against the Azure OpenAI endpoint and setting `LLM_PROVIDER=azure`
— nothing else in the codebase changes.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import LLMProvider, LLMResponse, Message


class AzureStubProvider(LLMProvider):
    name = "azure"

    def __init__(self, model: str = "gpt-4o", endpoint: str = "") -> None:
        super().__init__(model)
        self.endpoint = endpoint

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        raise NotImplementedError(
            "AzureStubProvider is a prod-ready stub: the interface is fully "
            "implemented but live calls are disabled by design. Configure an Azure "
            "OpenAI endpoint/deployment and implement generate() to go live — no "
            "other code changes are required."
        )
