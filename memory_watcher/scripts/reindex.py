#!/usr/bin/env python3
"""
Re-index vault with new embedding model.

Usage:
    cd memory_watcher && .venv/bin/python scripts/reindex.py

Drops all Qdrant collections and re-ingests every .md file from the vault.
Use when switching embedding models (e.g. fastembed BAAI/bge-small-en-v1.5 → Ollama mxbai-embed-large).
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VAULT_PATH = Path(__file__).resolve().parents[2]


async def drop_collections():
    from qdrant_client import AsyncQdrantClient
    client = AsyncQdrantClient(host="localhost", port=6333)
    collections = ["semantic_memory", "episodic_memory", "procedural_memory", "summaries"]
    for name in collections:
        try:
            exists = await client.collection_exists(name)
            if exists:
                await client.delete_collection(name)
                logger.info(f"Dropped collection: {name}")
        except Exception as e:
            logger.warning(f"Could not drop {name}: {e}")
    logger.info("All collections dropped.")


async def reindex():
    from pipelines.ingestion import IngestionPipeline
    from embeddings.generator import EmbeddingGenerator
    from storage.qdrant_store import QdrantStore

    # Verify embedding model works first
    embedder = EmbeddingGenerator(provider="ollama", model_name="mxbai-embed-large:335m")
    await embedder.initialize()
    test = await embedder._generate_ollama(["test"])
    dim = len(test[0])
    logger.info(f"Embedding model output dim: {dim}")
    assert dim == 1024, f"Expected 1024, got {dim}"

    # Drop old collections
    await drop_collections()

    # Re-initialize with new dimensions
    store = QdrantStore(vector_size=1024)
    await store.initialize_collections()

    # Ingest all vault files
    pipeline = IngestionPipeline()
    pipeline.vector_store = store
    pipeline.embedder = embedder

    md_files = list(VAULT_PATH.rglob("*.md"))
    md_files = [f for f in md_files if not any(part.startswith(".") for part in f.parts)]
    md_files = [f for f in md_files if "memory_watcher" not in f.parts]

    logger.info(f"Found {len(md_files)} markdown files to index")

    success = 0
    failed = 0
    for f in md_files:
        try:
            await pipeline.process_file(str(f))
            success += 1
        except Exception as e:
            logger.error(f"Failed to index {f.name}: {e}")
            failed += 1

    logger.info(f"Re-index complete: {success} success, {failed} failed")


if __name__ == "__main__":
    asyncio.run(reindex())
