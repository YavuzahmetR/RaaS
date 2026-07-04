"""Query-time access control.

The hard guarantee lives in the retrieval layer: `app.rag.store.search` has a
mandatory `tenant_id` parameter that always becomes a server-side Qdrant filter
— there is no unfiltered search function in the codebase, so cross-tenant reads
are impossible by construction, not by caller discipline.

This module adds the API-boundary layer: tenant identifiers are validated
before any handler logic runs, so malformed/empty tenants fail fast with a
clear message instead of propagating downstream.

OWASP LLM Top 10 mapping: LLM08 (Excessive Agency) / broken access control.
"""

from __future__ import annotations

import re

_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class ACLError(ValueError):
    """Tenant validation failure (maps to HTTP 400/422 at the API boundary)."""


def ensure_tenant(tenant: str) -> str:
    """Validate and normalise a tenant identifier. Raises ACLError if invalid."""
    tenant = (tenant or "").strip().lower()
    if not _TENANT_RE.match(tenant):
        raise ACLError(
            "Invalid tenant id: must be 1-64 chars of [a-z0-9_-], starting alphanumeric."
        )
    return tenant
