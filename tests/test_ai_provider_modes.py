import pytest

from apps.api.config import settings
from packages.ai.factory import create_embedder, create_llm
from packages.ai.local import EvidenceOnlyLLM


def test_search_only_llm_never_needs_cloud_key(monkeypatch):
    monkeypatch.setattr(settings, "chat_provider", "disabled")
    llm = create_llm(None)
    assert isinstance(llm, EvidenceOnlyLLM)
    assert llm.provider == "disabled"
    assert llm.model == "evidence-only"


@pytest.mark.asyncio
async def test_search_only_returns_grounded_evidence(monkeypatch):
    monkeypatch.setattr(settings, "chat_provider", "disabled")
    llm = create_llm(None)
    context = "--- SOURCE 1 ---\nDoc: policy.txt\n---\nThe verification code is DQ-12345."
    parts = [part async for part in llm.stream_answer("What is the code?", context)]
    answer = "".join(parts)
    assert "DQ-12345" in answer


def test_mock_provider_is_still_available(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "mock")
    monkeypatch.setattr(settings, "chat_provider", "mock")
    assert create_embedder(None).model == "mock-embedding-v1"
    assert create_llm(None).model == "mock-grounded-v1"


def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "not-a-provider")
    with pytest.raises(RuntimeError):
        create_embedder(None)
