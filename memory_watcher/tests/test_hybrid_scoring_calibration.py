import pytest
import uuid

try:
    from api.models import SearchRequest, SearchResponse
    from api.retrieval.hybrid import HybridRetrieval
except ImportError:
    from memory_watcher.api.models import SearchRequest, SearchResponse
    from memory_watcher.api.retrieval.hybrid import HybridRetrieval


class FakeEmbedder:
    async def embed(self, document):
        document.chunks[0].embedding = [0.1] * 384
        return document




class FakeReranker:
    async def score(self, pairs):
        return [0.8] * len(pairs)


class FakeVectorStore:
    def __init__(self, candidates):
        self.candidates = candidates

    async def search_v2(self, vector, **kwargs):
        return self.candidates

    async def search(self, **kwargs):
        return self.candidates



class FakeControlStore:
    def __init__(self, valid):
        self.valid = valid

    async def fts_search(self, query, **filters):
        return []

    async def valid_revision_pairs(self, memory_ids, include_historical=False):
        return self.valid

    async def expand_verified_entities(self, entity_keys, limit=20):
        return {}

    async def profile_memory_boosts(self, query, entity_keys):
        return {}


def test_search_request_default_min_score_is_zero():
    req = SearchRequest(query="test query")
    assert req.min_score == 0.0


@pytest.mark.asyncio
async def test_hybrid_search_returns_multiple_ranked_candidates():
    # 4 distinct candidate chunks with varying relevance
    candidates = []
    valid_pairs = set()
    texts = [
        "PostgreSQL setup, replication parameters, and WAL archiving rules.",
        "Qdrant vector indexes, HNSW collection parameters, and cosine similarity metric.",
        "FastAPI endpoints, lifespan event handlers, and Pydantic request validation schemas.",
        "Obsidian frontmatter conventions, YAML tags, and bidirectional wikilink graph extraction.",
    ]
    for i in range(4):
        cid = uuid.uuid4()
        mid = uuid.uuid4()
        rid = uuid.uuid4()
        valid_pairs.add((mid, rid))
        candidates.append(
            {
                "id": str(cid),
                "score": 0.85 - i * 0.05,
                "payload": {
                    "chunk_id": str(cid),
                    "memory_id": str(mid),
                    "revision_id": str(rid),
                    "memory_type": "semantic",
                    "source_file": f"Concepts/Topic_{i}.md",
                    "text": texts[i],
                },
            }
        )



    control = FakeControlStore(valid=valid_pairs)
    vector = FakeVectorStore(candidates)
    hybrid = HybridRetrieval(control, vector, FakeEmbedder(), reranker=FakeReranker())

    req = SearchRequest(query="test query", limit=4)
    response = await hybrid.search(req)

    print("RESPONSE RESULTS:", response.results)
    assert len(response.results) == 4

    # Verify score graduation is monotonic and sensible
    scores = [r.score for r in response.results]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0.3 for s in scores)
