#!/usr/bin/env python3
"""
Re-index vault with versioned collection and authoritative control plane.

Usage:
    cd memory_watcher && .venv/bin/python scripts/reindex.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.postgres_store import PostgresStore
from storage.qdrant_store import QdrantStore
from embeddings.generator import EmbeddingGenerator
from pipelines.reconciliation import Reconciler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reindex_v2")

VAULT_PATH = Path(__file__).resolve().parents[2]


async def reindex():
    logger.info("Initializing Postgres control plane and Qdrant store...")
    control_store = PostgresStore()
    await control_store.open()
    await control_store.migrate()

    vector_store = QdrantStore()
    await vector_store.initialize_v2_collection()

    embedder = EmbeddingGenerator()
    await embedder.initialize()

    reconciler = Reconciler(vault_root=VAULT_PATH, store=control_store)
    logger.info("Starting complete reconciliation scan...")
    report = await reconciler.scan(force=True)

    logger.info(
        "Reconciliation scan finished: discovered=%d staged=%d unchanged=%d archived=%d deleted=%d failed=%d",
        report.discovered,
        report.staged,
        report.unchanged,
        report.archived,
        report.deleted,
        report.failed,
    )

    try:
        from scripts.force_graph_rebuild import rebuild_graph
        logger.info("Rebuilding knowledge graph JSON and interactive visualization...")
        await rebuild_graph()
    except Exception as e:
        logger.warning("Knowledge graph rebuild skipped/failed: %s", e)

    await control_store.close()
    await vector_store.close()


if __name__ == "__main__":
    asyncio.run(reindex())
