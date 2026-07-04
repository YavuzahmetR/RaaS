"""Agent tools with an explicit allowlist.

Every tool the agent can invoke lives in `TOOL_REGISTRY`; anything not in the
registry cannot be called, period. (Phase 5 guardrails test this property.)
Current tools:
  - list_documents: tenant-scoped metadata query (which docs exist for me?)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.rag import metadata


async def list_documents(tenant_id: str) -> list[dict[str, Any]]:
    """Return the tenant's ingested documents (doc metadata from Postgres)."""
    docs = await metadata.list_documents(tenant_id)
    return [
        {
            "doc_id": str(d["doc_id"]),
            "filename": d["filename"],
            "chunk_count": d["chunk_count"],
            "created_at": d["created_at"].isoformat(),
        }
        for d in docs
    ]


TOOL_REGISTRY: dict[str, Callable[..., Awaitable[Any]]] = {
    "list_documents": list_documents,
}


async def call_tool(name: str, **kwargs: Any) -> Any:
    """Invoke an allowlisted tool. Unknown names are rejected, not looked up."""
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        raise PermissionError(f"Tool {name!r} is not allowlisted. Allowed: {sorted(TOOL_REGISTRY)}")
    return await tool(**kwargs)
