"""JWT scaffold tests: signature, expiry, tenant claim."""

from __future__ import annotations

import pytest

from app.auth.jwt_auth import AuthError, create_token, verify_token

SECRET = "test-secret"


def test_roundtrip_valid_token() -> None:
    token = create_token(secret=SECRET, subject="user-1", tenant_id="acme")
    payload = verify_token(token, secret=SECRET)
    assert payload.subject == "user-1"
    assert payload.tenant_id == "acme"


def test_wrong_secret_rejected() -> None:
    token = create_token(secret=SECRET, subject="user-1", tenant_id="acme")
    with pytest.raises(AuthError, match="signature"):
        verify_token(token, secret="other-secret")


def test_expired_token_rejected() -> None:
    token = create_token(secret=SECRET, subject="user-1", tenant_id="acme", ttl_s=-10)
    with pytest.raises(AuthError, match="expired"):
        verify_token(token, secret=SECRET)


def test_tampered_payload_rejected() -> None:
    token = create_token(secret=SECRET, subject="user-1", tenant_id="acme")
    header, payload, sig = token.split(".")
    tampered = f"{header}.{payload[:-2]}xx.{sig}"
    with pytest.raises(AuthError):
        verify_token(tampered, secret=SECRET)


def test_malformed_token_rejected() -> None:
    with pytest.raises(AuthError, match="Malformed"):
        verify_token("not-a-jwt", secret=SECRET)
