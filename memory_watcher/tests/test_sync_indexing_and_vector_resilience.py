import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.models import RememberRequest, SearchRequest
from chunkers.semantic import SemanticChunker
from models.document import Chunk, ChunkMetadata, Document
from models.memory_record import parse_memory
from storage.qdrant_store import QdrantStore


def test_parse_memory_without_text_reads_from_disk(tmp_path):
    note = tmp_path / "Concepts" / "Resilience.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        '---\ntype: concept\ntags:\n  - "#reliability"\n---\n# Resilience Patterns\nContent about recovery.',
        encoding="utf-8",
    )

    # Calling with only path (no text argument)
    record = parse_memory(note, vault_root=tmp_path)
    assert record.title == "Resilience Patterns"
    assert record.type == "semantic"
    assert record.tags == ["#reliability"]
    assert "Content about recovery." in record.body


def test_semantic_chunker_chunk_document(tmp_path):
    chunker = SemanticChunker()
    note = tmp_path / "Concepts" / "Chunking.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    content = "---\ntype: semantic\n---\n# Chunking\n\nParagraph one.\n\nParagraph two."
    note.write_text(content, encoding="utf-8")

    record = parse_memory(note, vault_root=tmp_path)
    chunks = chunker.chunk_document(record)
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)
    assert any("Paragraph one" in c.content for c in chunks)

    # Also supports Document directly
    doc = Document(path="test.md", raw_content=content)
    chunks_from_doc = chunker.chunk_document(doc)
    assert len(chunks_from_doc) >= 1


@pytest.mark.asyncio
async def test_qdrant_store_upsert_v2():
    client = AsyncMock()
    store = QdrantStore(client=client)

    chunks = [
        Chunk(
            content="# Title\n\nBody content",
            metadata=ChunkMetadata(
                chunk_id=str(uuid.uuid4()),
                source_file="Concepts/Title.md",
                heading_hierarchy=["Title"],
                tags=["test"],
                entities=["EntityA"],
                timestamps={"created": "2026-09-05"},
                semantic_category="semantic",
            ),
            embedding=[0.1] * 1024,
        )
    ]

    await store.upsert_v2(chunks)
    assert client.upsert.called
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "memory_chunks_v2"
    points = call_kwargs["points"]
    assert len(points) == 1
    assert points[0].vector == [0.1] * 1024
    assert points[0].payload["memory_type"] == "semantic"
    assert points[0].payload["text"] == "# Title\n\nBody content"


@pytest.mark.asyncio
async def test_qdrant_store_search_v2_retries_transient_connection_error():
    client = AsyncMock()
    store = QdrantStore(client=client)

    # First call raises ConnectionError, second succeeds
    client.search.side_effect = [
        ConnectionError("Connection dropped before pool warmed up"),
        [MagicMock(id="chunk-1", payload={"memory_id": "mem-1", "revision_id": "rev-1"}, score=0.9)],
    ]

    results = await store.search_v2([0.1] * 1024, limit=5)
    assert len(results) == 1
    assert client.search.call_count == 2


@pytest.mark.asyncio
async def test_hybrid_retrieval_retries_transient_connection_error():
    from api.retrieval.hybrid import HybridRetrieval

    control_store = AsyncMock()
    control_store.fts_search.return_value = []
    control_store.expand_verified_entities.return_value = {}
    control_store.profile_memory_boosts.return_value = {}
    control_store.filter_active_candidates.side_effect = lambda c: c
    control_store.filter_historical_candidates.side_effect = lambda c: c

    mem_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    control_store.valid_revision_pairs = AsyncMock(return_value={(mem_id, rev_id)})

    vector_store = AsyncMock()
    # First search raises ConnectionError, second succeeds
    vector_store.search_v2.side_effect = [
        ConnectionError("Qdrant connection reset by peer"),
        [
            {
                "id": "chunk-1",
                "score": 0.85,
                "payload": {"memory_id": str(mem_id), "revision_id": str(rev_id)},
            }
        ],
    ]

    embedder = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.chunks = [MagicMock(embedding=[0.1] * 1024)]
    embedder.embed.return_value = mock_doc

    reranker = AsyncMock()
    reranker.score.return_value = [0.9]

    compressor = MagicMock()
    compressor.compress.side_effect = lambda c, **kwargs: c

    hybrid = HybridRetrieval(
        control_store=control_store,
        vector_store=vector_store,
        embedder=embedder,
        reranker=reranker,
        compressor=compressor,
    )

    req = SearchRequest(query="test query")
    results = await hybrid.search(req)
    assert len(results.results) == 1
    assert vector_store.search_v2.call_count == 2



@pytest.mark.asyncio
async def test_postgres_store_activate_revision():
    from storage.postgres_store import PostgresStore

    store = PostgresStore()
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = {"current_revision_id": uuid.uuid4()}
    mock_conn.execute.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_conn_ctx = AsyncMock()
    mock_conn_ctx.__aenter__.return_value = mock_conn
    mock_conn_ctx.__aexit__.return_value = False
    mock_pool.connection.return_value = mock_conn_ctx

    mock_tx_ctx = AsyncMock()
    mock_tx_ctx.__aenter__.return_value = None
    mock_tx_ctx.__aexit__.return_value = False
    mock_conn.transaction = MagicMock(return_value=mock_tx_ctx)

    store.pool = mock_pool

    mem_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    await store.activate_revision(mem_id, rev_id)

    executed_queries = [call[0][0] for call in mock_conn.execute.call_args_list]
    assert any("UPDATE document_revisions" in q for q in executed_queries)
    assert any("UPDATE documents" in q for q in executed_queries)
    assert any("UPDATE vector_outbox" in q for q in executed_queries)
    assert any("UPDATE ingestion_jobs" in q for q in executed_queries)


@pytest.mark.asyncio
async def test_remember_sync_indexing_success(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    from api.main import remember, pipeline
    from pipelines.reconciliation import ReconcileResult

    mem_id = uuid.uuid4()
    rev_id = uuid.uuid4()

    mock_reconciler = AsyncMock()
    mock_reconciler.chunker = SemanticChunker()
    mock_reconciler.reconcile_path.return_value = ReconcileResult(
        status="staged",
        path="Concepts/SyncTest.md",
        memory_id=mem_id,
        revision_id=rev_id,
    )

    mock_embedder = AsyncMock()
    mock_embedder.embed.side_effect = lambda d: d

    mock_vector_store = AsyncMock()
    mock_control_store = AsyncMock()

    monkeypatch.setattr(pipeline, "reconciler", mock_reconciler)
    monkeypatch.setattr(pipeline, "embedder", mock_embedder)
    monkeypatch.setattr(pipeline, "vector_store", mock_vector_store)
    monkeypatch.setattr(pipeline, "control_store", mock_control_store)

    req = RememberRequest(
        text="# Sync Test\nImmediate vector indexing test content.",
        category="semantic",
        sync=True,
    )

    res = await remember(req)
    assert res["status"] == "success"
    assert res["index_status"] == "active"
    assert res["indexed"] is True
    assert res["warning"] is None
    assert mock_vector_store.upsert_v2.called
    assert mock_control_store.activate_revision.called
