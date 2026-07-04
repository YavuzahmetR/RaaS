"""Retrieval pipeline: embed → tenant-filtered vector search → optional rerank.

Single entry point used by the agent, /search and the eval harness, so a
pipeline change is automatically measured by the same eval everywhere.
"""

from __future__ import annotations

import time

from app.config import get_settings
from app.observability.request_trace import record_stage
from app.rag import rerank as rr
from app.rag.embeddings import embed_query
from app.rag.store import Hit
from app.rag.store import search as vector_search


async def retrieve_chunks(
    *,
    tenant_id: str,
    query: str,
    top_k: int | None = None,
    use_rerank: bool | None = None,
) -> list[Hit]:
    """`use_rerank=None` falls back to the RERANK_ENABLED config default."""
    settings = get_settings()
    k = top_k or settings.retrieval_top_k
    enabled = settings.rerank_enabled if use_rerank is None else use_rerank

    vector = await embed_query(query)
    fetch_k = k * rr.FETCH_MULTIPLIER if enabled else k
    hits: list[Hit] = await vector_search(tenant_id=tenant_id, query_vector=vector, top_k=fetch_k)
    if enabled:
        # Timed separately so the proof UI can show rerank as its own pipeline
        # stage with a real measured latency (it is not a LangGraph node).
        started = time.perf_counter()
        hits = await rr.rerank(query, hits, k)
        record_stage("rerank", (time.perf_counter() - started) * 1000)
    return hits
