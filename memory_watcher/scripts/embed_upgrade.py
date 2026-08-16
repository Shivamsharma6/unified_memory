#!/usr/bin/env python3
"""Zero-downtime embedding model and dimension upgrade tool for UAMS.

This tool:
1. Creates a new Qdrant collection for the target embedding model & dimension.
2. Streams active chunk texts directly from PostgreSQL.
3. Batch-generates new embeddings using the target model.
4. Loads new vectors into the new versioned collection.
5. Atomically switches the active collection alias.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

WATCHER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WATCHER_ROOT))

from embeddings.generator import EmbeddingGenerator
from models.document import Chunk, ChunkMetadata, Document
from storage.postgres_store import PostgresStore
from storage.qdrant_store import QdrantStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("embed_upgrade")


async def upgrade_embeddings(args: argparse.Namespace) -> dict:
    target_dim = args.target_dim
    target_model = args.target_model
    target_provider = args.target_provider or os.getenv("UAMS_EMBED_PROVIDER", "ollama")
    alias_name = args.alias
    collection_name = args.collection_name or f"memory_chunks_v2_{target_dim}"
    batch_size = args.batch_size

    logger.info(
        "Starting embedding upgrade: model=%s provider=%s dim=%d -> collection=%s (alias=%s)",
        target_model,
        target_provider,
        target_dim,
        collection_name,
        alias_name,
    )

    store = PostgresStore()
    await store.open()

    vectors = QdrantStore(vector_size=target_dim)
    embedder = EmbeddingGenerator(provider=target_provider, model_name=target_model)

    start_time = time.monotonic()
    try:
        # Step 1: Create target collection
        logger.info("Initializing target collection: %s", collection_name)
        if not args.dry_run:
            await vectors.create_versioned_collection(collection_name, target_dim)

        # Step 2: Fetch all active chunks from PostgreSQL
        async with store.pool.connection() as connection:
            result = await connection.execute(
                """
                SELECT c.chunk_id, c.content, c.heading_path, c.metadata,
                       d.memory_id, d.memory_type, d.path,
                       r.revision_id, r.project, r.source_agent, r.frontmatter
                FROM chunks c
                JOIN documents d ON d.current_revision_id = c.revision_id
                JOIN document_revisions r ON r.revision_id = d.current_revision_id
                WHERE d.status = 'active' AND r.state = 'active'
                ORDER BY d.memory_id, c.ordinal
                """
            )
            rows = await result.fetchall()

        total_chunks = len(rows)
        logger.info("Found %d active chunks in PostgreSQL to re-embed", total_chunks)

        if total_chunks == 0:
            logger.info("No active chunks found. Upgrading collection alias directly.")
            if not args.dry_run:
                await vectors.switch_active_alias(collection_name, alias_name)
            return {
                "status": "success",
                "chunks_embedded": 0,
                "collection": collection_name,
                "alias": alias_name,
            }

        # Step 3 & 4: Batch embed and upsert into new collection
        processed = 0
        for i in range(0, total_chunks, batch_size):
            batch_rows = rows[i : i + batch_size]
            chunks = []
            for row in batch_rows:
                meta = row["metadata"] or {}
                frontmatter = row["frontmatter"] or {}
                chunks.append(
                    Chunk(
                        content=row["content"],
                        metadata=ChunkMetadata(
                            chunk_id=str(row["chunk_id"]),
                            source_file=row["path"],
                            heading_hierarchy=row["heading_path"] or [],
                            tags=meta.get("tags", []),
                            entities=meta.get("entities", []),
                            timestamps=frontmatter.get("timestamps", {}),
                            semantic_category=row["memory_type"],
                        ),
                    )
                )

            doc = Document(path=batch_rows[0]["path"], raw_content="", chunks=chunks)
            if not args.dry_run:
                embedded_doc = await embedder.embed(doc)
                points = []
                for row, chunk in zip(batch_rows, embedded_doc.chunks):
                    if chunk.embedding is None or len(chunk.embedding) != target_dim:
                        raise ValueError(
                            f"Generated embedding dimension {len(chunk.embedding) if chunk.embedding else None} "
                            f"does not match target dimension {target_dim}"
                        )
                    points.append(
                        {
                            "chunk_id": row["chunk_id"],
                            "vector": chunk.embedding,
                            "payload": {
                                "chunk_id": str(row["chunk_id"]),
                                "memory_id": str(row["memory_id"]),
                                "revision_id": str(row["revision_id"]),
                                "memory_type": row["memory_type"],
                                "project": row["project"],
                                "source_agent": row["source_agent"],
                                "source_file": row["path"],
                                "heading_hierarchy": row["heading_path"] or [],
                                "tags": (row["metadata"] or {}).get("tags", []),
                                "entity_keys": (row["metadata"] or {}).get("entities", []),
                                "timestamps": (row["frontmatter"] or {}).get("timestamps", {}),
                                "text": row["content"],
                            },
                        }
                    )
                # Upsert into specific target collection
                qdrant_points = [
                    models.PointStruct(
                        id=str(p["chunk_id"]),
                        vector=p["vector"],
                        payload=p["payload"],
                    )
                    for p in points
                ]
                from qdrant_client.http import models as qdrant_models
                await vectors.client.upsert(
                    collection_name=collection_name,
                    points=[
                        qdrant_models.PointStruct(
                            id=str(p["chunk_id"]),
                            vector=p["vector"],
                            payload=p["payload"],
                        )
                        for p in points
                    ],
                    wait=True,
                )

            processed += len(batch_rows)
            logger.info("Progress: %d / %d chunks embedded (%.1f%%)", processed, total_chunks, (processed / total_chunks) * 100)

        # Step 5: Atomically swap alias
        if not args.dry_run:
            logger.info("Switching active alias %s -> %s", alias_name, collection_name)
            await vectors.switch_active_alias(collection_name, alias_name)

        elapsed = time.monotonic() - start_time
        logger.info(
            "Embedding upgrade complete in %.2fs! %d chunks re-embedded into %s.",
            elapsed,
            processed,
            collection_name,
        )

        return {
            "status": "success",
            "chunks_embedded": processed,
            "collection": collection_name,
            "alias": alias_name,
            "elapsed_seconds": round(elapsed, 2),
            "target_model": target_model,
            "target_dim": target_dim,
            "target_provider": target_provider,
        }

    finally:
        await store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-model", required=True, help="Target embedding model (e.g. nomic-embed-text)")
    parser.add_argument("--target-dim", type=int, required=True, help="Target vector dimension (e.g. 768)")
    parser.add_argument("--target-provider", default=None, help="Embedding provider (ollama, openai, fastembed)")
    parser.add_argument("--collection-name", default=None, help="Target Qdrant collection name")
    parser.add_argument("--alias", default="memory_chunks_v2", help="Active collection alias")
    parser.add_argument("--batch-size", type=int, default=20, help="Re-embedding batch size")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without creating or swapping")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = asyncio.run(upgrade_embeddings(args))
    print("\n=== Embedding Upgrade Report ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("\nNext step: Update your .env file with:")
    print(f"  UAMS_EMBED_PROVIDER={result.get('target_provider')}")
    print(f"  UAMS_EMBED_MODEL={result.get('target_model')}")
    print(f"  UAMS_EMBED_DIMENSION={result.get('target_dim')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
