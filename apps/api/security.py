from __future__ import annotations
import time
from dataclasses import dataclass
import httpx
from fastapi import HTTPException, Request, status
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.config import settings


@dataclass(slots=True)
class Principal:
    user_id: str
    email: str | None
    claims: dict


_JWKS_CACHE: tuple[float, dict] | None = None


async def _jwks() -> dict:
    global _JWKS_CACHE
    if _JWKS_CACHE and time.time() - _JWKS_CACHE[0] < 3600:
        return _JWKS_CACHE[1]
    if not settings.effective_jwks_url:
        raise RuntimeError("Supabase JWKS URL is not configured")
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(settings.effective_jwks_url)
        r.raise_for_status()
        data = r.json()
    _JWKS_CACHE = (time.time(), data)
    return data


async def current_principal(request: Request) -> Principal:
    if settings.auth_mode == "dev":
        return Principal(settings.dev_user_id, settings.dev_user_email, {"sub": settings.dev_user_id, "email": settings.dev_user_email, "dev": True})

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = header.split(" ", 1)[1]
    try:
        unverified = jwt.get_unverified_header(token)
        keys = (await _jwks()).get("keys", [])
        key = next(k for k in keys if k.get("kid") == unverified.get("kid"))
        claims = jwt.decode(
            token,
            key,
            algorithms=[unverified.get("alg", "ES256")],
            audience="authenticated",
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None,
            options={"verify_aud": True, "verify_iss": bool(settings.supabase_url)},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    return Principal(user_id=claims["sub"], email=claims.get("email"), claims=claims)


async def ensure_profile(db: AsyncSession, principal: Principal) -> None:
    await db.execute(text("""
      INSERT INTO profiles(id,email) VALUES(:id,:email)
      ON CONFLICT(id) DO UPDATE SET email=COALESCE(EXCLUDED.email,profiles.email)
    """), {"id": principal.user_id, "email": principal.email})


async def require_workspace_role(workspace_id: str, principal: Principal, db: AsyncSession, allowed: set[str]):
    q = text("SELECT role FROM workspace_members WHERE workspace_id=:w AND user_id=:u AND status='active'")
    role = (await db.execute(q, {"w": workspace_id, "u": principal.user_id})).scalar_one_or_none()
    if role not in allowed:
        raise HTTPException(status_code=403, detail="Workspace access denied")
    return role
