"""Shared fixtures.

Unit tests (pattern/PII/ACL validation) run anywhere with no services.
Integration tests hit the live stack at API_URL (default http://localhost:8000)
and are skipped automatically when the API is not reachable, so `pytest` never
fails just because docker-compose is down.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from app.auth.jwt_auth import create_token

API_URL = os.environ.get("API_URL", "http://localhost:8000")
# Matches the .env default; override when testing against a differently-keyed API.
JWT_SECRET = os.environ.get("TEST_JWT_SECRET", "dev-jwt-secret-change-me")


class TenantTokenAuth(httpx.Auth):
    """Attach a tenant-scoped Bearer JWT to every live-API request.

    The tenant is read from the request itself (query param or JSON body), so
    cross-tenant tests keep working: each request gets a token for the tenant
    it claims, and the API's 403 mismatch path stays testable by NOT matching
    only when a test explicitly forges headers. Harmless when AUTH_ENABLED=false
    (the header is simply ignored).
    """

    def auth_flow(self, request: httpx.Request):
        tenant = request.url.params.get("tenant")
        if tenant is None and request.content:
            try:
                tenant = json.loads(request.content.decode("utf-8")).get("tenant")
            except (ValueError, AttributeError):
                tenant = None
        if tenant:
            token = create_token(secret=JWT_SECRET, subject="pytest", tenant_id=tenant)
            request.headers["Authorization"] = f"Bearer {token}"
        yield request


def _api_alive() -> bool:
    try:
        return httpx.get(f"{API_URL}/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


requires_api = pytest.mark.skipif(
    not _api_alive(), reason=f"live API not reachable at {API_URL}"
)


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API_URL,
        timeout=httpx.Timeout(300.0, connect=10.0),
        auth=TenantTokenAuth(),
    ) as c:
        yield c
