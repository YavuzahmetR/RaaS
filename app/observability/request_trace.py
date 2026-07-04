"""Per-request trace accumulator (ContextVar-based).

The SSE proof UI needs two numbers Langfuse has but the HTTP response didn't:
the real USD cost of every LLM call made while serving one request, and the
real latency of the rerank stage (which lives *inside* retrieve_chunks, not as
its own LangGraph node).

A `RequestTrace` is installed into a ContextVar at the start of a request.
`traced_generate` and the retrieval pipeline report into it if one is active;
when none is active (tests, eval runs) reporting is a no-op. ContextVars
propagate through awaits and into tasks created by LangGraph, and because the
installed object is shared (the ContextVar holds a reference), appends made in
child tasks are visible to the request handler.

The accumulator is intentionally a mutable collector — it is the one place
where mutation is the point. Individual records are frozen dataclasses.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LLMCallRecord:
    span: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float


@dataclass
class RequestTrace:
    """Mutable per-request collector; records themselves are immutable."""

    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    stage_ms: dict[str, float] = field(default_factory=dict)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(c.cost_usd for c in self.llm_calls), 6)

    @property
    def total_tokens(self) -> dict[str, int]:
        return {
            "prompt": sum(c.prompt_tokens for c in self.llm_calls),
            "completion": sum(c.completion_tokens for c in self.llm_calls),
        }


_current: ContextVar[RequestTrace | None] = ContextVar("raas_request_trace", default=None)


def start_trace() -> RequestTrace:
    """Install a fresh trace for the current request context and return it."""
    trace = RequestTrace()
    _current.set(trace)
    return trace


def clear_trace() -> None:
    _current.set(None)


def current_trace() -> RequestTrace | None:
    return _current.get()


def record_llm_call(record: LLMCallRecord) -> None:
    trace = _current.get()
    if trace is not None:
        trace.llm_calls.append(record)


def record_stage(name: str, latency_ms: float) -> None:
    """Record a sub-node pipeline stage (e.g. rerank inside retrieve)."""
    trace = _current.get()
    if trace is not None:
        trace.stage_ms[name] = round(latency_ms, 1)


def pop_stage(name: str) -> float | None:
    """Read-and-remove a stage timing (so loop iterations don't reuse it)."""
    trace = _current.get()
    if trace is None:
        return None
    return trace.stage_ms.pop(name, None)
