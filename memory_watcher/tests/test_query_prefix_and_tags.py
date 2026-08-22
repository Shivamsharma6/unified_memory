import pytest
import uuid

try:
    from api.models import SearchRequest
    from api.retrieval.hybrid import HybridRetrieval
    from models.document import Document
except ImportError:
    from memory_watcher.api.models import SearchRequest
    from memory_watcher.api.retrieval.hybrid import HybridRetrieval
    from memory_watcher.models.document import Document


class RecordingEmbedder:
    def __init__(self):
        self.embedded_texts = []

    async def embed(self, document: Document):
        for chunk in document.chunks:
            self.embedded_texts.append(chunk.content)
            chunk.embedding = [0.05] * 384
        return document


class RecordingVectorStore:
    def __init__(self):
        self.search_calls = []

    async def search_v2(self, vector, **kwargs):
        self.search_calls.append(kwargs)
        return []


class RecordingControlStore:
    def __init__(self):
        self.fts_calls = []

    async def fts_search(self, query, **filters):
        self.fts_calls.append(filters)
        return []

    async def valid_revision_pairs(self, memory_ids, include_historical=False):
        return set()

    async def expand_verified_entities(self, entity_keys, limit=20):
        return {}

    async def profile_memory_boosts(self, query, entity_keys):
        return {}


@pytest.mark.asyncio
async def test_asymmetric_query_prefix_and_tags_forwarding():
    embedder = RecordingEmbedder()
    vector_store = RecordingVectorStore()
    control_store = RecordingControlStore()

    hybrid = HybridRetrieval(control_store, vector_store, embedder)

    req = SearchRequest(
        query="scaling vector search",
        tags=["architecture", "qdrant"],
        memory_types=["semantic"],
    )

    await hybrid.search(req)

    # 1. Verify asymmetric prefix was prepended to query embedding
    assert len(embedder.embedded_texts) == 1
    assert "Represent this sentence for searching relevant passages: scaling vector search" in embedder.embedded_texts[0]

    # 2. Verify tags were passed in filter values to vector store & FTS
    assert vector_store.search_calls[0]["tags"] == ["architecture", "qdrant"]
    assert control_store.fts_calls[0]["tags"] == ["architecture", "qdrant"]
