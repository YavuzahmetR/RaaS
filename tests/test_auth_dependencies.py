"""Auth enforcement tests: the AUTH_ENABLED switch and tenant reconciliation.

Covers the security-critical logic added when wiring the JWT scaffold into the
endpoints (decision D14): tenant is trusted from the verified token, and a
request may not claim a tenant the token is not authorised for.
"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

from app.auth import dependencies as dep
from app.auth.jwt_auth import TokenPayload, create_token

SECRET = "test-secret"


def _settings(auth_enabled: bool, jwt_secret: str = SECRET) -> types.SimpleNamespace:
    return types.SimpleNamespace(auth_enabled=auth_enabled, jwt_secret=jwt_secret)


# --- resolve_tenant -------------------------------------------------------- #
def test_resolve_tenant_disabled_uses_request() -> None:
    assert dep.resolve_tenant("EvalCorp", None) == "evalcorp"  # normalised


def test_resolve_tenant_disabled_rejects_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        dep.resolve_tenant("", None)
    assert exc.value.status_code == 400


def test_resolve_tenant_enabled_trusts_token() -> None:
    tp = TokenPayload(subject="u", tenant_id="acme", expires_at=9_999_999_999)
    assert dep.resolve_tenant("acme", tp) == "acme"
    assert dep.resolve_tenant(None, tp) == "acme"  # token alone is enough


def test_resolve_tenant_enabled_rejects_mismatch() -> None:
    tp = TokenPayload(subject="u", tenant_id="acme", expires_at=9_999_999_999)
    with pytest.raises(HTTPException) as exc:
        dep.resolve_tenant("globex", tp)
    assert exc.value.status_code == 403


# --- optional_auth --------------------------------------------------------- #
def test_optional_auth_disabled_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dep, "get_settings", lambda: _settings(False))
    assert asyncio.run(dep.optional_auth(None)) is None


def test_optional_auth_enabled_requires_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dep, "get_settings", lambda: _settings(True))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep.optional_auth(None))
    assert exc.value.status_code == 401


def test_optional_auth_enabled_accepts_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dep, "get_settings", lambda: _settings(True))
    token = create_token(secret=SECRET, subject="u", tenant_id="acme")
    payload = asyncio.run(dep.optional_auth(f"Bearer {token}"))
    assert payload is not None and payload.tenant_id == "acme"


def test_optional_auth_enabled_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dep, "get_settings", lambda: _settings(True))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep.optional_auth("Bearer not.a.valid-token"))
    assert exc.value.status_code == 401


def test_optional_auth_enabled_without_secret_is_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dep, "get_settings", lambda: _settings(True, jwt_secret=""))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep.optional_auth("Bearer whatever"))
    assert exc.value.status_code == 500
