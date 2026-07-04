"""In-memory guardrail event log (ring buffer).

Feeds the proof UI's guardrail panel: every injection check — pass or block —
is recorded with tenant, layer and rule. A bounded deque keeps memory constant;
this is deliberately process-local demo scope (a real deployment would emit to
Postgres or an event bus).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

_MAX_EVENTS = 100


@dataclass(frozen=True, slots=True)
class GuardrailEvent:
    ts: float  # unix epoch seconds
    tenant: str
    guardrail: str  # "prompt_injection"
    blocked: bool
    layer: str  # "pattern" | "llm" | "none"
    reason: str  # matched rule label, empty when passed
    query_preview: str  # first 80 chars — enough for the log, no full payloads


_events: deque[GuardrailEvent] = deque(maxlen=_MAX_EVENTS)


def record_injection_event(
    *, tenant: str, blocked: bool, layer: str, reason: str, query: str
) -> None:
    _events.append(
        GuardrailEvent(
            ts=time.time(),
            tenant=tenant,
            guardrail="prompt_injection",
            blocked=blocked,
            layer=layer,
            reason=reason,
            query_preview=query[:80],
        )
    )


def recent_events(limit: int = 25) -> list[dict[str, Any]]:
    """Newest first."""
    items = list(_events)[-limit:]
    return [asdict(e) for e in reversed(items)]


def blocked_count() -> int:
    return sum(1 for e in _events if e.blocked)
