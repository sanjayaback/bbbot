from apps.api.config import settings
from packages.ai.gemini import GeminiEmbedder, GeminiLLM
from packages.ai.local import EvidenceOnlyLLM, LocalEmbedder, LocalOpenAICompatibleLLM
from packages.ai.mock import MockEmbedder, MockLLM


def create_embedder(api_key: str | None = None):
    provider = settings.embedding_provider.lower()
    if provider == "local":
        return LocalEmbedder()
    if provider == "gemini":
        return GeminiEmbedder(api_key)
    if provider == "mock":
        return MockEmbedder()
    raise RuntimeError(f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}")


def create_llm(api_key: str | None = None):
    provider = settings.chat_provider.lower()
    if provider == "disabled":
        return EvidenceOnlyLLM()
    if provider == "local":
        return LocalOpenAICompatibleLLM()
    if provider == "gemini":
        return GeminiLLM(api_key)
    if provider == "mock":
        return MockLLM()
    raise RuntimeError(f"Unsupported CHAT_PROVIDER={settings.chat_provider!r}")
