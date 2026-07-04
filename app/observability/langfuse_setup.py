"""Langfuse wiring (SDK v2, matches the self-hosted Langfuse v2 server).

Design:
  - `observe` is re-exported from here. When Langfuse keys are configured it is
    the real decorator (each decorated agent node becomes a span, nested under
    the request's root trace); when keys are missing it degrades to a no-op so
    the application never hard-depends on observability being up.
  - `traced_generate()` wraps every LLM call as a Langfuse *generation* carrying
    model, token usage and the real USD cost computed by the provider adapter.
  - `finalize_trace()` stamps tenant/route/confidence on the root trace and
    flushes (SDK batches in a background thread; we flush per request so traces
    are immediately visible).
"""

from __future__ import annotations

import os
from typing import Any

from app.config import get_settings
from app.observability.request_trace import LLMCallRecord, record_llm_call
from app.providers.base import LLMResponse, Message
from app.providers.factory import get_provider

_settings = get_settings()
ENABLED = bool(_settings.langfuse_public_key and _settings.langfuse_secret_key)

if ENABLED:
    # The decorators SDK reads configuration from env vars.
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", _settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", _settings.langfuse_host)
    from langfuse.decorators import langfuse_context, observe
else:  # pragma: no cover - exercised only when observability is off
    langfuse_context = None

    def observe(*d_args: Any, **d_kwargs: Any):  # type: ignore[misc]
        """No-op stand-in supporting both @observe and @observe(...) forms."""
        if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
            return d_args[0]

        def wrap(fn):
            return fn

        return wrap


@observe(as_type="generation")
async def traced_generate(
    span_name: str,
    messages: list[Message],
    *,
    provider_name: str | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """LLM call traced as a Langfuse generation with tokens + real USD cost."""
    resp = await get_provider(provider_name).generate(messages, **kwargs)
    # Feed the per-request accumulator (proof UI cost summary); no-op when no
    # request trace is active (eval runs, tests).
    record_llm_call(
        LLMCallRecord(
            span=span_name,
            provider=resp.provider,
            model=resp.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            cost_usd=resp.cost_usd,
            latency_ms=resp.latency_ms,
        )
    )
    if ENABLED:
        langfuse_context.update_current_observation(
            name=span_name,
            model=f"{resp.provider}/{resp.model}",
            input=[{"role": m.role, "content": m.content} for m in messages],
            output=resp.text,
            usage={
                "input": resp.usage.prompt_tokens,
                "output": resp.usage.completion_tokens,
                "total": resp.usage.total_tokens,
                "unit": "TOKENS",
                "total_cost": resp.cost_usd,
            },
            metadata={"latency_ms": round(resp.latency_ms), "cost_usd": resp.cost_usd},
        )
    return resp


def finalize_trace(*, tenant_id: str, query: str, state: dict[str, Any]) -> None:
    """Stamp summary fields on the root trace and flush the batch."""
    if not ENABLED:
        return
    langfuse_context.update_current_trace(
        name="raas-query",
        user_id=tenant_id,
        input=query,
        output=state.get("answer", ""),
        metadata={
            "route": state.get("route"),
            "grounded": state.get("grounded"),
            "confidence": state.get("confidence"),
            "self_check_iterations": state.get("self_check_iterations"),
            "steps": state.get("steps", []),
        },
        tags=[f"route:{state.get('route')}"],
    )
    langfuse_context.flush()
