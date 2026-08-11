import json
import sys
import uuid
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.readiness import assess_readiness
from models.memory_record import parse_memory
from scripts.auto_integrate import inspect_json_target
from scripts.migrate_control_plane import write_memory_ids


def _legacy_note(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """---
type: semantic
status: active
aliases: []
tags: ["#test"]
entities: ["[[PostgreSQL]]"]
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
---
# Durable Profile

## Fact

PostgreSQL stores exact facts.
""",
        encoding="utf-8",
    )


class FakeControlStore:
    def __init__(
        self,
        memory_id,
        revision_id,
        *,
        chunk_ids=None,
        pending=0,
        failed=0,
    ):
        self.memory_id = memory_id
        self.revision_id = revision_id
        self.chunk_ids = set(chunk_ids or {uuid.uuid4()})
        self.pending = pending
        self.failed = failed

    async def ping(self):
        return True

    async def readiness_metrics(self):
        return {
            "pending_jobs": self.pending,
            "failed_jobs": self.failed,
            "pending_outbox": self.pending,
            "failed_outbox": self.failed,
            "oldest_pending_seconds": 0,
        }

    async def projection_state(self):
        return {
            "document_ids": {self.memory_id},
            "current_pairs": {(self.memory_id, self.revision_id)},
            "point_ids": self.chunk_ids,
            "expected_points": len(self.chunk_ids),
        }


class FakeVectorStore:
    def __init__(self, pairs, *, point_ids=None):
        self.pairs = set(pairs)
        self.point_ids = set(point_ids or set())

    async def readiness_probe(self, query_vector):
        return {"collection": "memory_chunks_v2", "result_count": 1}

    async def projection_state(self):
        return {
            "pairs": self.pairs,
            "point_ids": self.point_ids,
            "points": len(self.point_ids),
        }


class FakeEmbedder:
    async def embed(self, document):
        document.chunks[0].embedding = [0.1, 0.2, 0.3]
        return document


class BrokenEmbedder:
    async def embed(self, document):
        raise RuntimeError("embedding unavailable")


class FakeReranker:
    _available = False

    async def _ensure_model(self):
        return None


@pytest.mark.asyncio
async def test_readiness_reports_deep_components_and_zero_drift(tmp_path):
    note = tmp_path / "Concepts" / "Durable Profile.md"
    _legacy_note(note)
    memory_id = parse_memory(note, note.read_text(), vault_root=tmp_path).memory_id
    revision_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    control = FakeControlStore(memory_id, revision_id, chunk_ids={chunk_id})

    report = await assess_readiness(
        tmp_path,
        control,
        FakeVectorStore({(memory_id, revision_id)}, point_ids={chunk_id}),
        FakeEmbedder(),
        FakeReranker(),
    )

    assert report["ready"] is True
    assert report["components"]["postgresql"]["status"] == "ok"
    assert report["components"]["qdrant"]["status"] == "ok"
    assert report["components"]["embedding_search_probe"]["status"] == "ok"
    assert report["components"]["reranker"]["mode"] == "heuristic"
    assert report["jobs"]["pending_jobs"] == 0
    assert report["drift"]["total"] == 0


@pytest.mark.asyncio
async def test_readiness_fails_on_projection_drift_or_embedding_outage(tmp_path):
    note = tmp_path / "Concepts" / "Durable Profile.md"
    _legacy_note(note)
    memory_id = parse_memory(note, note.read_text(), vault_root=tmp_path).memory_id
    revision_id = uuid.uuid4()
    control = FakeControlStore(memory_id, revision_id)

    report = await assess_readiness(
        tmp_path,
        control,
        FakeVectorStore(set()),
        BrokenEmbedder(),
        FakeReranker(),
    )

    assert report["ready"] is False
    assert report["components"]["embedding_search_probe"]["status"] == "unavailable"
    assert report["drift"]["qdrant_missing"] == 1


@pytest.mark.asyncio
async def test_readiness_detects_chunk_swap_with_same_revision_and_point_count(tmp_path):
    note = tmp_path / "Concepts" / "Durable Profile.md"
    _legacy_note(note)
    memory_id = parse_memory(note, note.read_text(), vault_root=tmp_path).memory_id
    revision_id = uuid.uuid4()
    expected_chunk_id = uuid.uuid4()
    stale_chunk_id = uuid.uuid4()
    control = FakeControlStore(
        memory_id,
        revision_id,
        chunk_ids={expected_chunk_id},
    )

    report = await assess_readiness(
        tmp_path,
        control,
        FakeVectorStore(
            {(memory_id, revision_id)},
            point_ids={stale_chunk_id},
        ),
        FakeEmbedder(),
        FakeReranker(),
    )

    assert report["ready"] is False
    assert report["drift"]["qdrant_missing_points"] == 1
    assert report["drift"]["qdrant_stale_points"] == 1


def test_controlled_memory_id_migration_is_idempotent(tmp_path):
    note = tmp_path / "Concepts" / "Durable Profile.md"
    _legacy_note(note)

    first = write_memory_ids(tmp_path)
    first_content = note.read_text(encoding="utf-8")
    second = write_memory_ids(tmp_path)

    assert first == ["Concepts/Durable Profile.md"]
    assert second == []
    assert "memory_id:" in first_content
    assert note.read_text(encoding="utf-8") == first_content


def test_integration_inspection_reports_configured_missing_invalid_and_unreachable(tmp_path):
    expected = {"command": "/opt/uams", "args": ["mcp"], "env": {}}
    configured = tmp_path / "configured.json"
    configured.write_text(json.dumps({"mcpServers": {"uams": expected}}), encoding="utf-8")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    unreachable = tmp_path / "unreachable.json"
    unreachable.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "uams": {"command": "/does/not/exist", "args": ["mcp"], "env": {}}
                }
            }
        ),
        encoding="utf-8",
    )

    assert inspect_json_target("Configured", configured, expected)["status"] == "configured"
    assert inspect_json_target("Missing", tmp_path / "missing.json", expected)["status"] == "missing"
    assert inspect_json_target("Invalid", invalid, expected)["status"] == "invalid"
    assert inspect_json_target("Unreachable", unreachable, expected)["status"] == "unreachable"
