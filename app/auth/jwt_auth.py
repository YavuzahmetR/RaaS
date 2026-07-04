"""JWT verification scaffold (Supabase-compatible).

Status: scaffolded, NOT yet enforced on endpoints — listed under "known limits"
in the README. The demo uses explicit tenant ids; production turns this on by
adding `Depends(require_tenant)` to the endpoints.

Supabase-ready: Supabase issues standard HS256 JWTs signed with the project's
JWT secret and carries the tenant in a claim — exactly what `verify_token`
checks. Swapping local JWTs for Supabase auth is configuration (secret +
claim name), not code.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

JWT_ALG = "HS256"
TENANT_CLAIM = "tenant_id"


class AuthError(ValueError):
    """Token invalid, expired, or missing required claims."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    subject: str
    tenant_id: str
    expires_at: int


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def create_token(*, secret: str, subject: str, tenant_id: str, ttl_s: int = 3600) -> str:
    """Mint an HS256 JWT (used by tests and local development)."""
    header = _b64url_encode(json.dumps({"alg": JWT_ALG, "typ": "JWT"}).encode())
    payload = _b64url_encode(
        json.dumps(
            {"sub": subject, TENANT_CLAIM: tenant_id, "exp": int(time.time()) + ttl_s}
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url_encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_token(token: str, *, secret: str) -> TokenPayload:
    """Validate signature, expiry and tenant claim. Raises AuthError."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as e:
        raise AuthError("Malformed token") from e

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise AuthError("Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise AuthError("Token expired")
    tenant = payload.get(TENANT_CLAIM, "")
    if not tenant:
        raise AuthError(f"Missing {TENANT_CLAIM} claim")
    return TokenPayload(
        subject=payload.get("sub", ""), tenant_id=tenant, expires_at=payload["exp"]
    )
