"""Agent state schema shared by all LangGraph nodes.

LangGraph owns state merging, so this is a TypedDict (not a frozen dataclass):
each node returns only the keys it changed and never mutates the incoming dict.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# Hard cap on self-check → re-retrieve loops (infinite-loop protection).
MAX_SELF_CHECK_ITERATIONS = 2

Route = Literal["direct", "docs", "list_docs"]


class AgentState(TypedDict, total=False):
    # Inputs
    query: str
    tenant_id: str

    # Router decision
    route: Route

    # Retrieval working set (current_query may be reformulated by self_check)
    current_query: str
    retrieved_docs: list[dict[str, Any]]

    # Generation
    answer: str

    # Self-check loop
    self_check_iterations: int
    grounded: bool

    # Output
    citations: list[dict[str, Any]]
    confidence: float

    # Executed node names, in order — makes the loop visible in logs/responses.
    steps: list[str]
