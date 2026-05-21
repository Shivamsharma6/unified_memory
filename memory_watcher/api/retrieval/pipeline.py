import logging
import re
from typing import List, Dict, Any
from api.models import SearchRequest, SearchResult, SearchResponse
from storage.qdrant_store import QdrantStore
from embeddings.generator import EmbeddingGenerator
from api.retrieval.compressor import ContextCompressor

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    def __init__(self):
        self.vector_store = QdrantStore()
        self.embedder = EmbeddingGenerator()
        self.compressor = ContextCompressor(sim_threshold=0.85)
        self.entity_pattern = re.compile(r'\[\[(.*?)\]\]')

    async def initialize(self):
        await self.vector_store.initialize_collections()
        await self.embedder.initialize()

    async def _step1_understand_query(self, query: str) -> str:
        return query.strip().lower()

    async def _step2_classify_intent(self, query: str) -> str:
        if "how to" in query or "step" in query or "code" in query:
            return "procedural"
        if "summarize" in query:
            return "summary"
        return "semantic"

    async def _step3_extract_entities(self, query: str) -> List[str]:
        return list(set(self.entity_pattern.findall(query)))

    async def _step4_graph_expansion(self, entities: List[str]) -> List[str]:
        expanded = set(entities)
        if "Unified Memory" in expanded:
            expanded.update(["Qdrant", "Obsidian"])
        return list(expanded)

    async def _step5_vector_retrieval(self, query: str, expanded_entities: List[str], intent: str, limit: int) -> List[Any]:
        class MockDoc: chunks = []
        doc = MockDoc()
        from models.document import Chunk, ChunkMetadata
        meta = ChunkMetadata(chunk_id="query", source_file="query")
        doc.chunks = [Chunk(content=query, metadata=meta)]
        doc = await self.embedder.embed(doc)
        query_vector = doc.chunks[0].embedding

        collection = f"{intent}_memory" if intent in ["semantic", "episodic", "procedural"] else "semantic_memory"
        
        results = []
        base_results = await self.vector_store.hybrid_search(query_vector, collection, limit=limit)
        results.extend(base_results)
        return results

    async def _step6_rerank(self, results: List[Any], query: str) -> List[SearchResult]:
        ranked = []
        for r in results:
            score = r.score
            payload = r.payload or {}
            importance = 1.0 
            
            ranked.append(SearchResult(
                chunk_id=str(r.id),
                text=payload.get("text", ""),
                score=score,
                importance=importance,
                source_file=payload.get("source_file", "unknown"),
                entities=payload.get("entities", [])
            ))
        return ranked

    async def _step7_context_compression(self, ranked: List[SearchResult], compress: bool, request: SearchRequest) -> List[SearchResult]:
        if not compress: return ranked
        
        # Profile detection based on request or intent
        profile = "research"
        if "code" in request.query or "implement" in request.query:
            profile = "coding"
        
        max_tokens = getattr(request, 'max_tokens', 1500) # Fallback to 1500
        
        return self.compressor.compress(ranked, max_tokens=max_tokens, profile=profile)

    async def _step8_assemble(self, request: SearchRequest) -> SearchResponse:
        norm_query = await self._step1_understand_query(request.query)
        intent = await self._step2_classify_intent(norm_query)
        entities = await self._step3_extract_entities(request.query)
        entities.extend(request.entities)
        
        expanded_entities = await self._step4_graph_expansion(entities)
        raw_results = await self._step5_vector_retrieval(norm_query, expanded_entities, intent, request.limit)
        
        ranked_results = await self._step6_rerank(raw_results, norm_query)
        compressed_results = await self._step7_context_compression(ranked_results, request.compress, request)
        
        tokens = sum(len(r.text.split()) * 1.3 for r in compressed_results)
        
        return SearchResponse(
            query=request.query,
            intent=intent,
            expanded_entities=expanded_entities,
            results=compressed_results,
            context_tokens_used=int(tokens)
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        return await self._step8_assemble(request)
