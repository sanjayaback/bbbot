from apps.api.config import settings
from packages.storage.local import LocalStorage
from packages.storage.supabase import SupabaseStorage


def storage_backend():
    if settings.storage_backend == "supabase":
        return SupabaseStorage(settings.supabase_url, settings.supabase_secret_key, settings.storage_bucket)
    return LocalStorage(settings.local_storage_root)
