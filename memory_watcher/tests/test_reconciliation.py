import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.reconciliation import Reconciler


def _write_note(path: Path, memory_id: uuid.UUID, body: str = "Durable fact.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
memory_id: {memory_id}
type: semantic
status: active
aliases: []
tags: ["#test"]
entities: ["[[Qdrant]]"]
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
---
# Test Memory

## Fact
{body}
""",
        encoding="utf-8",
    )


class FakeStore:
    def __init__(self):
        self.documents = {}
        self.revisions = []
        self.failures = []
        self.active_calls = []
        self.concurrent = 0
        self.max_concurrent = 0
        self.fail_next = False

    async def stage_revision(self, **values):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("postgres unavailable")
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await asyncio.sleep(0.01)
        try:
            record = values["record"]
            content_hash = values["content_hash"]
            document_status = values["document_status"]
            existing = self.documents.get(record.memory_id)
            previous = existing["current_revision_id"] if existing else None
            if existing and existing["content_hash"] == content_hash:
                existing.update(path=record.vault_path, status=document_status)
                return SimpleNamespace(
                    revision_id=existing["revision_id"],
                    previous_revision_id=previous,
                    created=False,
                )

            revision_id = uuid.uuid4()
            self.revisions.append(revision_id)
            self.documents[record.memory_id] = {
                "path": record.vault_path,
                "status": document_status,
                "content_hash": content_hash,
                "revision_id": revision_id,
                "current_revision_id": previous,
            }
            return SimpleNamespace(
                revision_id=revision_id,
                previous_revision_id=previous,
                created=True,
            )
        finally:
            self.concurrent -= 1

    async def mark_missing_documents(self, seen_memory_ids):
        seen = set(seen_memory_ids)
        missing = []
        for memory_id, document in self.documents.items():
            if memory_id not in seen and document["status"] != "deleted":
                document["status"] = "deleted"
                missing.append(memory_id)
        return missing

    async def mark_deleted_by_path(self, vault_path):
        for memory_id, document in self.documents.items():
            if document["path"] == vault_path:
                document["status"] = "deleted"
                return memory_id
        return None

    async def record_ingestion_failure(self, vault_path, error):
        self.failures.append((vault_path, str(error)))


@pytest.mark.asyncio
async def test_content_hash_is_idempotent_and_prior_revision_stays_active(tmp_path):
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Test Memory.md"
    _write_note(note, memory_id)
    store = FakeStore()
    previous_revision = uuid.uuid4()
    store.documents[memory_id] = {
        "path": "Concepts/Test Memory.md",
        "status": "active",
        "content_hash": "older",
        "revision_id": previous_revision,
        "current_revision_id": previous_revision,
    }
    reconciler = Reconciler(tmp_path, store)

    first = await reconciler.reconcile_path(note)
    second = await reconciler.reconcile_path(note)

    assert first.status == "staged"
    assert second.status == "unchanged"
    assert len(store.revisions) == 1
    assert store.documents[memory_id]["current_revision_id"] == previous_revision
    assert store.active_calls == []


@pytest.mark.asyncio
async def test_same_memory_id_correlates_move_and_archive(tmp_path):
    memory_id = uuid.uuid4()
    original = tmp_path / "Concepts" / "Test Memory.md"
    _write_note(original, memory_id)
    store = FakeStore()
    reconciler = Reconciler(tmp_path, store)
    await reconciler.reconcile_path(original)

    moved = tmp_path / "Archive" / original.name
    moved.parent.mkdir()
    original.replace(moved)
    result = await reconciler.reconcile_path(moved)

    assert result.status == "unchanged"
    assert len(store.documents) == 1
    assert len(store.revisions) == 1
    assert store.documents[memory_id]["path"] == "Archive/Test Memory.md"
    assert store.documents[memory_id]["status"] == "archived"


@pytest.mark.asyncio
async def test_scan_marks_deleted_notes_and_excludes_generated_directories(tmp_path):
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Test Memory.md"
    _write_note(note, memory_id)
    _write_note(tmp_path / ".uams" / "backups" / "ignored.md", uuid.uuid4())
    _write_note(tmp_path / "memory_watcher" / "ignored.md", uuid.uuid4())
    store = FakeStore()
    reconciler = Reconciler(tmp_path, store)

    first = await reconciler.startup_reconcile()
    note.unlink()
    second = await reconciler.scan()

    assert first.discovered == 1
    assert second.deleted == 1
    assert store.documents[memory_id]["status"] == "deleted"


@pytest.mark.asyncio
async def test_events_for_one_memory_are_serialized(tmp_path):
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Test Memory.md"
    _write_note(note, memory_id)
    store = FakeStore()
    reconciler = Reconciler(tmp_path, store)

    await asyncio.gather(
        reconciler.reconcile_path(note),
        reconciler.reconcile_path(note),
        reconciler.reconcile_path(note),
    )

    assert store.max_concurrent == 1
    assert len(store.revisions) == 1


@pytest.mark.asyncio
async def test_failure_is_recorded_and_a_later_retry_can_succeed(tmp_path):
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Test Memory.md"
    _write_note(note, memory_id)
    store = FakeStore()
    store.fail_next = True
    reconciler = Reconciler(tmp_path, store)

    failed = await reconciler.reconcile_path(note)
    retried = await reconciler.reconcile_path(note)

    assert failed.status == "failed"
    assert "postgres unavailable" in failed.error
    assert store.failures
    assert retried.status == "staged"
