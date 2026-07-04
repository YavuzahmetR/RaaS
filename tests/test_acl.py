"""Query-time ACL tests: tenant A must never see tenant B's documents."""

from __future__ import annotations

import pytest

from app.guardrails.acl import ACLError, ensure_tenant
from tests.conftest import requires_api

# --- Unit: tenant validation at the API boundary -------------------------- #


@pytest.mark.parametrize("tenant", ["acme", "globex-2", "a", "tenant_x", "ACME"])
def test_valid_tenants_accepted(tenant: str) -> None:
    assert ensure_tenant(tenant) == tenant.strip().lower()


@pytest.mark.parametrize("tenant", ["", "  ", "-leading", "has space", "x" * 65, "a;drop"])
def test_invalid_tenants_rejected(tenant: str) -> None:
    with pytest.raises(ACLError):
        ensure_tenant(tenant)


# --- Integration: cross-tenant isolation on the live stack ---------------- #
# Precondition (created in Phase 2 verification): tenant `acme` owns
# hr_policy_acme.md and tenant `globex` owns it_policy_globex.pdf.


@requires_api
def test_tenant_cannot_read_other_tenants_documents(client) -> None:
    # globex asks about content that exists ONLY in acme's document.
    resp = client.get(
        "/search", params={"tenant": "globex", "q": "annual leave carried over days", "k": 5}
    )
    assert resp.status_code == 200
    for hit in resp.json()["hits"]:
        assert hit["source"] != "hr_policy_acme.md", "ACL BREACH: cross-tenant document returned"


@requires_api
def test_unknown_tenant_sees_nothing(client) -> None:
    resp = client.get("/search", params={"tenant": "intruder", "q": "leave policy", "k": 5})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


@requires_api
def test_documents_endpoint_is_tenant_scoped(client) -> None:
    resp = client.get("/documents", params={"tenant": "globex"})
    assert resp.status_code == 200
    filenames = {d["filename"] for d in resp.json()["documents"]}
    assert "hr_policy_acme.md" not in filenames
