import pytest
import math
from unittest.mock import MagicMock

try:
    from api.retrieval.reranker import CrossEncoderReranker
    from api.models import SearchResult
except ImportError:
    from memory_watcher.api.retrieval.reranker import CrossEncoderReranker
    from memory_watcher.api.models import SearchResult


@pytest.mark.asyncio
async def test_cross_encoder_calibrates_logits_with_sigmoid():
    reranker = CrossEncoderReranker()
    reranker._initialized = True
    reranker._available = True

    # Mock sentence_transformers predict returning typical ms-marco logits: +8.5, -4.2, 0.0
    mock_model = MagicMock()
    mock_model.predict.return_value = [8.5, -4.2, 0.0]
    reranker._model = mock_model

    pairs = [
        ("auth token", "We use JWT for authentication"),
        ("auth token", "Unrelated cooking recipe"),
        ("auth token", "Token mention in database log"),
    ]
    scores = await reranker.score(pairs)

    assert len(scores) == 3
    # Sigmoid of 8.5 is ~0.9998
    assert 0.99 <= scores[0] <= 1.0
    # Sigmoid of -4.2 is ~0.0147 (not collapsed to 0.0)
    assert 0.01 <= scores[1] <= 0.03
    # Sigmoid of 0.0 is exactly 0.5
    assert math.isclose(scores[2], 0.5, abs_tol=1e-3)


@pytest.mark.asyncio
async def test_cross_encoder_rerank_preserves_score_monotonicity():
    reranker = CrossEncoderReranker()
    reranker._initialized = True
    reranker._available = True
    mock_model = MagicMock()
    mock_model.predict.return_value = [6.0, 1.0, -5.0]
    reranker._model = mock_model

    results = [
        SearchResult(chunk_id="1", text="Highly relevant", score=0.7, importance=1.0, source_file="A.md", entities=[]),
        SearchResult(chunk_id="2", text="Moderately relevant", score=0.6, importance=1.0, source_file="B.md", entities=[]),
        SearchResult(chunk_id="3", text="Irrelevant", score=0.5, importance=1.0, source_file="C.md", entities=[]),
    ]

    reranked = await reranker.rerank("test query", results)
    assert [r.chunk_id for r in reranked] == ["1", "2", "3"]
    assert reranked[0].score > reranked[1].score > reranked[2].score
    assert all(0.0 <= r.score <= 1.0 for r in reranked)
