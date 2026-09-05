import asyncio
import uuid
import hashlib
import logging
import os
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from models.document import Document, Chunk

logger = logging.getLogger(__name__)

class QdrantStore:
    def __init__(
        self,
        host: str = None,
        port: int = None,
        vector_size: int = 1024,
        client=None,
    ):
        # Native integration using AsyncQdrantClient
        host = host or os.getenv("QDRANT_HOST", "127.0.0.1")
        port = port or int(os.getenv("QDRANT_HTTP_PORT", "6333"))
        self.client = client or AsyncQdrantClient(host=host, port=port)
        self.vector_size = vector_size
        self.v2_collection = "memory_chunks_v2"
        self.collections = [
            "semantic_memory",
            "episodic_memory",
            "procedural_memory",
            "summaries"
        ]

    def _make_uuid(self, chunk_id: str) -> str:
        """Qdrant requires UUID or integer IDs. Convert string ID to valid UUID."""
        return str(uuid.UUID(hex=hashlib.md5(chunk_id.encode()).hexdigest()))

    async def warmup(self) -> bool:
        """Warm up the Qdrant connection pool."""
        try:
            await self.client.get_collections()
            return True
        except Exception as e:
            logger.debug("Qdrant pool warmup attempt failed: %s", e)
            return False

    async def initialize_collections(self):
        """Automatic collection initialization with versioning/indexing and transient retry."""
        for attempt in range(1, 4):
            try:
                for col_name in self.collections:
                    exists = await self.client.collection_exists(col_name)
                    if not exists:
                        logger.info(f"Initializing collection: {col_name}")
                        await self.client.create_collection(
                            collection_name=col_name,
                            vectors_config=models.VectorParams(
                                size=self.vector_size, 
                                distance=models.Distance.COSINE
                            )
                        )
                        
                        # Setup payload indexes for metadata filtering
                        await self.client.create_payload_index(
                            collection_name=col_name,
                            field_name="source_file",
                            field_schema=models.PayloadSchemaType.KEYWORD
                        )
                        await self.client.create_payload_index(
                            collection_name=col_name,
                            field_name="entities",
                            field_schema=models.PayloadSchemaType.KEYWORD
                        )
                await self.initialize_v2_collection()
                return
            except Exception as exc:
                err_str = str(exc).casefold()
                is_transient = (
                    "connect" in err_str
                    or "connection" in err_str
                    or "timeout" in err_str
                    or "responsehandlingexception" in type(exc).__name__.casefold()
                    or isinstance(exc, (ConnectionError, OSError))
                )
                if is_transient and attempt < 3:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.info(
                        "Transient Qdrant connection error during collection init (attempt %d); retrying in %.2fs: %s",
                        attempt,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

    async def initialize_v2_collection(self):
        exists = await self.client.collection_exists(self.v2_collection)
        if not exists:
            logger.info("Initializing collection: %s", self.v2_collection)
            await self.client.create_collection(
                collection_name=self.v2_collection,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        for field_name in (
            "memory_id",
            "revision_id",
            "memory_type",
            "project",
            "source_agent",
            "entity_keys",
        ):
            await self.client.create_payload_index(
                collection_name=self.v2_collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def upsert_revision(self, points: List[Dict[str, Any]], batch_size: int = 64) -> None:
        if not points:
            return
        qdrant_points = []
        for point in points:
            vector = point["vector"]
            if len(vector) != self.vector_size:
                raise ValueError(
                    f"Embedding dimension {len(vector)} does not match Qdrant size {self.vector_size}"
                )
            qdrant_points.append(
                models.PointStruct(
                    id=str(point["chunk_id"]),
                    vector=vector,
                    payload=point["payload"],
                )
            )
        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i : i + batch_size]
            await self.client.upsert(
                collection_name=self.v2_collection,
                points=batch,
                wait=True,
            )

    async def delete_revision(self, memory_id: uuid.UUID, revision_id: uuid.UUID) -> None:
        await self.client.delete(
            collection_name=self.v2_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="memory_id",
                            match=models.MatchValue(value=str(memory_id)),
                        ),
                        models.FieldCondition(
                            key="revision_id",
                            match=models.MatchValue(value=str(revision_id)),
                        ),
                    ]
                )
            ),
            wait=True,
        )

    async def create_versioned_collection(self, collection_name: str, vector_size: int) -> None:
        """Create a new versioned vector collection with required payload indices."""
        exists = await self.client.collection_exists(collection_name)
        if not exists:
            logger.info("Creating versioned collection: %s (dim=%d)", collection_name, vector_size)
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        for field_name in (
            "memory_id",
            "revision_id",
            "memory_type",
            "project",
            "source_agent",
            "entity_keys",
        ):
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def switch_active_alias(self, target_collection: str, alias_name: str = "memory_chunks_v2") -> None:
        """Atomically point alias_name to target_collection."""
        await self.client.update_collection_aliases(
            change_aliases_operations=[
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(
                        collection_name=target_collection,
                        alias_name=alias_name,
                    )
                )
            ]
        )
        logger.info("Switched alias %s -> %s", alias_name, target_collection)

    async def close(self) -> None:
        """Close Qdrant client connection."""
        if hasattr(self.client, "close"):
            await self.client.close()

    async def delete_orphaned_points(self, point_ids: Optional[List[str | uuid.UUID]] = None) -> int:
        """Delete a batch of specific point IDs from the vector collection, or prune corrupted orphan points."""
        if point_ids is not None:
            if not point_ids:
                return 0
            str_ids = [str(pid) for pid in point_ids]
            await self.client.delete(
                collection_name=self.v2_collection,
                points_selector=models.PointIdsList(points=str_ids),
                wait=True,
            )
            return len(str_ids)

        # Self-healing scan: find points without valid memory_id or revision_id
        orphans = []
        offset = None
        while True:
            records, offset = await self.client.scroll(
                collection_name=self.v2_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                if not payload.get("memory_id") or not payload.get("revision_id"):
                    orphans.append(str(record.id))
            if offset is None:
                break

        if orphans:
            for i in range(0, len(orphans), 100):
                batch = orphans[i : i + 100]
                await self.client.delete(
                    collection_name=self.v2_collection,
                    points_selector=models.PointIdsList(points=batch),
                    wait=True,
                )
        return len(orphans)

    async def delete_memory(self, memory_id: uuid.UUID) -> None:
        await self.client.delete(
            collection_name=self.v2_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="memory_id",
                            match=models.MatchValue(value=str(memory_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def upsert_v2(self, chunks: List[Chunk], batch_size: int = 64) -> None:
        """Directly upsert chunk embeddings into v2 collection in batches."""
        if not chunks:
            return
        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            meta = chunk.metadata
            chunk_id = getattr(meta, "chunk_id", None) or str(uuid.uuid4())
            point_id = self._make_uuid(str(chunk_id))
            payload = {
                "chunk_id": str(chunk_id),
                "source_file": getattr(meta, "source_file", ""),
                "heading_hierarchy": getattr(meta, "heading_hierarchy", []),
                "tags": getattr(meta, "tags", []),
                "entity_keys": getattr(meta, "entities", []),
                "timestamps": getattr(meta, "timestamps", {}),
                "memory_type": getattr(meta, "semantic_category", None) or getattr(meta, "memory_type", None),
                "memory_id": str(getattr(meta, "memory_id", "")) if getattr(meta, "memory_id", None) else None,
                "revision_id": str(getattr(meta, "revision_id", "")) if getattr(meta, "revision_id", None) else None,
                "project": getattr(meta, "project", None),
                "source_agent": getattr(meta, "source_agent", None),
                "text": chunk.content,
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=chunk.embedding,
                    payload=payload,
                )
            )
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self.client.upsert(
                collection_name=self.v2_collection,
                points=batch,
                wait=True,
            )

    async def search_v2(
        self,
        query_vector: List[float],
        *,
        limit: int = 20,
        memory_types: List[str] | None = None,
        tags: List[str] | None = None,
        projects: List[str] | None = None,
        source_agents: List[str] | None = None,
    ) -> List[Any]:
        conditions = []
        for field_name, values in (
            ("memory_type", memory_types),
            ("tags", tags),
            ("project", projects),
            ("source_agent", source_agents),
        ):
            if values:
                conditions.append(
                    models.FieldCondition(
                        key=field_name,
                        match=models.MatchAny(any=list(values)),
                    )
                )
        query_filter = models.Filter(must=conditions) if conditions else None

        last_error = None
        for attempt in range(1, 4):
            try:
                return await self.client.search(
                    collection_name=self.v2_collection,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
            except Exception as exc:
                last_error = exc
                err_str = str(exc).casefold()
                is_transient = (
                    "connect" in err_str
                    or "connection" in err_str
                    or "timeout" in err_str
                    or "retryerror" in type(exc).__name__.casefold()
                    or "responsehandlingexception" in type(exc).__name__.casefold()
                    or isinstance(exc, (ConnectionError, OSError))
                )
                if is_transient and attempt < 3:
                    backoff = 0.2 * (2 ** (attempt - 1))
                    logger.info(
                        "Transient Qdrant search_v2 connection error on attempt %d; retrying in %.2fs: %s",
                        attempt,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise
        if last_error:
            raise last_error


    async def readiness_probe(self, query_vector: List[float]) -> Dict[str, Any]:
        collection = await self.client.get_collection(self.v2_collection)
        expected_size = collection.config.params.vectors.size
        if len(query_vector) != expected_size:
            raise ValueError(
                f"Probe embedding dimension {len(query_vector)} does not match {expected_size}"
            )
        results = await self.search_v2(query_vector, limit=1)
        return {
            "collection": self.v2_collection,
            "vector_size": expected_size,
            "result_count": len(results),
        }

    async def projection_state(self) -> Dict[str, Any]:
        pairs = set()
        point_ids = set()
        points = 0
        offset = None
        while True:
            records, offset = await self.client.scroll(
                collection_name=self.v2_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            points += len(records)
            for record in records:
                try:
                    point_ids.add(uuid.UUID(str(record.id)))
                except (TypeError, ValueError):
                    pass
                payload = record.payload or {}
                try:
                    pairs.add(
                        (
                            uuid.UUID(str(payload["memory_id"])),
                            uuid.UUID(str(payload["revision_id"])),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if offset is None:
                break
        return {"pairs": pairs, "point_ids": point_ids, "points": points}

    def _determine_collection(self, category: Optional[str]) -> str:
        cat = str(category).lower() if category else ""
        if "semantic" in cat: return "semantic_memory"
        if "episodic" in cat: return "episodic_memory"
        if "procedural" in cat: return "procedural_memory"
        if "summary" in cat: return "summaries"
        return "semantic_memory" # Fallback

    async def store_batch(self, doc: Document) -> None:
        """Batch embedding writes asynchronously."""
        points_by_collection = {c: [] for c in self.collections}
        
        for chunk in doc.chunks:
            if not chunk.embedding:
                # Mock embedding for test if missing
                chunk.embedding = [0.0] * self.vector_size
                
            collection = self._determine_collection(chunk.metadata.semantic_category)
            
            payload = {
                "source_file": chunk.metadata.source_file,
                "heading_hierarchy": chunk.metadata.heading_hierarchy,
                "text": chunk.content,
                "tags": chunk.metadata.tags,
                "entities": chunk.metadata.entities,
                "timestamps": chunk.metadata.timestamps,
                "relationships": chunk.metadata.backlinks
            }
            
            point = models.PointStruct(
                id=self._make_uuid(chunk.metadata.chunk_id),
                vector=chunk.embedding,
                payload=payload
            )
            points_by_collection[collection].append(point)

        # Execute batch upserts
        for col, points in points_by_collection.items():
            if points:
                await self.client.upsert(
                    collection_name=col,
                    points=points
                )
                logger.info(f"Upserted {len(points)} chunks into {col}")

    async def hybrid_search(self, query_vector: List[float], collection: str, limit: int = 5, entity_filter: str = None) -> List[Any]:
        """Hybrid search support with metadata filtering."""
        query_filter = None
        if entity_filter:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="entities",
                        match=models.MatchValue(value=entity_filter)
                    )
                ]
            )
            
        search_result = await self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        return search_result
