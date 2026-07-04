"""FastAPI entrypoint.

Phase 1: /health. Phase 2: /ingest, /search, /documents. Phase 3: /query.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.agent.graph import run_agent
from app.api.insights import router as insights_router
from app.api.stream import router as stream_router
from app.auth.dependencies import optional_auth, resolve_tenant
from app.auth.jwt_auth import TokenPayload
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.guardrails.acl import ACLError
from app.guardrails.events import record_injection_event
from app.guardrails.injection import check_query
from app.guardrails.pii import redact
from app.observability.request_trace import clear_trace, start_trace
from app.providers.factory import available_providers
from app.rag import metadata
from app.rag.ingest import IngestError, ingest_document
from app.rag.retrieve import retrieve_chunks

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await metadata.close_pool()


app = FastAPI(
    title="RaaS — Agentic RAG-as-a-Service",
    version="0.2.0",
    summary="Self-hostable, multi-tenant, fully-instrumented agentic RAG backend.",
    lifespan=lifespan,
)

# Proof-UI routers: SSE pipeline trace + read-only insight endpoints.
app.include_router(stream_router)
app.include_router(insights_router)
app.include_router(auth_router)


@app.get("/health")
async def health() -> dict:
    """Liveness probe used by docker-compose healthchecks and smoke tests."""
    return {
        "status": "ok",
        "service": "raas",
        "env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "providers": available_providers(),
    }


@app.post("/ingest")
async def ingest(
    tenant: str = Query(..., min_length=1, description="Tenant identifier"),
    file: UploadFile = File(...),
    auth: TokenPayload | None = Depends(optional_auth),
) -> dict:
    """Upload a document: parse → chunk → embed → Qdrant (+ metadata to Postgres)."""
    tenant = resolve_tenant(tenant, auth)
    payload = await file.read()
    try:
        result = await ingest_document(
            tenant_id=tenant, filename=file.filename or "upload", payload=payload
        )
    except (IngestError, ACLError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "doc_id": result.doc_id,
        "tenant": result.tenant_id,
        "filename": result.filename,
        "chunks": result.chunk_count,
    }


@app.get("/search")
async def search(
    tenant: str = Query(..., min_length=1),
    q: str = Query(..., min_length=1, description="Search query"),
    k: int = Query(default=None, ge=1, le=20),
    rerank: bool | None = Query(default=None, description="Override RERANK_ENABLED"),
    auth: TokenPayload | None = Depends(optional_auth),
) -> dict:
    """Tenant-filtered vector search over ingested chunks (retrieval only, no LLM)."""
    tenant = resolve_tenant(tenant, auth)
    hits = await retrieve_chunks(tenant_id=tenant, query=q, top_k=k, use_rerank=rerank)
    return {
        "tenant": tenant,
        "query": q,
        "hits": [
            {
                "score": round(h.score, 4),
                "text": h.text,
                "doc_id": h.doc_id,
                "source": h.source,
                "chunk_index": h.chunk_index,
            }
            for h in hits
        ],
    }


class QueryRequest(BaseModel):
    tenant: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=4000)


class EvalRequest(BaseModel):
    mode: str = Field(default="retrieval", pattern="^(retrieval|generation)$")
    limit: int | None = Field(default=None, ge=1, le=50)
    rerank: bool = False


@app.post("/eval/run")
async def eval_run(req: EvalRequest) -> dict:
    """Trigger the eval harness. mode=retrieval → recall@k/MRR (fast);
    mode=generation → full agent + LLM-judge metrics (slow, use limit)."""
    from eval.common import save_result
    from eval.retrieval_eval import run_retrieval_eval
    from eval.run_ragas import run_generation_eval

    if req.mode == "retrieval":
        result = await run_retrieval_eval(use_rerank=req.rerank, limit=req.limit)
    else:
        result = await run_generation_eval(limit=req.limit)
    path = save_result(f"{req.mode}_api", result)
    return {"mode": req.mode, "metrics": result["metrics"], "saved": str(path)}


@app.post("/query")
async def query(
    req: QueryRequest, auth: TokenPayload | None = Depends(optional_auth)
) -> dict:
    """Agentic RAG: router → retrieve → generate → self_check (max 2 loops) → cite.

    Guardrails: tenant ACL validation → dual-layer injection check → agent →
    PII redaction on the outgoing answer.
    """
    start = time.perf_counter()
    tenant = resolve_tenant(req.tenant, auth)

    verdict = await check_query(req.query)
    record_injection_event(
        tenant=tenant,
        blocked=verdict.blocked,
        layer=verdict.layer,
        reason=verdict.reason,
        query=req.query,
    )
    if verdict.blocked:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "query_blocked",
                "guardrail": "prompt_injection",
                "layer": verdict.layer,
                "reason": verdict.reason,
            },
        )

    trace = start_trace()
    try:
        state = await run_agent(query=req.query, tenant_id=tenant)
    finally:
        clear_trace()
    return {
        "answer": redact(state.get("answer", "")),
        "citations": state.get("citations", []),
        "confidence": state.get("confidence", 0.0),
        "route": state.get("route"),
        "grounded": state.get("grounded"),
        "self_check_iterations": state.get("self_check_iterations", 0),
        "steps": state.get("steps", []),
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "cost_usd": trace.total_cost_usd,
    }


@app.get("/documents")
async def documents(
    tenant: str = Query(..., min_length=1),
    auth: TokenPayload | None = Depends(optional_auth),
) -> dict:
    """List ingested documents for a tenant (metadata from Postgres)."""
    tenant = resolve_tenant(tenant, auth)
    docs = await metadata.list_documents(tenant)
    for d in docs:
        d["doc_id"] = str(d["doc_id"])
        d["created_at"] = d["created_at"].isoformat()
    return {"tenant": tenant, "documents": docs}
