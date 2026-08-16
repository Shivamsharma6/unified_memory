"""Property and invariant unit tests for UAMS hardening and architectural safety."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

WATCHER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WATCHER_ROOT))

from api.readiness import assess_deep_projection_drift, assess_lightweight_readiness
from api.routers.validation import validate_note_content
from models.memory_record import (
    MEMORY_ID_NAMESPACE,
    deterministic_memory_id,
    parse_memory,
    split_frontmatter,
)
from pipelines.reconciliation import Reconciler
from storage.qdrant_store import QdrantStore


# 1. Invariant: Memory ID Stability on File Moves
def test_memory_id_stability_with_explicit_frontmatter_id(tmp_path: Path):
    explicit_uuid = uuid.uuid4()
    content = f"""---
memory_id: {explicit_uuid}
type: semantic
tags: ["#concept"]
---
# Original Memory
Concepts and architecture notes.
"""
    note_a = tmp_path / "Daily" / "2026-08-16.md"
    note_a.parent.mkdir(parents=True)
    note_a.write_text(content)

    rec_a = parse_memory(note_a, content, vault_root=tmp_path)
    assert rec_a.memory_id == explicit_uuid

    # Move note from Daily to Concepts
    note_b = tmp_path / "Concepts" / "Promoted Note.md"
    note_b.parent.mkdir(parents=True)
    note_b.write_text(content)

    rec_b = parse_memory(note_b, content, vault_root=tmp_path)
    # The memory ID must remain identical despite path relocation
    assert rec_b.memory_id == explicit_uuid
    assert rec_a.memory_id == rec_b.memory_id


def test_deterministic_id_derivation_without_frontmatter(tmp_path: Path):
    content = """---
type: semantic
---
# Path Derived
No explicit memory_id in frontmatter.
"""
    note = tmp_path / "Concepts" / "Auto.md"
    note.parent.mkdir(parents=True)
    note.write_text(content)

    rec = parse_memory(note, content, vault_root=tmp_path)
    expected_id = uuid.uuid5(MEMORY_ID_NAMESPACE, "Concepts/Auto.md")
    assert rec.memory_id == expected_id


# 2. Invariant: Incremental Reconciliation Skips Unchanged Files
@pytest.mark.asyncio
async def test_incremental_reconciliation_skips_unmodified_stat(tmp_path: Path):
    note = tmp_path / "Concepts" / "Incremental.md"
    note.parent.mkdir(parents=True)
    note.write_text("---\ntype: semantic\n---\n# Test\nContent")
    stat = note.stat()

    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()

    mock_store = AsyncMock()
    mock_store.get_document_file_stats.return_value = {
        "Concepts/Incremental.md": {
            "memory_id": doc_id,
            "status": "active",
            "mtime_ns": stat.st_mtime_ns,
            "file_size": stat.st_size,
            "current_revision_id": rev_id,
            "content_hash": "dummy",
        }
    }

    reconciler = Reconciler(tmp_path, mock_store)
    scan_result = await reconciler.scan()

    assert scan_result.discovered == 1
    assert scan_result.unchanged == 1
    assert scan_result.staged == 0
    # Store.stage_revision should not have been called because stat matched
    mock_store.stage_revision.assert_not_called()


# 3. Invariant: Qdrant Versioning, Alias, and Orphan Point Management
@pytest.mark.asyncio
async def test_qdrant_versioned_collection_and_alias():
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False

    store = QdrantStore(vector_size=768, client=mock_client)
    await store.create_versioned_collection("memory_chunks_v2_768", 768)

    mock_client.create_collection.assert_awaited_once()
    assert mock_client.create_payload_index.call_count == 6

    await store.switch_active_alias("memory_chunks_v2_768", "memory_chunks_v2")
    mock_client.update_collection_aliases.assert_awaited_once()

    test_ids = [uuid.uuid4(), uuid.uuid4()]
    await store.delete_orphaned_points(test_ids)
    mock_client.delete.assert_awaited_once()


# 4. Invariant: Fast Lightweight Readiness (<10ms) vs Deep Drift Separation
@pytest.mark.asyncio
async def test_lightweight_readiness_probe():
    mock_control = AsyncMock()
    mock_control.ping.return_value = True
    mock_control.readiness_metrics.return_value = {
        "pending_jobs": 0,
        "failed_jobs": 0,
        "pending_outbox": 0,
        "failed_outbox": 0,
        "oldest_pending_seconds": 0.0,
    }

    mock_vectors = AsyncMock()
    mock_vectors.v2_collection = "memory_chunks_v2"
    mock_vectors.client.collection_exists.return_value = True

    result = await assess_lightweight_readiness(mock_control, mock_vectors)
    assert result["ready"] is True
    assert result["components"]["postgresql"]["status"] == "ok"
    assert result["components"]["qdrant"]["status"] == "ok"


# 5. Invariant: Vault Validation & AGENTS.md Schema Rule Enforcement
def test_vault_validation_rules(tmp_path: Path):
    # Rule A: Missing frontmatter
    invalid_content = "Raw note with no frontmatter block."
    res_a = validate_note_content(invalid_content, "Daily/2026-08-16.md")
    assert res_a.valid is False
    assert any(i.code == "MISSING_FRONTMATTER" for i in res_a.issues)

    # Rule B: Missing explicit memory_id generates warning
    implicit_content = """---
type: semantic
tags: ["#test"]
---
# Note Title
Note content with [[AnotherNote]].
"""
    res_b = validate_note_content(implicit_content, "Concepts/Implicit.md", vault_root=tmp_path)
    assert res_b.valid is True  # Valid but has warning
    assert res_b.has_explicit_id is False
    assert any(i.code == "MISSING_EXPLICIT_MEMORY_ID" for i in res_b.issues)
    assert res_b.wikilinks == ["AnotherNote"]

    # Rule C: Explicit valid memory_id
    valid_uuid = uuid.uuid4()
    explicit_content = f"""---
memory_id: {valid_uuid}
type: procedural
tags: ["#ops"]
---
# Ops Runbook
Step 1: Check logs.
"""
    res_c = validate_note_content(explicit_content, "Procedures/Deploy.md", vault_root=tmp_path)
    assert res_c.valid is True
    assert res_c.has_explicit_id is True
    assert res_c.memory_id == str(valid_uuid)
