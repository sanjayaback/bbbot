from sqlalchemy import text
from apps.api.config import settings
from packages.security.crypto import CredentialCipher


async def resolve_gemini_key(db, workspace_id: str) -> str:
    row=(await db.execute(text("SELECT encrypted_secret FROM api_credentials WHERE workspace_id=:w AND provider='gemini' ORDER BY created_at DESC LIMIT 1"),{"w":workspace_id})).mappings().first()
    if row:
        if not settings.credential_encryption_key:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is required to decrypt workspace credentials")
        return CredentialCipher(settings.credential_encryption_key).decrypt(row['encrypted_secret'])
    if settings.gemini_api_key:
        return settings.gemini_api_key
    raise RuntimeError("No Gemini API key configured for this workspace")
