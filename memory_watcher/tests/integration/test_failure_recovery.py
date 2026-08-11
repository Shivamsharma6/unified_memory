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
    compose,
    document_row,
    managed_note,
)


pytestmark = pytest.mark.integration


async def _drain(worker, store, timeout: float = 15.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await worker.run_once()
        metrics = await store.readiness_metrics()
        if metrics["pending_outbox"] == 0:
            return
        await asyncio.sleep(0.5)
    raise AssertionError("vector outbox did not drain before timeout")


@pytest.mark.asyncio
async def test_dependency_outages_missed_events_and_malformed_notes_recover(
    tmp_path,
    live_control_plane,
):
    store, vectors = live_control_plane
    embedder = DeterministicEmbedder(vectors.vector_size)
    worker = VectorWorker(store, vectors, embedder, batch_size=20)
    reconciler = Reconciler(tmp_path, store)
    memory_id = uuid.uuid4()
    note = tmp_path / "Concepts" / "Recovery Memory.md"
    note.parent.mkdir(parents=True)
    note.write_text(managed_note(memory_id, "The first revision remains available."))
    first = await reconciler.reconcile_path(note)
    await _drain(worker, store)

    note.write_text(managed_note(memory_id, "The recovered revision becomes current."))
    second = await reconciler.reconcile_path(note)

    compose("stop", "qdrant")
    try:
        await worker.run_once()
        during_outage = await document_row(store, memory_id)
        assert during_outage["current_revision_id"] == first.revision_id
    finally:
        compose("up", "-d", "--wait", "qdrant")

    await _drain(worker, store)
    recovered = await document_row(store, memory_id)
    assert recovered["current_revision_id"] == second.revision_id

    compose("stop", "postgres")
    try:
        missed_id = uuid.uuid4()
        missed = tmp_path / "Concepts" / "Missed Event.md"
        missed.write_text(managed_note(missed_id, "A startup scan recovers this write."))
    finally:
        compose("up", "-d", "--wait", "postgres")

    scan = await reconciler.startup_reconcile()
    assert scan.failed == 0
    await _drain(worker, store)
    assert (await document_row(store, missed_id))["status"] == "active"

    malformed_id = uuid.uuid4()
    malformed = tmp_path / "Concepts" / "Malformed Then Fixed.md"
    malformed.write_text(
        "---\nmemory_id: not-a-uuid\ntype: semantic\n---\n# Broken Memory\n"
    )
    failed = await reconciler.reconcile_path(malformed)
    assert failed.status == "failed"

    malformed.write_text(
        managed_note(malformed_id, "A corrected note clears its failed ingestion state.")
    )
    fixed = await reconciler.reconcile_path(malformed)
    assert fixed.status == "staged"
    await _drain(worker, store)

    retry_id = uuid.uuid4()
    retry_note = tmp_path / "Concepts" / "Operator Retry.md"
    retry_note.write_text(managed_note(retry_id, "An exhausted vector command is recoverable."))
    await reconciler.reconcile_path(retry_note)
    exhausted = await store.claim_vector_outbox("exhaustion-test", 1)
    assert len(exhausted) == 1
    await store.fail_vector_command(
        exhausted[0],
        RuntimeError("forced terminal embedding failure"),
        max_attempts=1,
    )
    assert (await store.readiness_metrics())["failed_outbox"] == 1
    assert await store.requeue_failed_vector_commands() == 1
    await _drain(worker, store)

    report = await assess_readiness(
        tmp_path,
        store,
        vectors,
        embedder,
        HeuristicReranker(),
    )
    assert report["ready"] is True, report
    assert report["jobs"]["failed_jobs"] == 0
    assert report["drift"]["total"] == 0
