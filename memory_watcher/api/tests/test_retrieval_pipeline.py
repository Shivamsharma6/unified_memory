import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.models import SearchRequest
from api.retrieval.pipeline import RetrievalPipeline


class FakeEmbedder:
    async def embed(self, doc):
        for chunk in doc.chunks:
            chunk.embedding = [0.1] * 384
        return doc


class RecordingVectorStore:
    def __init__(self):
        self.calls = []

    async def hybrid_search(self, query_vector, collection, limit=5, entity_filter=None):
        self.calls.append(
            {
                "collection": collection,
                "limit": limit,
                "entity_filter": entity_filter,
            }
        )
        suffix = entity_filter or "base"
        return [
            {
                "id": f"id-{suffix}",
                "score": 0.91,
                "payload": {
                    "text": f"Memory for {suffix}",
                    "source_file": f"{suffix}.md",
                    "entities": [suffix] if entity_filter else [],
                },
            }
        ]


@pytest.mark.asyncio
async def test_graph_expansion_influences_vector_retrieval():
    pipeline = RetrievalPipeline()
    pipeline.embedder = FakeEmbedder()
    pipeline.vector_store = RecordingVectorStore()
    pipeline.kg_store.G = nx.DiGraph()
    pipeline.kg_store.G.add_edge("Login Timeout", "Session Refresh", relation="caused_by")

    response = await pipeline.search(
        SearchRequest(query="Fix [[Login Timeout]]", limit=3, compress=False)
    )

    filters = {call["entity_filter"] for call in pipeline.vector_store.calls}
    assert "Login Timeout" in filters
    assert "Session Refresh" in filters
    assert response.expanded_entities


@pytest.mark.asyncio
async def test_graph_expanded_hits_can_survive_small_limits():
    pipeline = RetrievalPipeline()
    pipeline.embedder = FakeEmbedder()
    pipeline.vector_store = RecordingVectorStore()
    pipeline.kg_store.G = nx.DiGraph()
    pipeline.kg_store.G.add_edge("Login Timeout", "Session Refresh", relation="caused_by")

    response = await pipeline.search(
        SearchRequest(query="Fix [[Login Timeout]]", limit=1, compress=False)
    )

    assert any("Session Refresh" in result.text for result in response.results)


@pytest.mark.asyncio
async def test_context_request_max_tokens_reaches_compressor(monkeypatch):
    pipeline = RetrievalPipeline()

    seen = {}

    async def fake_vector_retrieval(query, expanded_entities, intent, limit):
        return [
            {
                "id": "context-id",
                "score": 0.9,
                "payload": {
                    "text": "one two three four five six seven eight nine ten",
                    "source_file": "memory.md",
                    "entities": [],
                },
            }
        ]

    def fake_compress(ranked, max_tokens, profile):
        seen["max_tokens"] = max_tokens
        return ranked

    monkeypatch.setattr(pipeline, "_step5_vector_retrieval", fake_vector_retrieval)
    monkeypatch.setattr(pipeline.compressor, "compress", fake_compress)

    await pipeline.search(
        SearchRequest(query="Recall project context", limit=1, compress=True, max_tokens=321)
    )

    assert seen["max_tokens"] == 321


@pytest.mark.asyncio
async def test_initialized_control_plane_never_falls_back_to_unvalidated_legacy_results(
    monkeypatch,
):
    pipeline = RetrievalPipeline()

    class BrokenHybrid:
        async def search(self, request):
            raise RuntimeError("postgres control plane unavailable")

    pipeline.hybrid = BrokenHybrid()

    async def unsafe_legacy(request):
        raise AssertionError("legacy retrieval must not run after control-plane activation")

    monkeypatch.setattr(pipeline, "_step8_assemble", unsafe_legacy)

    with pytest.raises(RuntimeError, match="postgres control plane unavailable"):
        await pipeline.search(SearchRequest(query="current revision only"))
