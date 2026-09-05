import pytest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from graph.extractor import extract_projection, clean_wikilink, normalize_entity_key
from models.memory_record import parse_memory
from storage.qdrant_store import QdrantStore
from uams_sdk.client import UAMSClient
from api.routers.memory_edit import _safe_request_path
from fastapi import HTTPException


def make_record(body: str, title: str = "Test Note", rel_path: str = "Concepts/Test Note.md"):
    markdown = f"""---
type: semantic
status: active
aliases: []
tags: ["#test"]
entities: []
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
---
# {title}

{body}
"""
    return parse_memory(Path(rel_path), markdown)


def test_dataview_inline_relations_extracted():
    body = """
    Our system has [[uses::Qdrant]] for vector storage.
    It also [depends_on:: [[PostgreSQL]]] for the control plane.
    """
    record = make_record(body, title="Architecture Spec")
    projection = extract_projection(record)

    claims = {(c.predicate, c.object) for c in projection.claims}
    assert ("uses", "Qdrant") in claims
    assert ("depends_on", "PostgreSQL") in claims


def test_memory_edit_safe_request_path_security():
    # 1. Non-markdown file must be rejected
    with pytest.raises(HTTPException) as exc1:
        _safe_request_path(".env")
    assert exc1.value.status_code == 400

    # 2. Critical config file must be rejected
    with pytest.raises(HTTPException) as exc2:
        _safe_request_path("docker-compose.yml")
    assert exc2.value.status_code == 400

    # 3. Root non-daily note must be rejected
    with pytest.raises(HTTPException) as exc3:
        _safe_request_path("random_root_note.md")
    assert exc3.value.status_code == 403

    # 4. Valid daily note in root must be allowed
    path = _safe_request_path("2026-09-05.md")
    assert path.name == "2026-09-05.md"

    # 5. Valid approved folder note must be allowed
    path = _safe_request_path("Concepts/Unified Memory.md")
    assert path.name == "Unified Memory.md"


@pytest.mark.asyncio
async def test_uams_client_headers_and_persistent_session():
    client = UAMSClient(
        base_url="http://localhost:8000",
        source_agent="antigravity-test",
        api_key="secret-token-123",
    )
    headers = client._headers()
    assert headers["X-Agent-Name"] == "antigravity-test"
    assert headers["X-API-Key"] == "secret-token-123"
    assert headers["Authorization"] == "Bearer secret-token-123"

    # Persistent session
    session1 = await client._get_client()
    session2 = await client._get_client()
    assert session1 is session2

    await client.close()
    assert client._client is None


@pytest.mark.asyncio
async def test_qdrant_store_batch_upsert_and_close():
    store = QdrantStore(vector_size=1024)
    store.client = AsyncMock()
    store.client.upsert = AsyncMock()
    store.client.close = AsyncMock()

    # Test close
    await store.close()
    store.client.close.assert_called_once()

    # Test batched upsert_revision
    fake_points = [
        {"chunk_id": uuid.uuid4(), "vector": [0.0] * 1024, "payload": {"idx": i}}
        for i in range(150)
    ]
    await store.upsert_revision(fake_points, batch_size=64)
    # 150 points with batch_size 64 => ceil(150/64) = 3 batches
    assert store.client.upsert.call_count == 3
