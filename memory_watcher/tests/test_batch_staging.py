import pytest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


try:
    from storage.postgres_store import PostgresStore
    from models.document import Chunk, ChunkMetadata
    from graph.extractor import ProjectedEntity, ProjectedMention, ProjectedClaim, MemoryProjection
    from models.memory_record import MemoryRecord, MemoryTimestamps
except ImportError:
    from memory_watcher.storage.postgres_store import PostgresStore
    from memory_watcher.models.document import Chunk, ChunkMetadata
    from memory_watcher.graph.extractor import ProjectedEntity, ProjectedMention, ProjectedClaim, MemoryProjection
    from memory_watcher.models.memory_record import MemoryRecord, MemoryTimestamps




@pytest.mark.asyncio
async def test_batch_staging_chunks_and_mentions_executemany():
    store = PostgresStore()
    mock_cursor = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_cursor), __aexit__=AsyncMock()))
    mock_conn.transaction = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    mock_conn.execute = AsyncMock()

    # Configure fetchone responses
    mock_conn.execute.side_effect = [
        None,  # advisory lock
        AsyncMock(fetchone=AsyncMock(return_value=None)),  # current_result
        None,  # insert documents
        None,  # update ingestion_jobs
        AsyncMock(fetchone=AsyncMock(return_value=None)),  # existing_result
        None,  # insert document_revisions
        AsyncMock(fetchone=AsyncMock(return_value={"entity_id": uuid.uuid4()})),  # entity insert
        None,  # ingestion_jobs insert
        None,  # vector_outbox insert
        None,  # memory_audit_events insert
    ]

    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))
    store.pool = mock_pool

    mem_id = uuid.uuid4()
    record = MemoryRecord(
        memory_id=mem_id,
        vault_path="Concepts/Batch.md",
        title="Batch Note",
        memory_type="semantic",
        source_agent="Hermes",
        project="UnifiedMemory",
        timestamps=MemoryTimestamps(),
        frontmatter={"type": "semantic"},
        body="Content",
        path=Path("Concepts/Batch.md"),
    )


    chunks = [
        Chunk(content=f"Chunk {i} content text", metadata=ChunkMetadata(chunk_id=f"c-{i}", source_file="Concepts/Batch.md"))
        for i in range(5)
    ]

    projection = MemoryProjection(
        memory_id=mem_id,
        entities=[ProjectedEntity(canonical_name="Batch Note", normalized_key="batch_note", entity_type="concept")],
        mentions=[ProjectedMention(entity_name="Batch Note", normalized_key="batch_note", surface_text="Batch Note", context="context snippet")],
        claims=[],
    )


    res = await store.stage_revision(
        record=record,
        raw_markdown="---\ntype: semantic\n---\n# Batch Note\nContent",
        content_hash="hash123",
        chunks=chunks,
        projection=projection,
        document_status="active",
        event_type="create",
    )

    assert res.created is True
    # Verify cursor.executemany was called for chunks and mentions
    assert mock_cursor.executemany.call_count >= 1
