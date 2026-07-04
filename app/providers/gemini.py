"""Gemini provider — secondary dev provider + LLM-as-judge (google-genai SDK)."""

from __future__ import annotations

import time
from typing import Any

from app.providers.base import LLMProvider, LLMResponse, Message, TokenUsage
from app.providers.pricing import compute_cost


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        super().__init__(model)
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing — set it in .env")
        # Lazy import so the adapter layer imports cleanly without the SDK present.
        from google import genai

        self._client = genai.Client(api_key=api_key)

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        from google.genai import types

        system_instruction = (
            "\n".join(m.content for m in messages if m.role == "system") or None
        )
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part.from_text(text=m.content)],
            )
            for m in messages
            if m.role != "system"
        ]
        # Gemini 2.5+ are thinking models: internal reasoning consumes
        # max_output_tokens and can leave an EMPTY visible reply on small
        # budgets. Thinking is disabled by default (deterministic judge/router
        # usage, lower cost); callers can override via thinking_config kwarg.
        thinking_config = kwargs.pop(
            "thinking_config", types.ThinkingConfig(thinking_budget=0)
        )
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            thinking_config=thinking_config,
            **kwargs,
        )

        start = time.perf_counter()
        resp = await self._client.aio.models.generate_content(
            model=self.model, contents=contents, config=config
        )
        latency_ms = (time.perf_counter() - start) * 1000.0

        um = resp.usage_metadata
        usage = TokenUsage(
            prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
        )
        return LLMResponse(
            text=resp.text or "",
            provider=self.name,
            model=self.model,
            usage=usage,
            cost_usd=compute_cost(
                self.name, self.model, usage.prompt_tokens, usage.completion_tokens
            ),
            latency_ms=latency_ms,
        )
