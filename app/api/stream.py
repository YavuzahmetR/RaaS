"""SSE trace stream: the agentic pipeline as real-time events.

POST /query/stream runs the same guardrails and the same LangGraph graph as
POST /query, but consumes it with `astream(stream_mode="updates")` so every
node completion becomes a Server-Sent Event carrying its *measured* latency.
Nothing here is animated on a timer — if the UI shows a node lighting up, a
node actually finished.

Event protocol (each SSE `data:` line is one JSON object):
    {"type": "accepted",  ...}                    request passed validation
    {"type": "guardrail", "blocked": bool, ...}   injection verdict (+latency)
    {"type": "node", "node": "...", "status": "ok", "latency_ms": ..., "detail": {...}}
    {"type": "answer",   ...}                     final answer + citations
    {"type": "summary",  ...}                     total latency + real USD cost
    {"type": "done"} | {"type": "error", ...}

Rerank is not a LangGraph node (it runs inside retrieve_chunks), so its real
latency is captured via request_trace.record_stage and re-emitted here as its
own pipeline stage — measured, not synthesized.

Langfuse note: the non-streaming /query wraps the run in one root trace
(`@observe` on run_agent). Streaming consumes the graph directly, so node spans
surface as individual traces instead of one nested tree — an accepted tradeoff
for real-time events.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import get_graph
from app.auth.dependencies import optional_auth, resolve_tenant
from app.auth.jwt_auth import TokenPayload
from app.guardrails.events import record_injection_event
from app.guardrails.injection import check_query
from app.guardrails.pii import redact
from app.observability.request_trace import clear_trace, pop_stage, start_trace

router = APIRouter(tags=["proof-ui"])


class StreamQueryRequest(BaseModel):
    tenant: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=4000)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _node_detail(node: str, update: dict[str, Any]) -> dict[str, Any]:
    """Small, UI-relevant summary of what a node produced (no full payloads)."""
    if node == "router":
        return {"route": update.get("route")}
    if node == "retrieve":
        return {"hits": len(update.get("retrieved_docs", []))}
    if node == "generate":
        return {"answer_chars": len(update.get("answer", ""))}
    if node == "self_check":
        return {
            "grounded": update.get("grounded"),
            "iteration": update.get("self_check_iterations"),
        }
    if node == "cite":
        return {
            "citations": len(update.get("citations", [])),
            "confidence": update.get("confidence"),
        }
    if node == "list_docs":
        return {"tool": "list_documents"}
    return {}


async def _event_stream(req: StreamQueryRequest, tenant: str) -> AsyncIterator[str]:
    trace = start_trace()
    t_start = time.perf_counter()
    try:
        yield _sse({"type": "accepted", "tenant": tenant, "query": req.query})

        # --- Guardrail: dual-layer injection check (recorded pass or block) ---
        g_started = time.perf_counter()
        verdict = await check_query(req.query)
        g_ms = round((time.perf_counter() - g_started) * 1000)
        record_injection_event(
            tenant=tenant,
            blocked=verdict.blocked,
            layer=verdict.layer,
            reason=verdict.reason,
            query=req.query,
        )
        yield _sse(
            {
                "type": "guardrail",
                "guardrail": "prompt_injection",
                "blocked": verdict.blocked,
                "layer": verdict.layer,
                "reason": verdict.reason,
                "latency_ms": g_ms,
            }
        )
        if verdict.blocked:
            yield _sse({"type": "done", "outcome": "blocked"})
            return

        # --- Agentic loop: one SSE event per completed LangGraph node ---------
        state: dict[str, Any] = {
            "query": req.query,
            "tenant_id": tenant,
            "self_check_iterations": 0,
            "steps": [],
        }
        merged: dict[str, Any] = dict(state)
        last = time.perf_counter()
        async for chunk in get_graph().astream(state, stream_mode="updates"):
            now = time.perf_counter()
            node_ms = round((now - last) * 1000)
            last = now
            for node, update in chunk.items():
                merged.update(update or {})
                if node == "retrieve":
                    # rerank ran inside this node; split its measured share out
                    # so the UI can light it as its own stage.
                    rerank_ms = pop_stage("rerank")
                    retrieve_ms = (
                        max(node_ms - round(rerank_ms), 0) if rerank_ms is not None else node_ms
                    )
                    yield _sse(
                        {
                            "type": "node",
                            "node": "retrieve",
                            "status": "ok",
                            "latency_ms": retrieve_ms,
                            "detail": _node_detail(node, update or {}),
                        }
                    )
                    yield _sse(
                        {
                            "type": "node",
                            "node": "rerank",
                            "status": "ok" if rerank_ms is not None else "skipped",
                            "latency_ms": round(rerank_ms) if rerank_ms is not None else 0,
                            "detail": {},
                        }
                    )
                else:
                    yield _sse(
                        {
                            "type": "node",
                            "node": node,
                            "status": "ok",
                            "latency_ms": node_ms,
                            "detail": _node_detail(node, update or {}),
                        }
                    )

        total_ms = round((time.perf_counter() - t_start) * 1000)
        yield _sse(
            {
                "type": "answer",
                "answer": redact(merged.get("answer", "")),
                "citations": merged.get("citations", []),
                "confidence": merged.get("confidence", 0.0),
                "route": merged.get("route"),
                "grounded": merged.get("grounded"),
                "self_check_iterations": merged.get("self_check_iterations", 0),
                "steps": merged.get("steps", []),
            }
        )
        yield _sse(
            {
                "type": "summary",
                "total_latency_ms": total_ms,
                "cost_usd": trace.total_cost_usd,
                "llm_calls": len(trace.llm_calls),
                "tokens": trace.total_tokens,
            }
        )
        yield _sse({"type": "done", "outcome": "ok"})
    except Exception as e:  # surface, never swallow — the UI shows the failure
        yield _sse({"type": "error", "stage": "agent", "message": str(e)})
    finally:
        clear_trace()


@router.post("/query/stream")
async def query_stream(
    req: StreamQueryRequest, auth: TokenPayload | None = Depends(optional_auth)
) -> StreamingResponse:
    """Agentic RAG with a real-time SSE trace of every pipeline stage."""
    # Auth + tenant resolution happen BEFORE streaming so 401/403/400 surface as
    # real HTTP status codes rather than mid-stream error events.
    tenant = resolve_tenant(req.tenant, auth)
    return StreamingResponse(
        _event_stream(req, tenant),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx (the UI container) must not buffer the event stream.
            "X-Accel-Buffering": "no",
        },
    )
