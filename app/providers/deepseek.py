"""DeepSeek provider — primary dev provider (OpenAI-compatible API)."""

from __future__ import annotations

import time
from typing import Any

from app.providers.base import LLMProvider, LLMResponse, Message, TokenUsage
from app.providers.pricing import compute_cost

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = DEEPSEEK_BASE_URL,
    ) -> None:
        super().__init__(model)
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing — set it in .env")
        # Lazy import so the adapter layer imports cleanly without the SDK present.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        start = time.perf_counter()
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0

        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            provider=self.name,
            model=self.model,
            usage=usage,
            cost_usd=compute_cost(
                self.name, self.model, usage.prompt_tokens, usage.completion_tokens
            ),
            latency_ms=latency_ms,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
