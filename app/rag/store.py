"""Qdrant vector store with tenant isolation enforced at the retrieval layer.

Multi-tenancy model: one collection, every point
carries a `tenant_id` payload field with a keyword index, and EVERY search goes
through `search()` — whose `tenant_id` parameter is mandatory and always becomes
a server-side filter. There is deliberately no unfiltered search function in
this module, so cross-tenant access is impossible by construction, not by
caller discipline. (This is the query-time ACL the guardrails phase tests.)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from app.config import get_settings
from app.rag.embeddings import EMBEDDING_DIM

log = logging.getLogger("raas.store")

COLLECTION = "docs"

_client: AsyncQdrantClient | None = None

T = TypeVar("T")


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=get_settings().qdrant_url)
    return _client


def _reset_client() -> None:
    global _client
    _client = None


async def _with_retry(op: Callable[[], Awaitable[T]]) -> T:
    """Retry once on transport-level failures.

    Long LLM calls between Qdrant requests let pooled keep-alive connections go
    stale (server closes them idle); the next request then races the close and
    fails with ResponseHandlingException. One retry on a fresh client resolves
    it; a second consecutive failure is a real outage and propagates.
    """
    try:
        return await op()
    except ResponseHandlingException:
        log.warning("qdrant transport error, retrying once with a fresh client")
        _reset_client()
        return await op()


async def ensure_collection() -> None:
    if not await _with_retry(lambda: get_client().collection_exists(COLLECTION)):
        await get_client().create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM, distance=models.Distance.COSINE
            ),
        )
        await get_client().create_payload_index(
            collection_name=COLLECTION,
            field_name="tenant_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


@dataclass(frozen=True, slots=True)
class Hit:
    text: str
    score: float
    doc_id: str
    source: str
    chunk_index: int


async def upsert_chunks(
    *,
    tenant_id: str,
    doc_id: str,
    source: str,
    texts: list[str],
    vectors: list[list[float]],
) -> int:
    await ensure_collection()
    points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "tenant_id": tenant_id,
                "doc_id": doc_id,
                "source": source,
                "chunk_index": i,
                "text": text,
            },
        )
        for i, (text, vec) in enumerate(zip(texts, vectors, strict=True))
    ]
    await _with_retry(lambda: get_client().upsert(collection_name=COLLECTION, points=points))
    return len(points)


async def search(
    *,
    tenant_id: str,
    query_vector: list[float],
    top_k: int = 5,
) -> list[Hit]:
    """Tenant-filtered vector search. `tenant_id` is mandatory by design."""
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required for every search (query-time ACL)")
    await ensure_collection()
    result = await _with_retry(
        lambda: get_client().query_points(
            collection_name=COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id", match=models.MatchValue(value=tenant_id)
                    )
                ]
            ),
        )
    )
    return [
        Hit(
            text=p.payload.get("text", ""),
            score=p.score,
            doc_id=p.payload.get("doc_id", ""),
            source=p.payload.get("source", ""),
            chunk_index=p.payload.get("chunk_index", -1),
        )
        for p in result.points
    ]
