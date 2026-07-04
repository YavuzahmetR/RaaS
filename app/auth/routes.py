"""Demo token issuance — the "login" of the proof console.

POST /auth/token exchanges (tenant, demo password) for a short-lived HS256 JWT
carrying the tenant claim. This stands in for a real identity provider: in
production you would swap this endpoint for Supabase/OIDC and keep everything
else (verification, tenant reconciliation) unchanged — see D2/D14.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth.jwt_auth import create_token
from app.config import get_settings
from app.guardrails.acl import ACLError, ensure_tenant

TOKEN_TTL_S = 8 * 3600  # demo session length

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/token")
async def issue_token(req: TokenRequest) -> dict:
    """Mint a tenant-scoped Bearer token after checking the demo password."""
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled (AUTH_ENABLED=false)")
    if not settings.jwt_secret or not settings.auth_demo_password:
        raise HTTPException(
            status_code=500, detail="Auth misconfigured: JWT_SECRET/AUTH_DEMO_PASSWORD unset"
        )
    if not hmac.compare_digest(req.password, settings.auth_demo_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    try:
        tenant = ensure_tenant(req.tenant)
    except ACLError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    token = create_token(
        secret=settings.jwt_secret,
        subject=f"demo:{tenant}",
        tenant_id=tenant,
        ttl_s=TOKEN_TTL_S,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_S,
        "tenant": tenant,
    }
