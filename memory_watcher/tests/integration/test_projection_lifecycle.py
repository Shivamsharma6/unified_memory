from __future__ import annotations

import asyncio
import uuid

import pytest

from api.readiness import assess_readiness
from pipelines.reconciliation import Reconciler
from pipelines.vector_worker import VectorWorker

from conftest import (
    DeterministicEmbedder,
    HeuristicReranker,
    document_row,
    managed_note,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_update_move_archive_restore_delete_converges_without_drift(
    tmp_path,
    live_control_plane,
):
    store, vectors = live_control_plane
    embedder = DeterministicEmbedder(vectors.vector_size)
    worker = VectorWorker(store, vectors, embedder, batch_size=20)
    reconciler = Reconciler(tmp_path, store)
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Integration Memory.md"
    note.parent.mkdir(parents=True)
    note.write_text(managed_note(memory_id, "PostgreSQL stores revision one."))

    created = await reconciler.reconcile_path(note)
    await worker.run_once()
    first = await document_row(store, memory_id)

    assert created.status == "staged"
    assert first["status"] == "active"
    assert first["current_revision_id"] == created.revision_id

    note.write_text(managed_note(memory_id, "PostgreSQL stores revision two."))
    updated = await reconciler.reconcile_path(note)
    staged = await document_row(store, memory_id)

    assert updated.revision_id != created.revision_id
    assert staged["current_revision_id"] == created.revision_id

    await worker.run_once()
    await worker.run_once()
    activated = await document_row(store, memory_id)
    assert activated["current_revision_id"] == updated.revision_id
    graph = await store.graph_neighborhood("Integration Memory")
    assert graph is not None
    link = graph["links"][0]
    assert link["source"] == "Integration Memory"
    assert link["target"] == "Qdrant"
    assert link["predicate"] == "uses"
    assert link["evidence_memory_id"] == str(memory_id)
    assert link["evidence_revision_id"] == str(updated.revision_id)
    assert link["status"] == "explicit"

    archived = tmp_path / "Archive" / note.name
    archived.parent.mkdir()
    note.replace(archived)
    moved = await reconciler.reconcile_path(archived)
    archived_row = await document_row(store, memory_id)

    assert moved.status == "unchanged"
    assert archived_row["path"] == "Archive/Integration Memory.md"
    assert archived_row["status"] == "archived"
    assert await store.valid_revision_pairs({memory_id}) == set()

    restored = tmp_path / "Concepts" / archived.name
    archived.replace(restored)
    await reconciler.reconcile_path(restored)
    restored_row = await document_row(store, memory_id)

    assert restored_row["path"] == "Concepts/Integration Memory.md"
    assert restored_row["status"] == "active"
    assert await store.valid_revision_pairs({memory_id}) == {
        (memory_id, updated.revision_id)
    }

    restored.unlink()
    deleted = await reconciler.reconcile_path(restored)
    await worker.run_once()
    deleted_row = await document_row(store, memory_id)

    assert deleted.status == "deleted"
    assert deleted_row["status"] == "deleted"

    report = await assess_readiness(
        tmp_path,
        store,
        vectors,
        embedder,
        HeuristicReranker(),
    )
    assert report["ready"] is True, report
    assert report["drift"]["total"] == 0


@pytest.mark.asyncio
async def test_parallel_reconciliation_creates_one_active_revision_per_memory(
    tmp_path,
    live_control_plane,
):
    store, vectors = live_control_plane
    worker = VectorWorker(
        store,
        vectors,
        DeterministicEmbedder(vectors.vector_size),
        batch_size=20,
    )
    reconciler = Reconciler(tmp_path, store)
    memory_ids = [uuid.uuid4() for _ in range(12)]
    notes = []
    for index, memory_id in enumerate(memory_ids):
        note = tmp_path / "Concepts" / f"Parallel Memory {index}.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(managed_note(memory_id, f"Parallel durable fact {index}."))
        notes.append(note)

    staged = await asyncio.gather(
        *(reconciler.reconcile_path(note) for note in notes)
    )
    await worker.run_once()

    assert all(result.status == "staged" for result in staged)
    async with store.pool.connection() as connection:
        result = await connection.execute(
            """
            SELECT count(*) AS documents,
                   count(DISTINCT current_revision_id) AS active_revisions
            FROM documents
            WHERE memory_id = ANY(%s) AND status = 'active'
            """,
            (memory_ids,),
        )
        counts = await result.fetchone()
    assert counts["documents"] == 12
    assert counts["active_revisions"] == 12


@pytest.mark.asyncio
async def test_profile_facts_are_exact_evidenced_and_hidden_when_archived(
    tmp_path,
    live_control_plane,
):
    store, vectors = live_control_plane
    worker = VectorWorker(
        store,
        vectors,
        DeterministicEmbedder(vectors.vector_size),
        batch_size=20,
    )
    reconciler = Reconciler(tmp_path, store)
    memory_id = uuid.uuid4()
    profile = tmp_path / "People" / "Shivam Sharma.md"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        managed_note(memory_id, "Shivam prefers durable exact profile facts.").replace(
            "relationships:\n",
            "profile_facts:\n  preferred_database: PostgreSQL\nrelationships:\n",
        ).replace("# Integration Memory", "# Shivam Sharma")
    )

    staged = await reconciler.reconcile_path(profile)
    await worker.run_once()
    current = await store.get_profile("shivam sharma")

    assert current is not None
    assert current["profile_type"] == "user"
    assert current["facts"][0]["key"] == "preferred_database"
    assert current["facts"][0]["value"] == "PostgreSQL"
    assert current["facts"][0]["evidence_memory_id"] == str(memory_id)
    assert current["facts"][0]["evidence_revision_id"] == str(staged.revision_id)

    archived = tmp_path / "Archive" / profile.name
    archived.parent.mkdir()
    profile.replace(archived)
    await reconciler.reconcile_path(archived)

    assert await store.get_profile("shivam sharma") is None
    historical = await store.get_profile("shivam sharma", include_historical=True)
    assert historical is not None
    assert historical["facts"][0]["evidence_revision_id"] == str(staged.revision_id)
