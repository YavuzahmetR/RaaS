"""AWS Bedrock provider — PROD-READY STUB.

Implements the `LLMProvider` interface exactly but raises on `generate()`, making
it explicit that no live Bedrock call is wired up (no credits budget). Going live
means filling in `generate()` with a boto3 `bedrock-runtime` call and setting
`LLM_PROVIDER=bedrock` — no other code changes anywhere. That single-switch
portability is the entire point of the adapter layer.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import LLMProvider, LLMResponse, Message


class BedrockStubProvider(LLMProvider):
    name = "bedrock"

    def __init__(
        self,
        model: str = "anthropic.claude-3-5-sonnet",
        region: str = "us-east-1",
    ) -> None:
        super().__init__(model)
        self.region = region

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        raise NotImplementedError(
            "BedrockStubProvider is a prod-ready stub: the interface is fully "
            "implemented but live calls are disabled by design. Provide AWS "
            "credentials and implement generate() with boto3 bedrock-runtime to go "
            "live — no other code changes are required."
        )
