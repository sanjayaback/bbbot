from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from apps.api.config import settings
from apps.api.db import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "docuquery-api", "version": "1.0.0"}


@router.get("/ready")
async def ready():
    checks = {"database": "unknown", "redis": "unknown"}
    failed = False

    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error:{type(exc).__name__}"
        failed = True

    redis = Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
    try:
        if await redis.ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error:ping_failed"
            failed = True
    except Exception as exc:
        checks["redis"] = f"error:{type(exc).__name__}"
        failed = True
    finally:
        await redis.aclose()

    return {
        "status": "degraded" if failed else "ok",
        "service": "docuquery-api",
        "version": "1.0.0",
        **checks,
    }
