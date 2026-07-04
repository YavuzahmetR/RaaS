"""LangGraph state machine wiring.

    START → router ─┬─ "direct"    → generate ────────────────→ cite → END
                    ├─ "list_docs" → list_docs (tool) ────────────────→ END
                    └─ "docs"      → retrieve → generate → self_check ─┬→ cite → END
                                        ▲                              │
                                        └───── (not grounded, <2) ─────┘
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import MAX_SELF_CHECK_ITERATIONS, AgentState
from app.observability.langfuse_setup import finalize_trace, observe

_compiled = None


def _route_after_router(state: AgentState) -> str:
    return state.get("route", "docs")


def _route_after_generate(state: AgentState) -> str:
    return "self_check" if state.get("route") == "docs" else "cite"


def _route_after_self_check(state: AgentState) -> str:
    retries_left = state.get("self_check_iterations", 0) < MAX_SELF_CHECK_ITERATIONS
    if not state.get("grounded", True) and retries_left:
        return "retrieve"
    return "cite"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("router", nodes.router)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("generate", nodes.generate)
    g.add_node("self_check", nodes.self_check)
    g.add_node("cite", nodes.cite)
    g.add_node("list_docs", nodes.list_docs)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        _route_after_router,
        {"docs": "retrieve", "direct": "generate", "list_docs": "list_docs"},
    )
    g.add_edge("retrieve", "generate")
    g.add_conditional_edges(
        "generate", _route_after_generate, {"self_check": "self_check", "cite": "cite"}
    )
    g.add_conditional_edges(
        "self_check", _route_after_self_check, {"retrieve": "retrieve", "cite": "cite"}
    )
    g.add_edge("cite", END)
    g.add_edge("list_docs", END)
    return g.compile()


def get_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


@observe(name="raas-query")
async def run_agent(*, query: str, tenant_id: str) -> AgentState:
    initial: AgentState = {
        "query": query,
        "tenant_id": tenant_id,
        "self_check_iterations": 0,
        "steps": [],
    }
    state = await get_graph().ainvoke(initial)
    finalize_trace(tenant_id=tenant_id, query=query, state=dict(state))
    return state
