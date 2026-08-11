from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from psycopg import sql


WATCHER_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = WATCHER_ROOT.parent
COMPOSE_FILE = WATCHER_ROOT / "docker-compose.yml"
sys.path.insert(0, str(WATCHER_ROOT))

from storage.postgres_store import PostgresConfig, PostgresStore
from storage.qdrant_store import QdrantStore


def compose(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        cwd=WATCHER_ROOT,
        check=check,
        text=True,
        capture_output=True,
        timeout=120,
    )


@pytest.fixture(scope="session")
def docker_infrastructure():
    try:
        compose("up", "-d", "--wait", "postgres", "qdrant")
    except (OSError, subprocess.SubprocessError) as error:
        pytest.skip(f"Docker PostgreSQL/Qdrant infrastructure is unavailable: {error}")
    yield


async def _admin_connection():
    config = replace(PostgresConfig.from_env(), database="postgres")
    connection = await psycopg.AsyncConnection.connect(config.conninfo, autocommit=True)
    return connection


@pytest_asyncio.fixture
async def live_control_plane(docker_infrastructure):
    suffix = uuid.uuid4().hex[:16]
    database_name = f"uams_it_{suffix}"
    collection_name = f"memory_chunks_it_{suffix}"
    admin = await _admin_connection()
    await admin.execute(
        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
    )
    await admin.close()

    config = replace(
        PostgresConfig.from_env(),
        database=database_name,
        min_pool_size=1,
        max_pool_size=4,
    )
    store = PostgresStore(config)
    vectors = QdrantStore(
        vector_size=int(os.getenv("UAMS_EMBED_DIMENSION", "1024"))
    )
    vectors.v2_collection = collection_name
    await store.open()
    await store.migrate()
    await vectors.initialize_v2_collection()
    try:
        yield store, vectors
    finally:
        try:
            compose("up", "-d", "--wait", "postgres", "qdrant")
            await vectors.client.delete_collection(collection_name)
        finally:
            await store.close()
            admin = await _admin_connection()
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            await admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(database_name)
                )
            )
            await admin.close()


class DeterministicEmbedder:
    """Fast 1024-dimensional embeddings for container lifecycle tests."""

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    async def embed(self, document):
        for chunk in document.chunks:
            digest = hashlib.sha256(chunk.content.encode("utf-8")).digest()
            chunk.embedding = [
                ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
                for index in range(self.dimension)
            ]
        return document


class HeuristicReranker:
    _available = False
    model_name = "integration-heuristic"

    async def _ensure_model(self):
        return None

    async def score(self, pairs):
        return [1.0 for _ in pairs]


async def document_row(store: PostgresStore, memory_id: uuid.UUID):
    async with store.pool.connection() as connection:
        result = await connection.execute(
            """
            SELECT memory_id, path, status, current_revision_id
            FROM documents
            WHERE memory_id = %s
            """,
            (memory_id,),
        )
        return await result.fetchone()


def managed_note(
    memory_id: uuid.UUID,
    body: str,
    *,
    status: str = "active",
) -> str:
    return f"""---
memory_id: {memory_id}
type: semantic
status: {status}
aliases: []
tags: ["#integration"]
entities: ["[[PostgreSQL]]", "[[Qdrant]]"]
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
relationships:
  - predicate: uses
    target: "[[Qdrant]]"
    status: explicit
---
# Integration Memory

## Durable Fact

{body}
"""
