"""POST /auth/token: demo credential → tenant-scoped JWT."""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

from app.auth import routes
from app.auth.jwt_auth import verify_token
from app.auth.routes import TokenRequest

SECRET = "test-secret"
PASSWORD = "demo-pass"


def _settings(enabled: bool = True, secret: str = SECRET, password: str = PASSWORD):
    return types.SimpleNamespace(
        auth_enabled=enabled, jwt_secret=secret, auth_demo_password=password
    )


def _issue(req: TokenRequest) -> dict:
    return asyncio.run(routes.issue_token(req))


def test_issue_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    out = _issue(TokenRequest(tenant="EvalCorp", password=PASSWORD))
    payload = verify_token(out["access_token"], secret=SECRET)
    assert payload.tenant_id == "evalcorp"  # normalised
    assert out["token_type"] == "bearer"


def test_issue_token_wrong_password_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    with pytest.raises(HTTPException) as exc:
        _issue(TokenRequest(tenant="acme", password="nope"))
    assert exc.value.status_code == 401


def test_issue_token_auth_disabled_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: _settings(enabled=False))
    with pytest.raises(HTTPException) as exc:
        _issue(TokenRequest(tenant="acme", password=PASSWORD))
    assert exc.value.status_code == 400


def test_issue_token_misconfigured_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: _settings(password=""))
    with pytest.raises(HTTPException) as exc:
        _issue(TokenRequest(tenant="acme", password=PASSWORD))
    assert exc.value.status_code == 500


def test_issue_token_bad_tenant_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    with pytest.raises(HTTPException) as exc:
        _issue(TokenRequest(tenant="!!bad!!", password=PASSWORD))
    assert exc.value.status_code == 400
