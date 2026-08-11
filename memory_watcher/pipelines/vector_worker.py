"""Durable PostgreSQL-outbox delivery into Qdrant."""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from embeddings.generator import EmbeddingGenerator
from models.document import Chunk, ChunkMetadata, Document
from storage.qdrant_store import QdrantStore


logger = logging.getLogger(__name__)


class VectorWorker:
    def __init__(
        self,
        control_store,
        vector_store=None,
        embedder=None,
        *,
        worker_id: str | None = None,
        batch_size: int = 10,
        poll_interval: float = 1.0,
    ) -> None:
        self.control_store = control_store
        self.vector_store = vector_store or QdrantStore(
            vector_size=int(os.getenv("UAMS_EMBED_DIMENSION", "1024"))
        )
        self.embedder = embedder or EmbeddingGenerator()
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.batch_size = batch_size
        self.poll_interval = poll_interval

    async def initialize(self) -> None:
        await self.vector_store.initialize_v2_collection()

    async def _points_for_revision(self, revision_id):
        rows = await self.control_store.load_revision_chunks(revision_id)
        if not rows:
            return []
        chunks = []
        for row in rows:
            payload = row["payload"]
            chunks.append(
                Chunk(
                    content=row["text"],
                    metadata=ChunkMetadata(
                        chunk_id=str(row["chunk_id"]),
                        source_file=payload.get("source_file", ""),
                        heading_hierarchy=payload.get("heading_hierarchy", []),
                        tags=payload.get("tags", []),
                        entities=payload.get("entity_keys", []),
                        timestamps=payload.get("timestamps", {}),
                        semantic_category=payload.get("memory_type"),
                    ),
                )
            )
        document = await self.embedder.embed(
            Document(path=chunks[0].metadata.source_file, raw_content="", chunks=chunks)
        )
        points = []
        for row, chunk in zip(rows, document.chunks):
            if chunk.embedding is None:
                raise RuntimeError(f"Embedding missing for chunk {row['chunk_id']}")
            points.append(
                {
                    "chunk_id": row["chunk_id"],
                    "vector": chunk.embedding,
                    "payload": row["payload"],
                }
            )
        return points

    async def _process(self, command) -> None:
        if command.command == "upsert_revision":
            if command.revision_id is None:
                raise ValueError("upsert_revision command has no revision_id")
            points = await self._points_for_revision(command.revision_id)
            await self.vector_store.upsert_revision(points)
            await self.control_store.acknowledge_vector_upsert(command)
            return
        if command.command == "delete_revision":
            if command.revision_id is None:
                raise ValueError("delete_revision command has no revision_id")
            await self.vector_store.delete_revision(command.memory_id, command.revision_id)
            await self.control_store.complete_vector_command(command)
            return
        if command.command == "delete_memory":
            await self.vector_store.delete_memory(command.memory_id)
            await self.control_store.complete_vector_command(command)
            return
        raise ValueError(f"Unsupported vector outbox command: {command.command}")

    async def run_once(self) -> int:
        commands = await self.control_store.claim_vector_outbox(
            self.worker_id,
            self.batch_size,
        )
        for command in commands:
            try:
                await self._process(command)
            except Exception as error:
                logger.error("Vector command %s failed: %s", command.outbox_id, error)
                await self.control_store.fail_vector_command(command, error)
        return len(commands)

    async def run_forever(self) -> None:
        while True:
            try:
                processed = await self.run_once()
                if not processed:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.error("Vector worker poll failed: %s", error)
                await asyncio.sleep(self.poll_interval)
