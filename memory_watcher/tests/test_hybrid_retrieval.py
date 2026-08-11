import sys
import uuid
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.models import SearchRequest
from api.retrieval.hybrid import HybridRetrieval


class FakeEmbedder:
    async def embed(self, document):
        document.chunks[0].embedding = [0.1, 0.2, 0.3]
        return document


class BrokenEmbedder:
    async def embed(self, document):
        raise RuntimeError("embedding offline")


class FakeReranker:
    def __init__(self, score=1.0):
        self.value = score

    async def score(self, pairs):
        return [self.value for _ in pairs]


class FakeVectorStore:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    async def search_v2(self, query_vector, **filters):
        self.calls.append(filters)
        return self.candidates


class FakeControlStore:
    def __init__(
        self,
        *,
        fts=None,
        valid=None,
        historical=None,
        expansion=None,
        profile_boosts=None,
    ):
        self.fts = fts or []
        self.valid = set(valid or [])
        self.historical = set(historical or self.valid)
        self.expansion = expansion or {}
        self.profile_boosts = profile_boosts or {}
        self.fts_calls = []

    async def fts_search(self, query, **filters):
        self.fts_calls.append(filters)
        return self.fts

    async def valid_revision_pairs(self, memory_ids, include_historical=False):
        return self.historical if include_historical else self.valid

    async def expand_verified_entities(self, entity_keys, limit=20):
        return self.expansion

    async def profile_memory_boosts(self, query, entity_keys):
        return self.profile_boosts


def candidate(
    *,
    chunk_id=None,
    memory_id=None,
    revision_id=None,
    score=0.9,
    memory_type="semantic",
    entities=None,
    source="Concepts/Test.md",
    timestamps=None,
):
    chunk_id = chunk_id or uuid.uuid4()
    memory_id = memory_id or uuid.uuid4()
    revision_id = revision_id or uuid.uuid4()
    return {
        "id": str(chunk_id),
        "score": score,
        "payload": {
            "chunk_id": str(chunk_id),
            "memory_id": str(memory_id),
            "revision_id": str(revision_id),
            "memory_type": memory_type,
            "source_file": source,
            "entity_keys": entities or [],
            "timestamps": timestamps or {},
            "text": f"Evidence from {source}",
        },
    }


def pair(item):
    payload = item["payload"]
    return (uuid.UUID(payload["memory_id"]), uuid.UUID(payload["revision_id"]))


def pipeline(control, vector, reranker=None):
    return HybridRetrieval(
        control,
        vector,
        FakeEmbedder(),
        reranker=reranker or FakeReranker(),
    )


@pytest.mark.asyncio
async def test_default_search_rejects_stale_qdrant_candidate():
    current = candidate(source="Concepts/Current.md")
    stale = candidate(source="Concepts/Stale.md")
    control = FakeControlStore(valid={pair(current)})

    response = await pipeline(control, FakeVectorStore([stale, current])).search(
        SearchRequest(query="reconnect bug", limit=5, min_score=0.0, compress=False)
    )

    assert [item.source_file for item in response.results] == ["Concepts/Current.md"]
    assert all(item.revision_id == str(pair(current)[1]) for item in response.results)


@pytest.mark.asyncio
async def test_vector_search_crosses_memory_types_and_passes_filters():
    semantic = candidate(memory_type="semantic")
    episodic = candidate(memory_type="episodic")
    vector = FakeVectorStore([semantic, episodic])
    control = FakeControlStore(valid={pair(semantic), pair(episodic)})

    response = await pipeline(control, vector).search(
        SearchRequest(
            query="Qdrant cleanup",
            limit=5,
            min_score=0.0,
            compress=False,
            memory_types=["semantic", "episodic"],
            projects=["Unified Memory"],
            source_agents=["codex"],
        )
    )

    assert {result.memory_type for result in response.results} == {"semantic", "episodic"}
    assert vector.calls[0]["memory_types"] == ["semantic", "episodic"]
    assert vector.calls[0]["projects"] == ["Unified Memory"]
    assert control.fts_calls[0]["source_agents"] == ["codex"]


@pytest.mark.asyncio
async def test_fts_and_vector_results_are_rrf_fused_and_deduplicated():
    shared = candidate(source="Concepts/Shared.md")
    exact = candidate(source="Profiles/User.md", score=0.4)
    exact["rank"] = 0.8
    control = FakeControlStore(
        fts=[shared, exact],
        valid={pair(shared), pair(exact)},
    )

    response = await pipeline(control, FakeVectorStore([shared])).search(
        SearchRequest(query="exact preference", limit=5, min_score=0.0, compress=False)
    )

    assert [result.chunk_id for result in response.results].count(shared["payload"]["chunk_id"]) == 1
    assert response.results[0].source_file == "Concepts/Shared.md"
    assert set(response.results[0].rank_sources) == {"semantic", "lexical"}


@pytest.mark.asyncio
async def test_archived_and_historical_revisions_require_explicit_opt_in():
    archived = candidate(source="Archive/Old.md")
    control = FakeControlStore(valid=set(), historical={pair(archived)})
    hybrid = pipeline(control, FakeVectorStore([archived]))

    current = await hybrid.search(
        SearchRequest(query="old decision", min_score=0.0, compress=False)
    )
    historical = await hybrid.search(
        SearchRequest(
            query="old decision",
            min_score=0.0,
            compress=False,
            include_historical=True,
        )
    )

    assert current.results == []
    assert [result.source_file for result in historical.results] == ["Archive/Old.md"]


@pytest.mark.asyncio
async def test_min_score_is_enforced_after_reranking():
    weak = candidate(score=0.05)
    control = FakeControlStore(valid={pair(weak)})

    response = await pipeline(
        control,
        FakeVectorStore([weak]),
        reranker=FakeReranker(score=0.0),
    ).search(SearchRequest(query="unrelated", min_score=0.95, compress=False))

    assert response.results == []


@pytest.mark.asyncio
async def test_embedding_outage_degrades_to_postgres_fts():
    exact = candidate(source="Profiles/User.md")
    control = FakeControlStore(fts=[exact], valid={pair(exact)})
    hybrid = HybridRetrieval(
        control,
        FakeVectorStore([]),
        BrokenEmbedder(),
        reranker=FakeReranker(),
    )

    response = await hybrid.search(
        SearchRequest(query="exact preference", min_score=0.0, compress=False)
    )

    assert [result.source_file for result in response.results] == ["Profiles/User.md"]
    assert response.results[0].rank_sources == ["lexical"]


@pytest.mark.asyncio
async def test_graph_profile_and_temporal_boosts_are_bounded_and_evidenced():
    memory_id = uuid.uuid4()
    item = candidate(
        memory_id=memory_id,
        entities=["session refresh"],
        timestamps={"updated": "2999-01-01T00:00:00Z"},
    )
    control = FakeControlStore(
        valid={pair(item)},
        expansion={"session refresh": 0.9},
        profile_boosts={memory_id: 0.9},
    )

    response = await pipeline(control, FakeVectorStore([item])).search(
        SearchRequest(
            query="Fix [[Login Timeout]]",
            min_score=0.0,
            compress=False,
        )
    )

    result = response.results[0]
    assert result.importance <= 1.25
    assert result.score <= 1.0
    assert result.evidence_ids == [
        f"{result.memory_id}:{result.revision_id}:{result.chunk_id}"
    ]
    assert "session refresh" in response.expanded_entities
