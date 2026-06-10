import pytest
from api.retrieval.reranker import CrossEncoderReranker


@pytest.mark.asyncio
async def test_reranker_initializes():
    reranker = CrossEncoderReranker()
    assert reranker is not None


@pytest.mark.asyncio
async def test_reranker_scores_pairs():
    reranker = CrossEncoderReranker()
    pairs = [
        ("How to deploy with Docker", "Use docker compose up to start services"),
        ("How to deploy with Docker", "The weather is sunny today"),
    ]
    scores = await reranker.score(pairs)
    assert len(scores) == 2
    assert scores[0] > scores[1]


@pytest.mark.asyncio
async def test_reranker_reranks_results():
    reranker = CrossEncoderReranker()

    class MockResult:
        def __init__(self, text, score, source_file):
            self.text = text
            self.score = score
            self.source_file = source_file
            self.chunk_id = "mock"
            self.importance = 1.0
            self.entities = []

    results = [
        MockResult("The weather is nice today", 0.9, "weather.md"),
        MockResult("Docker compose starts the Qdrant container", 0.7, "docker.md"),
    ]
    query = "How do I start Qdrant?"
    reranked = await reranker.rerank(query, results)
    assert len(reranked) == 2
    assert reranked[0].source_file == "docker.md"
