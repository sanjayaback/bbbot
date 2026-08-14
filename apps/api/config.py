from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "change-me"
    app_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8000,http://localhost:8080,http://localhost:3000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docuquery"
    redis_url: str = "redis://localhost:6379/0"

    auth_mode: str = "dev"  # dev | supabase
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    dev_user_email: str = "dev@docuquery.local"

    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwks_url: str = ""

    storage_backend: str = "local"  # local | supabase
    storage_bucket: str = "documents"
    local_storage_root: str = "uploads"

    ai_mode: str = "gemini"  # gemini | mock (mock is development/test only)
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.6-flash"
    gemini_embed_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768
    retrieval_min_score: float = 0.35
    credential_encryption_key: str = ""

    max_upload_mb: int = 20
    rate_limit_ask: str = "20/minute"
    monthly_question_limit_default: int = 1000
    storage_limit_bytes_default: int = 2 * 1024 * 1024 * 1024

    ocr_enabled: bool = False
    tesseract_cmd: str = ""
    malware_scan_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def effective_jwks_url(self) -> str:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
