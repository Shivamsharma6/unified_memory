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

    async def initialize_collections(self):
        """Automatic collection initialization with versioning/indexing."""
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

    async def upsert_revision(self, points: List[Dict[str, Any]]) -> None:
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
        await self.client.upsert(
            collection_name=self.v2_collection,
            points=qdrant_points,
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

    async def search_v2(
        self,
        query_vector: List[float],
        *,
        limit: int = 20,
        memory_types: List[str] | None = None,
        projects: List[str] | None = None,
        source_agents: List[str] | None = None,
    ) -> List[Any]:
        conditions = []
        for field_name, values in (
            ("memory_type", memory_types),
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
        return await self.client.search(
            collection_name=self.v2_collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

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
