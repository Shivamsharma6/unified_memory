import pytest

try:
    from api.retrieval.compressor import ContextCompressor
    from api.models import SearchResult
except ImportError:
    from memory_watcher.api.retrieval.compressor import ContextCompressor
    from memory_watcher.api.models import SearchResult


def test_compressor_preserves_reranker_rank_order():
    compressor = ContextCompressor()
    results = [
        SearchResult(chunk_id="c1", text="Topic 1 text about architecture", score=0.95, importance=1.0, source_file="A.md", entities=[]),
        SearchResult(chunk_id="c2", text="Topic 2 text about database indexes", score=0.85, importance=1.0, source_file="B.md", entities=[]),
        SearchResult(chunk_id="c3", text="Topic 3 text about API routes", score=0.75, importance=1.0, source_file="C.md", entities=[]),
    ]

    compressed = compressor.compress(results, max_tokens=1000, profile="coding")
    assert [r.chunk_id for r in compressed] == ["c1", "c2", "c3"]


def test_compressor_merges_evidence_ids_on_deduplication():
    compressor = ContextCompressor(sim_threshold=0.8)
    results = [
        SearchResult(
            chunk_id="c1",
            text="Exact same paragraph describing the vector storage policy.",
            score=0.90,
            importance=1.0,
            source_file="A.md",
            entities=["Vector"],
            evidence_ids=["ev1"],
        ),
        SearchResult(
            chunk_id="c2",
            text="Exact same paragraph describing the vector storage policy.",
            score=0.88,
            importance=1.0,
            source_file="B.md",
            entities=["Storage"],
            evidence_ids=["ev2"],
        ),
    ]

    compressed = compressor.compress(results, max_tokens=1000)
    assert len(compressed) == 1
    assert "ev1" in compressed[0].evidence_ids
    assert "ev2" in compressed[0].evidence_ids
    assert "Vector" in compressed[0].entities
    assert "Storage" in compressed[0].entities


def test_compressor_greedy_knapsack_packs_subsequent_chunks():
    compressor = ContextCompressor()
    # c1 is 20 tokens, c2 is 500 tokens (oversized for 100 max_tokens), c3 is 15 tokens
    c1 = SearchResult(chunk_id="c1", text="Short intro content", score=0.9, importance=1.0, source_file="A.md", entities=[])
    c2 = SearchResult(chunk_id="c2", text="Long " * 300, score=0.8, importance=1.0, source_file="B.md", entities=[])
    c3 = SearchResult(chunk_id="c3", text="Small final content", score=0.7, importance=1.0, source_file="C.md", entities=[])

    compressed = compressor.compress([c1, c2, c3], max_tokens=60)
    # c1 fits, c2 doesn't fit, but c3 fits!
    assert "c1" in [r.chunk_id for r in compressed]
    assert "c3" in [r.chunk_id for r in compressed]
