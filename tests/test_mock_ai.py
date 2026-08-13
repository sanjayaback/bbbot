import asyncio
from packages.ai.mock import MockEmbedder, MockLLM


def test_mock_embedding_dimension_and_norm():
    vec=asyncio.run(MockEmbedder().embed("Nepal banking collateral policy"))
    assert len(vec)==768
    norm=sum(x*x for x in vec)
    assert 0.99 <= norm <= 1.01


def test_mock_llm_is_grounded_to_evidence():
    async def run():
        chunks=[]
        async for token in MockLLM().stream_answer("What?","--- SOURCE 1: x | Page 1 ---\nEvidence text"):
            chunks.append(token)
        return ''.join(chunks)
    answer=asyncio.run(run())
    assert "Evidence text" in answer
