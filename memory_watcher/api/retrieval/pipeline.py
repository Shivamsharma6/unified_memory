import logging
import re
from typing import List, Dict, Any
from api.models import SearchRequest, SearchResult, SearchResponse
from storage.qdrant_store import QdrantStore
from embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    def __init__(self):
        self.vector_store = QdrantStore()
        self.embedder = EmbeddingGenerator()
        # In a full system, these would use an LLM or Graph DB
        self.entity_pattern = re.compile(r'\[\[(.*?)\]\]')

    async def initialize(self):
        await self.vector_store.initialize_collections()
        await self.embedder.initialize()

    async def _step1_understand_query(self, query: str) -> str:
        """1. Query understanding (normalization/expansion)"""
        return query.strip().lower()

    async def _step2_classify_intent(self, query: str) -> str:
        """2. Intent classification (Search vs Procedure vs Recall)"""
        if "how to" in query or "step" in query:
            return "procedural"
        if "summarize" in query:
            return "summary"
        return "semantic"

    async def _step3_extract_entities(self, query: str) -> List[str]:
        """3. Entity extraction"""
        # Simple regex extraction for now; normally would use NER
        return list(set(self.entity_pattern.findall(query)))

    async def _step4_graph_expansion(self, entities: List[str]) -> List[str]:
        """4. Graph expansion (fetch 1-hop neighbors)"""
        # Stub: If 'OpenClaw' is found, expand to 'Hermes' etc.
        expanded = set(entities)
        # Mock expansion
        if "Unified Memory" in expanded:
            expanded.update(["Qdrant", "Obsidian"])
        return list(expanded)

    async def _step5_vector_retrieval(self, query: str, expanded_entities: List[str], intent: str, limit: int) -> List[Any]:
        """5. Vector retrieval (Hybrid search via Qdrant)"""
        # Embed the query
        class MockDoc: chunks = []
        doc = MockDoc()
        from models.document import Chunk, ChunkMetadata
        meta = ChunkMetadata(chunk_id="query", source_file="query")
        doc.chunks = [Chunk(content=query, metadata=meta)]
        doc = await self.embedder.embed(doc)
        query_vector = doc.chunks[0].embedding

        # Determine target collection based on intent
        collection = f"{intent}_memory" if intent in ["semantic", "episodic", "procedural"] else "semantic_memory"
        
        # Hybrid search for each entity + raw vector
        results = []
        # Execute base vector search
        base_results = await self.vector_store.hybrid_search(query_vector, collection, limit=limit)
        results.extend(base_results)

        # In production, we'd dedup and merge scores here.
        return results

    async def _step6_rerank(self, results: List[Any], query: str) -> List[SearchResult]:
        """6. Reranking and 7. Importance Scoring"""
        # Stub for BM25/CrossEncoder reranking
        ranked = []
        for r in results:
            # Qdrant returns ScoredPoint
            score = r.score
            payload = r.payload or {}
            
            # Recalculate score combining vector similarity + recency/importance heuristics
            importance = 1.0 # Mock importance
            final_score = score * importance
            
            ranked.append(SearchResult(
                chunk_id=str(r.id),
                text=payload.get("text", ""),
                score=final_score,
                importance=importance,
                source_file=payload.get("source_file", "unknown"),
                entities=payload.get("entities", [])
            ))
            
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked

    async def _step7_context_compression(self, ranked: List[SearchResult], compress: bool) -> List[SearchResult]:
        """7. Context compression (trim to token budget)"""
        if not compress: return ranked
        # Mock compression: drop results with low scores to save context window
        return [r for r in ranked if r.score > 0.6][:5]

    async def _step8_assemble(self, request: SearchRequest) -> SearchResponse:
        """8. Final context assembly"""
        norm_query = await self._step1_understand_query(request.query)
        intent = await self._step2_classify_intent(norm_query)
        entities = await self._step3_extract_entities(request.query)
        entities.extend(request.entities)
        
        expanded_entities = await self._step4_graph_expansion(entities)
        raw_results = await self._step5_vector_retrieval(norm_query, expanded_entities, intent, request.limit)
        
        ranked_results = await self._step6_rerank(raw_results, norm_query)
        compressed_results = await self._step7_context_compression(ranked_results, request.compress)
        
        # Estimate tokens (rough heuristic: 1 word ~ 1.3 tokens)
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
