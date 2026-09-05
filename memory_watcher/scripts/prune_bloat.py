#!/usr/bin/env python3
"""
Prune runaway revisions and chunks from PostgreSQL and recover disk space.

Usage:
    cd memory_watcher && .venv/bin/python scripts/prune_bloat.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prune_bloat")

POSTGRES_HOST = os.getenv("UAMS_POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("UAMS_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("UAMS_POSTGRES_DB", "uams")
POSTGRES_USER = os.getenv("UAMS_POSTGRES_USER", "uams")
POSTGRES_PASSWORD = os.getenv("UAMS_POSTGRES_PASSWORD", "uams-local-only")


async def get_db_size(conn) -> str:
    res = await conn.execute("SELECT pg_size_pretty(pg_database_size(%s)) AS size", (POSTGRES_DB,))
    row = await res.fetchone()
    return row["size"] if row else "unknown"


async def main():
    conn_str = f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
    logger.info("Connecting to PostgreSQL at %s:%d/%s...", POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB)

    async with await psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row, autocommit=True) as conn:
        initial_size = await get_db_size(conn)
        logger.info("Initial Database Size: %s", initial_size)

        # 1. Check verified-autoswe-knowledge document
        res = await conn.execute(
            "SELECT memory_id, current_revision_id, path FROM documents WHERE path LIKE %s",
            ("%verified-autoswe%",)
        )
        doc = await res.fetchone()
        if doc:
            memory_id = doc["memory_id"]
            active_rev = doc["current_revision_id"]
            logger.info("Found document %s (active revision: %s)", doc["path"], active_rev)

            count_res = await conn.execute(
                "SELECT count(*) FROM document_revisions WHERE memory_id = %s AND revision_id <> %s",
                (memory_id, active_rev),
            )
            total_dead = (await count_res.fetchone())["count"]
            logger.info("Found %d dead revisions for verified-autoswe to prune", total_dead)

            batch_size = 50
            pruned_count = 0
            while True:
                batch_res = await conn.execute(
                    """
                    SELECT revision_id FROM document_revisions
                    WHERE memory_id = %s
                      AND revision_id NOT IN (
                          SELECT current_revision_id FROM documents WHERE current_revision_id IS NOT NULL
                      )
                    LIMIT %s
                    """,
                    (memory_id, batch_size),
                )
                rows = await batch_res.fetchall()
                if not rows:
                    break
                rev_ids = [r["revision_id"] for r in rows]

                await conn.execute("DELETE FROM mentions WHERE revision_id = ANY(%s)", (rev_ids,))
                await conn.execute("DELETE FROM chunks WHERE revision_id = ANY(%s)", (rev_ids,))
                await conn.execute("DELETE FROM vector_outbox WHERE revision_id = ANY(%s)", (rev_ids,))
                await conn.execute("DELETE FROM ingestion_jobs WHERE revision_id = ANY(%s)", (rev_ids,))
                await conn.execute("DELETE FROM document_revisions WHERE revision_id = ANY(%s)", (rev_ids,))

                pruned_count += len(rev_ids)
                if pruned_count % 100 == 0 or pruned_count == total_dead:
                    logger.info("Pruned %d / %d dead revisions...", pruned_count, total_dead)

        logger.info("Pruning any other orphaned staged revisions older than 1 hour...")
        orphan_res = await conn.execute(
            """
            SELECT revision_id FROM document_revisions
            WHERE state = 'staged' AND created_at < now() - interval '1 hour'
              AND revision_id NOT IN (
                  SELECT current_revision_id FROM documents WHERE current_revision_id IS NOT NULL
              )
            LIMIT 500
            """
        )
        orphan_rows = await orphan_res.fetchall()
        if orphan_rows:
            orphan_ids = [r["revision_id"] for r in orphan_rows]
            await conn.execute("DELETE FROM mentions WHERE revision_id = ANY(%s)", (orphan_ids,))
            await conn.execute("DELETE FROM chunks WHERE revision_id = ANY(%s)", (orphan_ids,))
            await conn.execute("DELETE FROM vector_outbox WHERE revision_id = ANY(%s)", (orphan_ids,))
            await conn.execute("DELETE FROM ingestion_jobs WHERE revision_id = ANY(%s)", (orphan_ids,))
            await conn.execute("DELETE FROM document_revisions WHERE revision_id = ANY(%s)", (orphan_ids,))
            logger.info("Pruned %d general orphaned staged revisions", len(orphan_ids))

        await conn.execute(
            "DELETE FROM vector_outbox WHERE status = 'succeeded' AND completed_at < now() - interval '1 day'"
        )

        logger.info("Running VACUUM FULL on chunks, mentions, document_revisions, vector_outbox...")
        await conn.execute("VACUUM FULL chunks;")
        await conn.execute("VACUUM FULL mentions;")
        await conn.execute("VACUUM FULL document_revisions;")
        await conn.execute("VACUUM FULL vector_outbox;")
        await conn.execute("VACUUM FULL ingestion_jobs;")

        final_size = await get_db_size(conn)
        logger.info("Database Vacuum Complete!")
        logger.info("Size Before: %s | Size After: %s", initial_size, final_size)


if __name__ == "__main__":
    asyncio.run(main())
