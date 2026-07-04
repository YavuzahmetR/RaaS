"""Document metadata persistence (Postgres via asyncpg).

Stores who ingested what, when, for which tenant — the relational side of the
multi-tenant story (Qdrant holds vectors, Postgres holds provenance/ACL data).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id      UUID PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    filename    TEXT NOT NULL,
    source      TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents (tenant_id);
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(get_settings().postgres_dsn, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_SCHEMA)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def record_document(
    *, doc_id: str, tenant_id: str, filename: str, source: str, chunk_count: int
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO documents (doc_id, tenant_id, filename, source, chunk_count)
               VALUES ($1, $2, $3, $4, $5)""",
            doc_id,
            tenant_id,
            filename,
            source,
            chunk_count,
        )


async def list_tenants() -> list[str]:
    """Distinct tenants that have ingested at least one document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT tenant_id FROM documents ORDER BY tenant_id")
    return [r["tenant_id"] for r in rows]


async def list_documents(tenant_id: str) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT doc_id, tenant_id, filename, source, chunk_count, created_at
               FROM documents WHERE tenant_id = $1 ORDER BY created_at DESC""",
            tenant_id,
        )
    return [dict(r) for r in rows]
