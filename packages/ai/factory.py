from apps.api.config import settings
from packages.ai.gemini import GeminiEmbedder,GeminiLLM
from packages.ai.mock import MockEmbedder,MockLLM


def create_embedder(api_key: str | None = None):
    if settings.ai_mode == "mock":
        return MockEmbedder()
    return GeminiEmbedder(api_key)


def create_llm(api_key: str | None = None):
    if settings.ai_mode == "mock":
        return MockLLM()
    return GeminiLLM(api_key)
