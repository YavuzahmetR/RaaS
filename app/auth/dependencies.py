"""FastAPI auth dependencies — the switch that turns the JWT scaffold on.

Design (architecture decision D14):
- `AUTH_ENABLED=false` (default): endpoints keep working with an explicit
  `tenant`; no token needed — the demo/`docker compose up` stays frictionless.
- `AUTH_ENABLED=true`: tenant-scoped endpoints require a valid Bearer JWT.
  `resolve_tenant` then trusts the token's `tenant_id` claim and rejects any
  request whose stated tenant disagrees with it (403) — a caller cannot ask for
  a tenant it has not proven ownership of.

The retrieval-layer ACL (store.search mandatory tenant filter) still stands
underneath regardless; this adds authentication on top of that authorization.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.auth.jwt_auth import AuthError, TokenPayload, verify_token
from app.config import get_settings
from app.guardrails.acl import ACLError, ensure_tenant

_BEARER_PREFIX = "Bearer "


async def optional_auth(
    authorization: str | None = Header(default=None),
) -> TokenPayload | None:
    """Verify the Bearer JWT when auth is enabled; a no-op (None) when it isn't.

    Raises 401 when auth is on and the token is missing, malformed, expired or
    signed with the wrong secret.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    if not settings.jwt_secret:
        # Misconfiguration: auth demanded but no secret to verify against.
        raise HTTPException(status_code=500, detail="Auth enabled but JWT_SECRET is not set")
    token = authorization[len(_BEARER_PREFIX):].strip()
    try:
        return verify_token(token, secret=settings.jwt_secret)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


def resolve_tenant(requested: str | None, auth: TokenPayload | None) -> str:
    """Return the validated tenant to operate on, reconciling request and token.

    - auth disabled: use the explicit `requested` tenant (demo behavior).
    - auth enabled: trust the token's tenant; if `requested` is given and differs
      from the token's claim, reject with 403.
    """
    if auth is None:
        try:
            return ensure_tenant(requested or "")
        except ACLError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        token_tenant = ensure_tenant(auth.tenant_id)
    except ACLError as e:
        raise HTTPException(status_code=401, detail=f"Invalid tenant in token: {e}") from e

    if requested:
        try:
            if ensure_tenant(requested) != token_tenant:
                raise HTTPException(
                    status_code=403, detail="Tenant mismatch: token is not authorised for it"
                )
        except ACLError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return token_tenant
