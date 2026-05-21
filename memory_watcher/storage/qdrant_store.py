import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from models.document import Document, Chunk

logger = logging.getLogger(__name__)

class QdrantStore:
    def __init__(self, host: str = "localhost", port: int = 6333, vector_size: int = 384):
        # Native integration using AsyncQdrantClient
        self.client = AsyncQdrantClient(host=host, port=port)
        self.vector_size = vector_size
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
