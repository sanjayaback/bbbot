from fastapi import APIRouter
from apps.api.config import settings

router = APIRouter(tags=["configuration"])


@router.get("/api/public-config")
async def public_config():
    return {
        "auth_mode": settings.auth_mode,
        "supabase_url": settings.supabase_url if settings.auth_mode == "supabase" else "",
        "supabase_publishable_key": settings.supabase_publishable_key if settings.auth_mode == "supabase" else "",
        "max_upload_mb": settings.max_upload_mb,
        "app_env": settings.app_env,
        "app_mode": settings.app_mode,
        "embedding_provider": settings.embedding_provider,
        "chat_provider": settings.chat_provider,
    }
