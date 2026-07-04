"""End-to-end: ingest a fresh document → ask → grounded answer with citations.

Uses a unique tenant per run so the test is self-contained and repeatable.
Also proves ingest-side PII redaction end to end: the uploaded document
contains an email address which must never come back in search results.
"""

from __future__ import annotations

import uuid

from tests.conftest import requires_api

DOC = """\
Initech Vacation Policy

Employees receive 15 days of paid vacation in their first year, increasing to
25 days after five years of service. Vacation requests go to vacation-desk@initech.example.

Initech On-call Compensation

Engineers on the weekly on-call rotation receive a flat stipend of 4200 TRY per
week plus compensatory time off for any incident handled outside business hours.
"""


@requires_api
def test_ingest_then_query_returns_cited_grounded_answer(client) -> None:
    tenant = f"e2e-{uuid.uuid4().hex[:8]}"

    # 1) ingest
    resp = client.post(
        f"/ingest?tenant={tenant}",
        files={"file": ("initech_policy.txt", DOC.encode(), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunks"] >= 1

    # 2) retrieval sanity + ingest-side PII redaction proof
    resp = client.get(
        "/search", params={"tenant": tenant, "q": "on-call stipend amount", "k": 3}
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits, "no hits for freshly ingested document"
    assert any("4200" in h["text"] for h in hits)
    assert all("vacation-desk@initech.example" not in h["text"] for h in hits), (
        "ingest-side PII redaction failed: raw email stored in vector payload"
    )

    # 3) agentic query → grounded, cited answer
    resp = client.post(
        "/query",
        json={"tenant": tenant, "query": "What is the weekly on-call stipend at Initech?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "4200" in body["answer"]
    assert body["citations"], "answer has no citations"
    assert body["citations"][0]["source"] == "initech_policy.txt"
    assert body["route"] == "docs"
    assert "retrieve" in body["steps"]
