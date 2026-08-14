from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "change-me"
    app_base_url: str = "http://localhost:8000"
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

    # Application AI modes. search_only is the safest/default non-generative path.
    app_mode: str = "search_only"  # search_only | local_llm | cloud_llm
    ai_mode: str = "gemini"  # backwards compatibility: gemini | mock
    embedding_provider: str = "local"  # local | gemini | mock
    chat_provider: str = "disabled"  # disabled | local | gemini | mock

    # Local multilingual embeddings. multilingual-e5-base outputs 768 dimensions,
    # matching the existing pgvector schema without a destructive migration.
    local_embed_model: str = "intfloat/multilingual-e5-base"
    local_embed_device: str = "cpu"
    local_embed_query_prefix: str = "query: "
    local_embed_passage_prefix: str = "passage: "

    # Optional local/OpenAI-compatible LLM endpoint (Ollama, llama.cpp, vLLM, etc.).
    local_llm_base_url: str = "http://host.docker.internal:11434/v1"
    local_llm_api_key: str = "ollama"
    local_llm_model: str = "qwen2.5:7b"
    local_llm_timeout_seconds: float = 120.0

    # Optional Gemini cloud providers.
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embedding_dimension: int = 768
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


settings = Settings()
