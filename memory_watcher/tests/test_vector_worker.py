import sys
import uuid
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.vector_worker import VectorWorker
from storage.postgres_store import OutboxCommand
from storage.qdrant_store import QdrantStore


class FakeQdrantClient:
    def __init__(self):
        self.created = []
        self.indexes = []
        self.upserts = []
        self.deletes = []

    async def collection_exists(self, name):
        return False

    async def create_collection(self, **values):
        self.created.append(values)

    async def create_payload_index(self, **values):
        self.indexes.append(values)

    async def upsert(self, **values):
        self.upserts.append(values)

    async def delete(self, **values):
        self.deletes.append(values)


@pytest.mark.asyncio
async def test_v2_collection_and_payload_indexes_are_initialized():
    client = FakeQdrantClient()
    store = QdrantStore(vector_size=3, client=client)

    await store.initialize_v2_collection()

    assert [item["collection_name"] for item in client.created] == ["memory_chunks_v2"]
    assert {item["field_name"] for item in client.indexes} == {
        "memory_id",
        "revision_id",
        "memory_type",
        "project",
        "source_agent",
        "entity_keys",
    }


@pytest.mark.asyncio
async def test_revision_upsert_waits_for_ack_and_deletes_by_both_ids():
    client = FakeQdrantClient()
    store = QdrantStore(vector_size=3, client=client)
    memory_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    await store.upsert_revision(
        [
            {
                "chunk_id": chunk_id,
                "vector": [0.1, 0.2, 0.3],
                "payload": {
                    "memory_id": str(memory_id),
                    "revision_id": str(revision_id),
                    "text": "durable fact",
                },
            }
        ]
    )
    await store.delete_revision(memory_id, revision_id)

    assert client.upserts[0]["wait"] is True
    assert str(client.upserts[0]["points"][0].id) == str(chunk_id)
    conditions = client.deletes[0]["points_selector"].filter.must
    assert {(condition.key, condition.match.value) for condition in conditions} == {
        ("memory_id", str(memory_id)),
        ("revision_id", str(revision_id)),
    }


class FakeEmbedder:
    async def embed(self, document):
        for chunk in document.chunks:
            chunk.embedding = [0.1, 0.2, 0.3]
        return document


class FakeVectorStore:
    vector_size = 3

    def __init__(self, fail_upsert=False):
        self.fail_upsert = fail_upsert
        self.upserts = []
        self.deleted_revisions = []
        self.deleted_memories = []

    async def initialize_v2_collection(self):
        return None

    async def upsert_revision(self, points):
        if self.fail_upsert:
            raise RuntimeError("qdrant unavailable")
        self.upserts.append(points)

    async def delete_revision(self, memory_id, revision_id):
        self.deleted_revisions.append((memory_id, revision_id))

    async def delete_memory(self, memory_id):
        self.deleted_memories.append(memory_id)


class FakeControlStore:
    def __init__(self, command, rows=None, previous_revision_id=None):
        self.commands = [command]
        self.rows = rows or []
        self.previous_revision_id = previous_revision_id
        self.activated = []
        self.completed = []
        self.failed = []

    async def claim_vector_outbox(self, worker_id, limit):
        claimed, self.commands = self.commands[:limit], self.commands[limit:]
        return claimed

    async def load_revision_chunks(self, revision_id):
        return self.rows

    async def acknowledge_vector_upsert(self, command):
        self.activated.append(command.revision_id)
        if self.previous_revision_id:
            self.commands.append(
                OutboxCommand(
                    outbox_id=command.outbox_id + 1,
                    command="delete_revision",
                    memory_id=command.memory_id,
                    revision_id=self.previous_revision_id,
                    attempts=0,
                )
            )
        return self.previous_revision_id

    async def complete_vector_command(self, command):
        self.completed.append(command.outbox_id)

    async def fail_vector_command(self, command, error):
        self.failed.append((command.outbox_id, str(error)))


def _upsert_command(memory_id, revision_id):
    return OutboxCommand(
        outbox_id=1,
        command="upsert_revision",
        memory_id=memory_id,
        revision_id=revision_id,
        attempts=0,
    )


@pytest.mark.asyncio
async def test_worker_activates_only_after_upsert_and_durably_cleans_old_revision():
    memory_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    previous_revision_id = uuid.uuid4()
    control = FakeControlStore(
        _upsert_command(memory_id, revision_id),
        rows=[
            {
                "chunk_id": uuid.uuid4(),
                "text": "PostgreSQL stores the active revision.",
                "payload": {
                    "memory_id": str(memory_id),
                    "revision_id": str(revision_id),
                    "source_file": "Concepts/Test.md",
                },
            }
        ],
        previous_revision_id=previous_revision_id,
    )
    vectors = FakeVectorStore()
    worker = VectorWorker(control, vectors, FakeEmbedder(), batch_size=10)

    assert await worker.run_once() == 1
    assert control.activated == [revision_id]
    assert len(vectors.upserts) == 1
    assert vectors.deleted_revisions == []

    assert await worker.run_once() == 1
    assert vectors.deleted_revisions == [(memory_id, previous_revision_id)]
    assert control.completed == [2]


@pytest.mark.asyncio
async def test_worker_retries_without_activation_when_qdrant_fails():
    memory_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    command = _upsert_command(memory_id, revision_id)
    control = FakeControlStore(
        command,
        rows=[
            {
                "chunk_id": uuid.uuid4(),
                "text": "Retry this revision.",
                "payload": {
                    "memory_id": str(memory_id),
                    "revision_id": str(revision_id),
                },
            }
        ],
    )
    vectors = FakeVectorStore(fail_upsert=True)
    worker = VectorWorker(control, vectors, FakeEmbedder())

    assert await worker.run_once() == 1

    assert control.activated == []
    assert control.failed == [(1, "qdrant unavailable")]
