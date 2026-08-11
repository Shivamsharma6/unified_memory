"""PostgreSQL connection lifecycle and schema migrations for UAMS."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from graph.extractor import normalize_entity_key


_MIGRATION_RE = re.compile(r"^(?P<version>\d+)_.*\.sql$")
_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class PostgresConfig:
    """Runtime PostgreSQL settings with secret-safe diagnostics."""

    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "uams"
    user: str = "uams"
    password: str = field(default="uams-local-only", repr=False)
    min_pool_size: int = 1
    max_pool_size: int = 10
    connect_timeout: int = 5

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            host=os.getenv("UAMS_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("UAMS_POSTGRES_PORT", "5432")),
            database=os.getenv("UAMS_POSTGRES_DB", "uams"),
            user=os.getenv("UAMS_POSTGRES_USER", "uams"),
            password=os.getenv("UAMS_POSTGRES_PASSWORD", "uams-local-only"),
            min_pool_size=int(os.getenv("UAMS_POSTGRES_POOL_MIN", "1")),
            max_pool_size=int(os.getenv("UAMS_POSTGRES_POOL_MAX", "10")),
            connect_timeout=int(os.getenv("UAMS_POSTGRES_CONNECT_TIMEOUT", "5")),
        )

    @property
    def conninfo(self) -> str:
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
            connect_timeout=self.connect_timeout,
        )


@dataclass(frozen=True)
class StageRevisionResult:
    revision_id: uuid.UUID
    previous_revision_id: uuid.UUID | None
    created: bool


@dataclass(frozen=True)
class OutboxCommand:
    outbox_id: int
    command: str
    memory_id: uuid.UUID
    revision_id: uuid.UUID | None
    attempts: int


def migration_paths(directory: Path | None = None) -> list[Path]:
    """Return numbered SQL migrations in deterministic version order."""

    root = directory or _MIGRATIONS_DIR
    paths = [path for path in root.glob("*.sql") if _MIGRATION_RE.match(path.name)]
    return sorted(paths, key=lambda path: int(_MIGRATION_RE.match(path.name).group("version")))


class PostgresStore:
    """Own the async pool and apply immutable, checksummed migrations."""

    def __init__(
        self,
        config: PostgresConfig | None = None,
        *,
        pool_factory: Callable[..., AsyncConnectionPool] = AsyncConnectionPool,
    ) -> None:
        self.config = config or PostgresConfig.from_env()
        self.pool = pool_factory(
            conninfo=self.config.conninfo,
            min_size=self.config.min_pool_size,
            max_size=self.config.max_pool_size,
            open=False,
            kwargs={"row_factory": dict_row},
            check=AsyncConnectionPool.check_connection,
        )

    async def open(self) -> None:
        await self.pool.open(wait=True)

    async def close(self) -> None:
        await self.pool.close()

    async def ping(self) -> bool:
        async with self.pool.connection() as connection:
            result = await connection.execute("SELECT 1 AS ok")
            row = await result.fetchone()
            return bool(row and row["ok"] == 1)

    async def migrate(self, directory: Path | None = None) -> list[str]:
        """Apply pending migrations while preventing concurrent runners."""

        applied: list[str] = []
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("uams:schema-migrations",),
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version bigint PRIMARY KEY,
                        filename text NOT NULL UNIQUE,
                        checksum char(64) NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )

                for path in migration_paths(directory):
                    match = _MIGRATION_RE.match(path.name)
                    version = int(match.group("version"))
                    sql = path.read_text(encoding="utf-8")
                    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                    result = await connection.execute(
                        "SELECT checksum FROM schema_migrations WHERE version = %s",
                        (version,),
                    )
                    row = await result.fetchone()
                    if row:
                        if row["checksum"] != checksum:
                            raise RuntimeError(f"Migration {path.name} changed after application")
                        continue

                    await connection.execute(sql, prepare=False)
                    await connection.execute(
                        """
                        INSERT INTO schema_migrations (version, filename, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (version, path.name, checksum),
                    )
                    applied.append(path.name)

        return applied

    @staticmethod
    def _jsonable(value: Any) -> Any:
        return json.loads(json.dumps(value, default=str))

    async def stage_revision(
        self,
        *,
        record,
        raw_markdown: str,
        content_hash: str,
        chunks,
        projection,
        document_status: str,
        event_type: str,
    ) -> StageRevisionResult:
        """Stage one complete revision without changing the active revision."""

        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (str(record.memory_id),),
                )
                current_result = await connection.execute(
                    """
                    SELECT current_revision_id, path, status
                    FROM documents
                    WHERE memory_id = %s
                    """,
                    (record.memory_id,),
                )
                current = await current_result.fetchone()
                previous_revision_id = current["current_revision_id"] if current else None
                previous_path = current["path"] if current else None
                previous_status = current["status"] if current else None

                await connection.execute(
                    """
                    INSERT INTO documents (memory_id, path, memory_type, status)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (memory_id) DO UPDATE SET
                        path = EXCLUDED.path,
                        memory_type = EXCLUDED.memory_type,
                        status = EXCLUDED.status,
                        updated_at = now()
                    """,
                    (record.memory_id, record.vault_path, record.memory_type, document_status),
                )
                await connection.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = 'succeeded', finished_at = now(), updated_at = now()
                    WHERE event_type = 'reconcile'
                      AND vault_path = %s
                      AND status = 'failed'
                    """,
                    (record.vault_path,),
                )

                existing_result = await connection.execute(
                    """
                    SELECT revision_id
                    FROM document_revisions
                    WHERE memory_id = %s AND content_hash = %s
                    """,
                    (record.memory_id, content_hash),
                )
                existing = await existing_result.fetchone()
                if existing:
                    existing_revision_id = existing["revision_id"]
                    needs_projection = (
                        existing_revision_id != previous_revision_id
                        or previous_status == "deleted"
                    )
                    if needs_projection:
                        await connection.execute(
                            """
                            UPDATE document_revisions
                            SET state = 'staged', superseded_at = NULL
                            WHERE revision_id = %s
                            """,
                            (existing_revision_id,),
                        )
                        await connection.execute(
                            """
                            UPDATE profile_facts
                            SET status = 'staged', valid_to = NULL
                            WHERE evidence_revision_id = %s
                              AND status = 'superseded'
                            """,
                            (existing_revision_id,),
                        )
                        await connection.execute(
                            """
                            INSERT INTO ingestion_jobs (
                                memory_id, revision_id, event_type, status
                            ) VALUES (%s, %s, %s, 'pending')
                            """,
                            (record.memory_id, existing_revision_id, event_type),
                        )
                        await connection.execute(
                            """
                            INSERT INTO vector_outbox (
                                command, memory_id, revision_id, payload
                            ) VALUES ('upsert_revision', %s, %s, %s)
                            ON CONFLICT (command, memory_id, revision_id)
                            DO UPDATE SET
                                status = 'pending', attempts = 0,
                                available_at = now(), locked_at = NULL,
                                locked_by = NULL, last_error = NULL,
                                completed_at = NULL,
                                payload = EXCLUDED.payload
                            """,
                            (
                                record.memory_id,
                                existing_revision_id,
                                Jsonb({"content_hash": content_hash, "reprojection": True}),
                            ),
                        )
                        await connection.execute(
                            """
                            INSERT INTO memory_audit_events (
                                memory_id, revision_id, event_type, actor, details
                            ) VALUES (%s, %s, 'revision_restaged', %s, %s)
                            """,
                            (
                                record.memory_id,
                                existing_revision_id,
                                record.source_agent,
                                Jsonb(
                                    {
                                        "path": record.vault_path,
                                        "previous_revision_id": (
                                            str(previous_revision_id)
                                            if previous_revision_id
                                            else None
                                        ),
                                        "previous_status": previous_status,
                                    }
                                ),
                            ),
                        )
                        return StageRevisionResult(
                            revision_id=existing_revision_id,
                            previous_revision_id=previous_revision_id,
                            created=True,
                        )
                    if previous_path != record.vault_path or event_type == "archive":
                        await connection.execute(
                            """
                            INSERT INTO memory_audit_events
                                (memory_id, revision_id, event_type, actor, details)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                record.memory_id,
                                existing["revision_id"],
                                "move" if previous_path != record.vault_path else event_type,
                                record.source_agent,
                                Jsonb({"from": previous_path, "to": record.vault_path}),
                            ),
                        )
                    return StageRevisionResult(
                        revision_id=existing["revision_id"],
                        previous_revision_id=previous_revision_id,
                        created=False,
                    )

                revision_id = uuid.uuid4()
                await connection.execute(
                    """
                    INSERT INTO document_revisions (
                        revision_id, memory_id, content_hash, title, raw_markdown,
                        frontmatter, source_agent, project, occurred_at, state
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'staged')
                    """,
                    (
                        revision_id,
                        record.memory_id,
                        content_hash,
                        record.title,
                        raw_markdown,
                        Jsonb(self._jsonable(record.frontmatter)),
                        record.source_agent,
                        record.project,
                        record.timestamps.occurred,
                    ),
                )

                for ordinal, chunk in enumerate(chunks):
                    chunk_id = uuid.uuid5(record.memory_id, f"{content_hash}:{ordinal}")
                    await connection.execute(
                        """
                        INSERT INTO chunks (
                            chunk_id, revision_id, memory_id, ordinal, heading_path,
                            content, embedding_text, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            chunk_id,
                            revision_id,
                            record.memory_id,
                            ordinal,
                            chunk.metadata.heading_hierarchy,
                            chunk.content,
                            chunk.content,
                            Jsonb(self._jsonable(chunk.metadata.model_dump(mode="json"))),
                        ),
                    )

                entity_ids: dict[str, uuid.UUID] = {}
                for entity in projection.entities:
                    entity_result = await connection.execute(
                        """
                        INSERT INTO entities (canonical_name, normalized_key, entity_type)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (normalized_key) DO UPDATE SET
                            updated_at = now()
                        RETURNING entity_id
                        """,
                        (entity.canonical_name, entity.normalized_key, entity.entity_type),
                    )
                    entity_row = await entity_result.fetchone()
                    entity_ids[entity.normalized_key] = entity_row["entity_id"]
                    for alias in entity.aliases:
                        alias_key = normalize_entity_key(alias)
                        if not alias_key or alias_key == entity.normalized_key:
                            continue
                        await connection.execute(
                            """
                            INSERT INTO entity_aliases (entity_id, alias, normalized_key)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (normalized_key) DO UPDATE SET
                                entity_id = EXCLUDED.entity_id,
                                alias = EXCLUDED.alias
                            """,
                            (entity_row["entity_id"], alias, alias_key),
                        )

                for mention in projection.mentions:
                    entity_id = entity_ids.get(mention.normalized_key)
                    if entity_id is None:
                        continue
                    await connection.execute(
                        """
                        INSERT INTO mentions (
                            revision_id, memory_id, entity_id, surface_text, context
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            revision_id,
                            record.memory_id,
                            entity_id,
                            mention.surface_text,
                            mention.context,
                        ),
                    )

                subject_id = entity_ids.get(normalize_entity_key(record.title))
                for claim in projection.claims:
                    object_id = entity_ids.get(normalize_entity_key(claim.object))
                    if subject_id is None or object_id is None:
                        continue
                    await connection.execute(
                        """
                        INSERT INTO claims (
                            subject_entity_id, predicate, object_entity_id,
                            evidence_memory_id, evidence_revision_id, status,
                            confidence, provenance
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            subject_id,
                            claim.predicate,
                            object_id,
                            record.memory_id,
                            revision_id,
                            claim.status,
                            claim.confidence,
                            Jsonb({"path": claim.evidence_path}),
                        ),
                    )

                await self._stage_profile_facts(connection, record, revision_id)
                await connection.execute(
                    """
                    INSERT INTO ingestion_jobs (
                        memory_id, revision_id, event_type, status
                    ) VALUES (%s, %s, %s, 'pending')
                    """,
                    (record.memory_id, revision_id, event_type),
                )
                await connection.execute(
                    """
                    INSERT INTO vector_outbox (command, memory_id, revision_id, payload)
                    VALUES ('upsert_revision', %s, %s, %s)
                    ON CONFLICT (command, memory_id, revision_id) DO NOTHING
                    """,
                    (
                        record.memory_id,
                        revision_id,
                        Jsonb({"content_hash": content_hash}),
                    ),
                )
                await connection.execute(
                    """
                    INSERT INTO memory_audit_events (
                        memory_id, revision_id, event_type, actor, details
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        record.memory_id,
                        revision_id,
                        "revision_staged",
                        record.source_agent,
                        Jsonb({"path": record.vault_path, "source_event": event_type}),
                    ),
                )

                return StageRevisionResult(
                    revision_id=revision_id,
                    previous_revision_id=previous_revision_id,
                    created=True,
                )

    async def _stage_profile_facts(self, connection, record, revision_id: uuid.UUID) -> None:
        first_folder = Path(record.vault_path).parts[0] if Path(record.vault_path).parts else ""
        profile_type = {"Agents": "agent", "People": "user", "Projects": "project"}.get(first_folder)
        facts = record.frontmatter.get("profile_facts") or record.frontmatter.get("facts") or {}
        if not profile_type or not isinstance(facts, dict):
            return
        profile_result = await connection.execute(
            """
            INSERT INTO profiles (profile_type, canonical_key, display_name, metadata)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (profile_type, canonical_key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            RETURNING profile_id
            """,
            (
                profile_type,
                normalize_entity_key(record.title),
                record.title,
                Jsonb({"path": record.vault_path}),
            ),
        )
        profile = await profile_result.fetchone()
        for key, value in facts.items():
            await connection.execute(
                """
                INSERT INTO profile_facts (
                    profile_id, fact_key, fact_value,
                    evidence_memory_id, evidence_revision_id, status
                ) VALUES (%s, %s, %s, %s, %s, 'staged')
                """,
                (
                    profile["profile_id"],
                    str(key),
                    Jsonb(self._jsonable(value)),
                    record.memory_id,
                    revision_id,
                ),
            )

    async def mark_missing_documents(self, seen_memory_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
        seen = list(seen_memory_ids)
        async with self.pool.connection() as connection:
            async with connection.transaction():
                if seen:
                    result = await connection.execute(
                        """
                        SELECT memory_id, current_revision_id
                        FROM documents
                        WHERE status <> 'deleted' AND NOT (memory_id = ANY(%s))
                        FOR UPDATE
                        """,
                        (seen,),
                    )
                else:
                    result = await connection.execute(
                        """
                        SELECT memory_id, current_revision_id
                        FROM documents
                        WHERE status <> 'deleted'
                        FOR UPDATE
                        """
                    )
                rows = await result.fetchall()
                for row in rows:
                    await self._mark_deleted(connection, row["memory_id"], row["current_revision_id"])
                return [row["memory_id"] for row in rows]

    async def mark_deleted_by_path(self, vault_path: str) -> uuid.UUID | None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                result = await connection.execute(
                    """
                    SELECT memory_id, current_revision_id
                    FROM documents WHERE path = %s
                    FOR UPDATE
                    """,
                    (vault_path,),
                )
                row = await result.fetchone()
                if row is None:
                    return None
                await self._mark_deleted(connection, row["memory_id"], row["current_revision_id"])
                return row["memory_id"]

    async def _mark_deleted(self, connection, memory_id: uuid.UUID, revision_id: uuid.UUID | None) -> None:
        await connection.execute(
            "UPDATE documents SET status = 'deleted', updated_at = now() WHERE memory_id = %s",
            (memory_id,),
        )
        await connection.execute(
            """
            INSERT INTO vector_outbox (command, memory_id, revision_id, payload)
            SELECT 'delete_memory', %s, NULL, '{}'::jsonb
            WHERE NOT EXISTS (
                SELECT 1 FROM vector_outbox
                WHERE command = 'delete_memory' AND memory_id = %s
                  AND status IN ('pending', 'processing')
            )
            """,
            (memory_id, memory_id),
        )
        await connection.execute(
            """
            INSERT INTO memory_audit_events (memory_id, revision_id, event_type, details)
            VALUES (%s, %s, 'delete_discovered', '{}'::jsonb)
            """,
            (memory_id, revision_id),
        )

    async def record_ingestion_failure(self, vault_path: str, error: Exception) -> None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO ingestion_jobs (
                        event_type, status, attempts, error, finished_at, vault_path
                    )
                    VALUES ('reconcile', 'failed', 1, %s, now(), %s)
                    """,
                    (f"{vault_path}: {error}", vault_path),
                )
                await connection.execute(
                    """
                    INSERT INTO memory_audit_events (event_type, details)
                    VALUES ('reconciliation_failed', %s)
                    """,
                    (Jsonb({"path": vault_path, "error": str(error)}),),
                )

    async def claim_vector_outbox(
        self,
        worker_id: str,
        limit: int = 10,
    ) -> list[OutboxCommand]:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                result = await connection.execute(
                    """
                    WITH picked AS (
                        SELECT outbox_id
                        FROM vector_outbox
                        WHERE (status = 'pending' AND available_at <= now())
                           OR (status = 'processing' AND locked_at < now() - interval '5 minutes')
                        ORDER BY outbox_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE vector_outbox AS outbox
                    SET status = 'processing',
                        attempts = outbox.attempts + 1,
                        locked_at = now(),
                        locked_by = %s
                    FROM picked
                    WHERE outbox.outbox_id = picked.outbox_id
                    RETURNING outbox.outbox_id, outbox.command, outbox.memory_id,
                              outbox.revision_id, outbox.attempts
                    """,
                    (limit, worker_id),
                )
                rows = await result.fetchall()
                return [OutboxCommand(**row) for row in rows]

    async def load_revision_chunks(self, revision_id: uuid.UUID) -> list[dict[str, Any]]:
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT c.chunk_id, c.content, c.heading_path, c.metadata,
                       d.memory_id, d.memory_type, d.path,
                       r.revision_id, r.project, r.source_agent, r.frontmatter,
                       COALESCE((
                           SELECT array_agg(DISTINCT e.normalized_key)
                           FROM mentions m
                           JOIN entities e ON e.entity_id = m.entity_id
                           WHERE m.revision_id = r.revision_id
                       ), ARRAY[]::text[]) AS entity_keys
                FROM chunks c
                JOIN document_revisions r ON r.revision_id = c.revision_id
                JOIN documents d ON d.memory_id = r.memory_id
                WHERE c.revision_id = %s
                ORDER BY c.ordinal
                """,
                (revision_id,),
            )
            rows = await result.fetchall()
            values = []
            for row in rows:
                metadata = row["metadata"] or {}
                frontmatter = row["frontmatter"] or {}
                values.append(
                    {
                        "chunk_id": row["chunk_id"],
                        "text": row["content"],
                        "payload": {
                            "chunk_id": str(row["chunk_id"]),
                            "memory_id": str(row["memory_id"]),
                            "revision_id": str(row["revision_id"]),
                            "memory_type": row["memory_type"],
                            "project": row["project"],
                            "source_agent": row["source_agent"],
                            "source_file": row["path"],
                            "heading_hierarchy": row["heading_path"],
                            "tags": metadata.get("tags", []),
                            "entity_keys": row["entity_keys"],
                            "timestamps": frontmatter.get("timestamps", {}),
                            "text": row["content"],
                        },
                    }
                )
            return values

    async def acknowledge_vector_upsert(
        self,
        command: OutboxCommand,
    ) -> uuid.UUID | None:
        if command.revision_id is None:
            raise ValueError("upsert_revision requires a revision_id")
        async with self.pool.connection() as connection:
            async with connection.transaction():
                document_result = await connection.execute(
                    """
                    SELECT current_revision_id
                    FROM documents
                    WHERE memory_id = %s
                    FOR UPDATE
                    """,
                    (command.memory_id,),
                )
                document = await document_result.fetchone()
                if document is None:
                    raise RuntimeError(f"Memory {command.memory_id} no longer exists")
                previous_revision_id = document["current_revision_id"]

                if previous_revision_id and previous_revision_id != command.revision_id:
                    await connection.execute(
                        """
                        UPDATE document_revisions
                        SET state = 'superseded', superseded_at = now()
                        WHERE revision_id = %s
                        """,
                        (previous_revision_id,),
                    )
                    await connection.execute(
                        """
                        UPDATE profile_facts
                        SET status = 'superseded', valid_to = now()
                        WHERE evidence_revision_id = %s AND status = 'active'
                        """,
                        (previous_revision_id,),
                    )

                await connection.execute(
                    """
                    UPDATE document_revisions
                    SET state = 'active', activated_at = COALESCE(activated_at, now())
                    WHERE revision_id = %s AND memory_id = %s
                    """,
                    (command.revision_id, command.memory_id),
                )
                await connection.execute(
                    """
                    UPDATE documents
                    SET current_revision_id = %s, updated_at = now()
                    WHERE memory_id = %s
                    """,
                    (command.revision_id, command.memory_id),
                )
                await connection.execute(
                    """
                    UPDATE profile_facts
                    SET status = 'active', valid_from = now()
                    WHERE evidence_revision_id = %s AND status = 'staged'
                    """,
                    (command.revision_id,),
                )
                await self._complete_outbox_row(connection, command.outbox_id)
                await connection.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = 'succeeded', finished_at = now(), updated_at = now()
                    WHERE revision_id = %s AND status IN ('pending', 'running', 'retrying')
                    """,
                    (command.revision_id,),
                )
                if previous_revision_id and previous_revision_id != command.revision_id:
                    await connection.execute(
                        """
                        INSERT INTO vector_outbox (
                            command, memory_id, revision_id, payload
                        ) VALUES ('delete_revision', %s, %s, '{}'::jsonb)
                        ON CONFLICT (command, memory_id, revision_id)
                        DO UPDATE SET
                            status = 'pending', attempts = 0,
                            available_at = now(), locked_at = NULL,
                            locked_by = NULL, last_error = NULL,
                            completed_at = NULL
                        """,
                        (command.memory_id, previous_revision_id),
                    )
                await connection.execute(
                    """
                    INSERT INTO memory_audit_events (
                        memory_id, revision_id, event_type, details
                    ) VALUES (%s, %s, 'revision_activated', %s)
                    """,
                    (
                        command.memory_id,
                        command.revision_id,
                        Jsonb(
                            {
                                "previous_revision_id": (
                                    str(previous_revision_id) if previous_revision_id else None
                                )
                            }
                        ),
                    ),
                )
                return previous_revision_id

    async def _complete_outbox_row(self, connection, outbox_id: int) -> None:
        await connection.execute(
            """
            UPDATE vector_outbox
            SET status = 'succeeded', completed_at = now(),
                locked_at = NULL, locked_by = NULL, last_error = NULL
            WHERE outbox_id = %s
            """,
            (outbox_id,),
        )

    async def complete_vector_command(self, command: OutboxCommand) -> None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await self._complete_outbox_row(connection, command.outbox_id)
                await connection.execute(
                    """
                    INSERT INTO memory_audit_events (
                        memory_id, revision_id, event_type, details
                    ) VALUES (%s, %s, 'vector_cleanup_completed', %s)
                    """,
                    (
                        command.memory_id,
                        command.revision_id,
                        Jsonb({"command": command.command}),
                    ),
                )

    async def fail_vector_command(
        self,
        command: OutboxCommand,
        error: Exception,
        max_attempts: int = 8,
    ) -> None:
        exhausted = command.attempts >= max_attempts
        delay_seconds = min(2 ** max(command.attempts, 1), 300)
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    UPDATE vector_outbox
                    SET status = %s,
                        available_at = now() + (%s * interval '1 second'),
                        locked_at = NULL,
                        locked_by = NULL,
                        last_error = %s
                    WHERE outbox_id = %s
                    """,
                    ("failed" if exhausted else "pending", delay_seconds, str(error), command.outbox_id),
                )
                if command.revision_id:
                    await connection.execute(
                        """
                        UPDATE ingestion_jobs
                        SET status = %s, attempts = %s, error = %s, updated_at = now(),
                            finished_at = CASE WHEN %s THEN now() ELSE NULL END
                        WHERE revision_id = %s AND status <> 'succeeded'
                        """,
                        (
                            "failed" if exhausted else "retrying",
                            command.attempts,
                            str(error),
                            exhausted,
                            command.revision_id,
                        ),
                    )

    async def fts_search(
        self,
        query: str,
        *,
        limit: int = 20,
        memory_types: list[str] | None = None,
        projects: list[str] | None = None,
        source_agents: list[str] | None = None,
        include_historical: bool = False,
    ) -> list[dict[str, Any]]:
        conditions = ["c.search_vector @@ search_queries.relaxed_query"]
        parameters: list[Any] = []
        if include_historical:
            conditions.append("r.state IN ('active', 'superseded')")
        else:
            conditions.extend(
                [
                    "d.status = 'active'",
                    "d.current_revision_id = c.revision_id",
                    "r.state = 'active'",
                ]
            )
        for column, values in (
            ("d.memory_type", memory_types),
            ("r.project", projects),
            ("r.source_agent", source_agents),
        ):
            if values:
                conditions.append(f"{column} = ANY(%s)")
                parameters.append(values)
        parameters = [query, query, query, *parameters, limit]
        sql = f"""
            WITH search_queries AS (
                SELECT
                    websearch_to_tsquery('english'::regconfig, %s) AS strict_query,
                    tsvector_to_array(
                        to_tsvector('english'::regconfig, %s)
                    ) AS query_lexemes,
                    to_tsquery(
                        'english'::regconfig,
                        array_to_string(
                            tsvector_to_array(
                                to_tsvector('english'::regconfig, %s)
                            ),
                            ' | '
                        )
                    ) AS relaxed_query
            )
            SELECT c.chunk_id, c.content, c.heading_path, c.metadata,
                   d.memory_id, d.memory_type, d.path,
                   r.revision_id, r.project, r.source_agent, r.frontmatter,
                   (lexical.coverage
                       + CASE
                           WHEN c.search_vector @@ search_queries.strict_query
                           THEN 0.25 ELSE 0.0
                         END
                       + LEAST(0.25, ts_rank_cd(
                           c.search_vector,
                           search_queries.relaxed_query
                         ))
                   ) AS rank,
                   COALESCE((
                       SELECT array_agg(DISTINCT e.normalized_key)
                       FROM mentions m
                       JOIN entities e ON e.entity_id = m.entity_id
                       WHERE m.revision_id = r.revision_id
                   ), ARRAY[]::text[]) AS entity_keys
            FROM chunks c
            JOIN document_revisions r ON r.revision_id = c.revision_id
            JOIN documents d ON d.memory_id = r.memory_id
            CROSS JOIN search_queries
            CROSS JOIN LATERAL (
                SELECT
                    cardinality(
                        ARRAY(
                            SELECT unnest(search_queries.query_lexemes)
                            INTERSECT
                            SELECT unnest(tsvector_to_array(c.search_vector))
                        )
                    )::double precision
                    / GREATEST(cardinality(search_queries.query_lexemes), 1)
                    AS coverage
            ) AS lexical
            WHERE {' AND '.join(conditions)}
            ORDER BY
                lexical.coverage DESC,
                (c.search_vector @@ search_queries.strict_query) DESC,
                rank DESC,
                c.ordinal
            LIMIT %s
        """
        async with self.pool.connection() as connection:
            result = await connection.execute(sql, parameters)
            rows = await result.fetchall()
        return [
            {
                "id": str(row["chunk_id"]),
                "rank": float(row["rank"]),
                "payload": {
                    "chunk_id": str(row["chunk_id"]),
                    "memory_id": str(row["memory_id"]),
                    "revision_id": str(row["revision_id"]),
                    "memory_type": row["memory_type"],
                    "project": row["project"],
                    "source_agent": row["source_agent"],
                    "source_file": row["path"],
                    "heading_hierarchy": row["heading_path"],
                    "tags": (row["metadata"] or {}).get("tags", []),
                    "entity_keys": row["entity_keys"],
                    "timestamps": (row["frontmatter"] or {}).get("timestamps", {}),
                    "text": row["content"],
                },
            }
            for row in rows
        ]

    async def valid_revision_pairs(
        self,
        memory_ids: Iterable[uuid.UUID],
        *,
        include_historical: bool = False,
    ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        ids = list(memory_ids)
        if not ids:
            return set()
        conditions = ["r.memory_id = ANY(%s)"]
        if include_historical:
            conditions.append("r.state IN ('active', 'superseded')")
        else:
            conditions.extend(
                [
                    "d.status = 'active'",
                    "d.current_revision_id = r.revision_id",
                    "r.state = 'active'",
                ]
            )
        async with self.pool.connection() as connection:
            result = await connection.execute(
                f"""
                SELECT r.memory_id, r.revision_id
                FROM document_revisions r
                JOIN documents d ON d.memory_id = r.memory_id
                WHERE {' AND '.join(conditions)}
                """,
                (ids,),
            )
            rows = await result.fetchall()
        return {(row["memory_id"], row["revision_id"]) for row in rows}

    async def expand_verified_entities(
        self,
        entity_keys: list[str],
        *,
        limit: int = 20,
    ) -> dict[str, float]:
        if not entity_keys:
            return {}
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                WITH seed_entities AS (
                    SELECT entity_id FROM entities WHERE normalized_key = ANY(%s)
                    UNION
                    SELECT entity_id FROM entity_aliases WHERE normalized_key = ANY(%s)
                ), neighbors AS (
                    SELECT object_entity_id AS entity_id, predicate, confidence
                    FROM claims
                    JOIN documents d ON d.memory_id = evidence_memory_id
                    WHERE subject_entity_id IN (SELECT entity_id FROM seed_entities)
                      AND claims.status IN ('explicit', 'verified')
                      AND d.status = 'active'
                      AND d.current_revision_id = evidence_revision_id
                    UNION ALL
                    SELECT subject_entity_id AS entity_id, predicate, confidence
                    FROM claims
                    JOIN documents d ON d.memory_id = evidence_memory_id
                    WHERE object_entity_id IN (SELECT entity_id FROM seed_entities)
                      AND claims.status IN ('explicit', 'verified')
                      AND d.status = 'active'
                      AND d.current_revision_id = evidence_revision_id
                )
                SELECT e.normalized_key, neighbors.predicate, max(neighbors.confidence) AS confidence
                FROM neighbors
                JOIN entities e ON e.entity_id = neighbors.entity_id
                WHERE neighbors.entity_id IS NOT NULL
                GROUP BY e.normalized_key, neighbors.predicate
                ORDER BY confidence DESC
                LIMIT %s
                """,
                (entity_keys, entity_keys, limit),
            )
            rows = await result.fetchall()
        predicate_weights = {
            "fixes": 0.10,
            "resolves": 0.10,
            "caused_by": 0.08,
            "depends_on": 0.06,
            "uses": 0.05,
            "related_to": 0.04,
        }
        expansion: dict[str, float] = {}
        for row in rows:
            weight = predicate_weights.get(row["predicate"], 0.03) * float(row["confidence"])
            expansion[row["normalized_key"]] = max(
                expansion.get(row["normalized_key"], 0.0),
                min(weight, 0.10),
            )
        return expansion

    async def profile_memory_boosts(
        self,
        query: str,
        entity_keys: list[str],
    ) -> dict[uuid.UUID, float]:
        normalized_query = normalize_entity_key(query)
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT DISTINCT pf.evidence_memory_id
                FROM profiles p
                JOIN profile_facts pf ON pf.profile_id = p.profile_id
                JOIN documents d ON d.memory_id = pf.evidence_memory_id
                WHERE pf.status = 'active'
                  AND d.status = 'active'
                  AND d.current_revision_id = pf.evidence_revision_id
                  AND (
                      %s LIKE '%%' || p.canonical_key || '%%'
                      OR p.canonical_key = ANY(%s)
                  )
                """,
                (normalized_query, entity_keys),
            )
            rows = await result.fetchall()
        return {row["evidence_memory_id"]: 0.08 for row in rows}

    async def _claim_rows(
        self,
        *,
        include_candidates: bool = False,
        include_historical: bool = False,
    ) -> list[dict[str, Any]]:
        statuses = ["explicit", "verified"]
        if include_candidates:
            statuses.append("candidate")
        lifecycle = (
            "r.state IN ('active', 'superseded')"
            if include_historical
            else "d.status = 'active' AND d.current_revision_id = c.evidence_revision_id"
        )
        async with self.pool.connection() as connection:
            result = await connection.execute(
                f"""
                SELECT c.claim_id, c.predicate, c.status, c.confidence,
                       c.evidence_memory_id, c.evidence_revision_id,
                       s.canonical_name AS subject_name,
                       s.entity_type AS subject_type,
                       o.canonical_name AS object_name,
                       o.entity_type AS object_type,
                       c.object_value,
                       d.path AS evidence_path
                FROM claims c
                JOIN entities s ON s.entity_id = c.subject_entity_id
                LEFT JOIN entities o ON o.entity_id = c.object_entity_id
                JOIN documents d ON d.memory_id = c.evidence_memory_id
                JOIN document_revisions r ON r.revision_id = c.evidence_revision_id
                WHERE c.status = ANY(%s) AND {lifecycle}
                ORDER BY c.claim_id
                """,
                (statuses,),
            )
            return await result.fetchall()

    @staticmethod
    def _claim_graph(rows: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        links = []
        for row in rows:
            subject = row["subject_name"]
            object_name = row["object_name"]
            if object_name is None:
                object_name = f"Literal:{row['claim_id']}"
                object_label = row["object_value"]
                object_type = "literal"
            else:
                object_label = object_name
                object_type = row["object_type"]
            nodes[subject] = {
                "id": subject,
                "label": subject,
                "type": row["subject_type"],
            }
            nodes[object_name] = {
                "id": object_name,
                "label": object_label,
                "type": object_type,
            }
            links.append(
                {
                    "key": str(row["claim_id"]),
                    "source": subject,
                    "target": object_name,
                    "relation": row["predicate"],
                    "predicate": row["predicate"],
                    "claim_id": str(row["claim_id"]),
                    "evidence_memory_id": str(row["evidence_memory_id"]),
                    "evidence_revision_id": str(row["evidence_revision_id"]),
                    "evidence_path": row["evidence_path"],
                    "confidence": float(row["confidence"]),
                    "status": row["status"],
                }
            )
        return {
            "directed": True,
            "multigraph": True,
            "graph": {},
            "nodes": list(nodes.values()),
            "links": links,
        }

    async def export_claim_graph(
        self,
        *,
        include_candidates: bool = False,
        include_historical: bool = False,
    ) -> dict[str, Any]:
        rows = await self._claim_rows(
            include_candidates=include_candidates,
            include_historical=include_historical,
        )
        return self._claim_graph(rows)

    async def graph_neighborhood(
        self,
        entity: str,
        *,
        radius: int = 1,
        include_candidates: bool = False,
        include_historical: bool = False,
    ) -> dict[str, Any] | None:
        graph = await self.export_claim_graph(
            include_candidates=include_candidates,
            include_historical=include_historical,
        )
        requested_key = normalize_entity_key(entity)
        start = next(
            (
                node["id"]
                for node in graph["nodes"]
                if normalize_entity_key(str(node["label"])) == requested_key
            ),
            None,
        )
        if start is None:
            return None
        adjacency: dict[str, set[str]] = {}
        for link in graph["links"]:
            adjacency.setdefault(link["source"], set()).add(link["target"])
            adjacency.setdefault(link["target"], set()).add(link["source"])
        reached = {start}
        frontier = {start}
        for _ in range(max(0, radius)):
            frontier = {
                neighbor
                for node in frontier
                for neighbor in adjacency.get(node, set())
                if neighbor not in reached
            }
            reached.update(frontier)
        graph["nodes"] = [node for node in graph["nodes"] if node["id"] in reached]
        graph["links"] = [
            link
            for link in graph["links"]
            if link["source"] in reached and link["target"] in reached
        ]
        return graph

    async def get_profile(
        self,
        profile_id: str,
        *,
        include_historical: bool = False,
    ) -> dict[str, Any] | None:
        try:
            parsed_id = uuid.UUID(profile_id)
        except ValueError:
            parsed_id = None
        async with self.pool.connection() as connection:
            if parsed_id:
                profile_result = await connection.execute(
                    "SELECT * FROM profiles WHERE profile_id = %s",
                    (parsed_id,),
                )
            else:
                profile_result = await connection.execute(
                    "SELECT * FROM profiles WHERE canonical_key = %s",
                    (normalize_entity_key(profile_id),),
                )
            profile = await profile_result.fetchone()
            if profile is None:
                return None
            lifecycle = (
                "pf.status IN ('active', 'superseded')"
                if include_historical
                else "pf.status = 'active' AND d.status = 'active' "
                "AND d.current_revision_id = pf.evidence_revision_id"
            )
            facts_result = await connection.execute(
                f"""
                SELECT pf.fact_id, pf.fact_key, pf.fact_value, pf.status,
                       pf.evidence_memory_id, pf.evidence_revision_id,
                       pf.valid_from, pf.valid_to, d.path AS source_file
                FROM profile_facts pf
                JOIN documents d ON d.memory_id = pf.evidence_memory_id
                WHERE pf.profile_id = %s AND {lifecycle}
                ORDER BY pf.fact_key, pf.valid_from DESC
                """,
                (profile["profile_id"],),
            )
            facts = await facts_result.fetchall()
        if not facts and not include_historical:
            return None
        return {
            "profile_id": str(profile["profile_id"]),
            "profile_type": profile["profile_type"],
            "canonical_key": profile["canonical_key"],
            "display_name": profile["display_name"],
            "metadata": profile["metadata"],
            "facts": [
                {
                    "fact_id": str(fact["fact_id"]),
                    "key": fact["fact_key"],
                    "value": fact["fact_value"],
                    "status": fact["status"],
                    "evidence_memory_id": str(fact["evidence_memory_id"]),
                    "evidence_revision_id": str(fact["evidence_revision_id"]),
                    "source_file": fact["source_file"],
                    "valid_from": fact["valid_from"],
                    "valid_to": fact["valid_to"],
                }
                for fact in facts
            ],
        }

    async def get_memory_status(self, memory_id: uuid.UUID) -> dict[str, Any] | None:
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT d.memory_id, d.path, d.status AS document_status,
                       d.current_revision_id,
                       latest.revision_id AS latest_revision_id,
                       latest.state AS revision_state,
                       job.status AS job_status,
                       outbox.status AS outbox_status,
                       outbox.last_error
                FROM documents d
                LEFT JOIN LATERAL (
                    SELECT revision_id, state
                    FROM document_revisions
                    WHERE memory_id = d.memory_id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) latest ON true
                LEFT JOIN LATERAL (
                    SELECT status
                    FROM ingestion_jobs
                    WHERE memory_id = d.memory_id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) job ON true
                LEFT JOIN LATERAL (
                    SELECT status, last_error
                    FROM vector_outbox
                    WHERE memory_id = d.memory_id
                    ORDER BY outbox_id DESC
                    LIMIT 1
                ) outbox ON true
                WHERE d.memory_id = %s
                """,
                (memory_id,),
            )
            row = await result.fetchone()
        if row is None:
            return None
        indexed = (
            row["current_revision_id"] == row["latest_revision_id"]
            and row["revision_state"] == "active"
            and row["document_status"] == "active"
        )
        failed = row["job_status"] == "failed" or row["outbox_status"] == "failed"
        return {
            "memory_id": str(row["memory_id"]),
            "path": row["path"],
            "document_status": row["document_status"],
            "current_revision_id": (
                str(row["current_revision_id"]) if row["current_revision_id"] else None
            ),
            "latest_revision_id": (
                str(row["latest_revision_id"]) if row["latest_revision_id"] else None
            ),
            "revision_state": row["revision_state"],
            "index_status": "indexed" if indexed else ("failed" if failed else "pending"),
            "job_status": row["job_status"],
            "outbox_status": row["outbox_status"],
            "error": row["last_error"],
        }

    async def list_entities(self) -> list[str]:
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT DISTINCT e.canonical_name
                FROM entities e
                WHERE EXISTS (
                    SELECT 1
                    FROM mentions m
                    JOIN documents d ON d.memory_id = m.memory_id
                    WHERE m.entity_id = e.entity_id
                      AND d.status = 'active'
                      AND d.current_revision_id = m.revision_id
                ) OR EXISTS (
                    SELECT 1
                    FROM claims c
                    JOIN documents d ON d.memory_id = c.evidence_memory_id
                    WHERE (c.subject_entity_id = e.entity_id OR c.object_entity_id = e.entity_id)
                      AND c.status IN ('explicit', 'verified')
                      AND d.status = 'active'
                      AND d.current_revision_id = c.evidence_revision_id
                )
                ORDER BY e.canonical_name
                """
            )
            rows = await result.fetchall()
        return [row["canonical_name"] for row in rows]

    async def readiness_metrics(self) -> dict[str, Any]:
        async with self.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT
                    count(*) FILTER (WHERE status IN ('pending', 'running', 'retrying'))
                        AS pending_jobs,
                    count(*) FILTER (WHERE status = 'failed') AS failed_jobs,
                    COALESCE(extract(epoch FROM now() - min(created_at)
                        FILTER (WHERE status IN ('pending', 'running', 'retrying'))), 0)
                        AS oldest_pending_seconds
                FROM ingestion_jobs
                """
            )
            jobs = await result.fetchone()
            outbox_result = await connection.execute(
                """
                SELECT
                    count(*) FILTER (WHERE status IN ('pending', 'processing'))
                        AS pending_outbox,
                    count(*) FILTER (WHERE status = 'failed') AS failed_outbox
                FROM vector_outbox
                """
            )
            outbox = await outbox_result.fetchone()
        return {
            "pending_jobs": int(jobs["pending_jobs"]),
            "failed_jobs": int(jobs["failed_jobs"]),
            "pending_outbox": int(outbox["pending_outbox"]),
            "failed_outbox": int(outbox["failed_outbox"]),
            "oldest_pending_seconds": float(jobs["oldest_pending_seconds"] or 0),
        }

    async def requeue_failed_vector_commands(self) -> int:
        """Requeue exhausted vector work for an explicit operator migration retry."""

        async with self.pool.connection() as connection:
            async with connection.transaction():
                result = await connection.execute(
                    """
                    UPDATE vector_outbox
                    SET status = 'pending', available_at = now(),
                        locked_at = NULL, locked_by = NULL
                    WHERE status = 'failed'
                    RETURNING revision_id
                    """
                )
                rows = await result.fetchall()
                revision_ids = [
                    row["revision_id"]
                    for row in rows
                    if row["revision_id"] is not None
                ]
                if revision_ids:
                    await connection.execute(
                        """
                        UPDATE ingestion_jobs
                        SET status = 'retrying', finished_at = NULL, updated_at = now()
                        WHERE revision_id = ANY(%s) AND status = 'failed'
                        """,
                        (revision_ids,),
                    )
        return len(rows)

    async def projection_state(self) -> dict[str, Any]:
        async with self.pool.connection() as connection:
            documents_result = await connection.execute(
                """
                SELECT d.memory_id, d.current_revision_id,
                       EXISTS (
                           SELECT 1 FROM chunks c
                           WHERE c.revision_id = d.current_revision_id
                       ) AS has_chunks
                FROM documents d
                WHERE d.status <> 'deleted'
                """
            )
            documents = await documents_result.fetchall()
            points_result = await connection.execute(
                """
                SELECT c.chunk_id
                FROM chunks c
                JOIN documents d ON d.current_revision_id = c.revision_id
                WHERE d.status <> 'deleted'
                """
            )
            point_rows = await points_result.fetchall()
        point_ids = {row["chunk_id"] for row in point_rows}
        return {
            "document_ids": {row["memory_id"] for row in documents},
            "current_pairs": {
                (row["memory_id"], row["current_revision_id"])
                for row in documents
                if row["current_revision_id"] is not None and row["has_chunks"]
            },
            "point_ids": point_ids,
            "expected_points": len(point_ids),
        }
