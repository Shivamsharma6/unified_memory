import logging
import re
import json
import networkx as nx
from typing import List, Dict, Any
from api.models import SearchRequest, SearchResult, SearchResponse
from storage.qdrant_store import QdrantStore
from embeddings.generator import EmbeddingGenerator
from api.retrieval.compressor import ContextCompressor
from graph.store import KnowledgeGraphStore

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    def __init__(self):
        self.vector_store = QdrantStore()
        self.embedder = EmbeddingGenerator()
        self.compressor = ContextCompressor(sim_threshold=0.85)
        self.kg_store = KnowledgeGraphStore()
        self.entity_pattern = re.compile(r'\[\[(.*?)\]\]')
        # Fallback regex for Capitalized entities if wikilinks aren't used in prompt
        self.fallback_entity_pattern = re.compile(r'\b[A-Z][a-zA-Z0-9]+\b')

    async def initialize(self):
        await self.vector_store.initialize_collections()
        await self.embedder.initialize()
        
        # Load the graph database / local JSON
        try:
            with open("knowledge_graph.json", "r") as f:
                self.kg_store.G = nx.node_link_graph(json.load(f))
                logger.info("Loaded Knowledge Graph for Graph-Aware Retrieval.")
        except Exception as e:
            logger.warning("Starting with empty Knowledge Graph.")

    async def _step1_understand_query(self, query: str) -> str:
        return query.strip()

    async def _step2_classify_intent(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["how to", "step", "code", "fix", "debug"]):
            return "procedural"
        if "summarize" in q:
            return "summary"
        return "semantic"

    async def _step3_extract_entities(self, query: str) -> List[str]:
        entities = list(set(self.entity_pattern.findall(query)))
        if not entities:
            # Try fallback extraction for words like EditFailure
            words = self.fallback_entity_pattern.findall(query)
            entities = [w for w in words if w not in ["How", "Why", "What", "When", "The", "A"]]
        return entities

    async def _step4_graph_expansion(self, entities: List[str]) -> List[str]:
        expanded = set(entities)
        for ent in entities:
            # Case-insensitive-ish graph lookup
            matched_node = None
            for node in self.kg_store.G.nodes():
                if str(node).lower() == ent.lower():
                    matched_node = node
                    break
                    
            if matched_node:
                expanded.add(matched_node)
                # Expand to 1-hop neighbors
                neighbors = list(self.kg_store.G.successors(matched_node)) + list(self.kg_store.G.predecessors(matched_node))
                expanded.update(neighbors)
                
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
        # In a real scenario, we might also filter by expanded_entities here
        base_results = await self.vector_store.hybrid_search(query_vector, collection, limit=limit)
        results.extend(base_results)
        return results

    async def _step6_rerank(self, results: List[Any], query_entities: List[str]) -> List[SearchResult]:
        """Graph-Aware Reranking using Knowledge Graph edges."""
        ranked = []
        for r in results:
            # Handle both actual Qdrant objects and mocked dicts (for tests)
            score = r.score if hasattr(r, 'score') else r.get('score', 0.5)
            payload = r.payload if hasattr(r, 'payload') else r.get('payload', {})
            r_id = getattr(r, 'id', r.get('id', 'mock_id'))
            
            base_importance = 1.0 
            result_entities = payload.get("entities", [])
            
            # --- RELATIONSHIP-AWARE RERANKING ---
            graph_boost = 0.0
            
            for q_ent in query_entities:
                q_node = next((n for n in self.kg_store.G.nodes() if str(n).lower() == q_ent.lower()), None)
                if not q_node: continue
                
                for r_ent in result_entities:
                    r_node = next((n for n in self.kg_store.G.nodes() if str(n).lower() == r_ent.lower()), None)
                    if not r_node: continue
                    
                    # Check if the result entity FIXES or is connected to the query entity
                    if self.kg_store.G.has_edge(r_node, q_node):
                        rel = self.kg_store.G[r_node][q_node].get("relation", "")
                        if rel in ["fixes", "resolves"]: graph_boost += 0.4
                        elif rel in ["caused_by"]: graph_boost += 0.25
                        elif rel in ["depends_on"]: graph_boost += 0.15
                        else: graph_boost += 0.1
                        
                    if self.kg_store.G.has_edge(q_node, r_node):
                        rel = self.kg_store.G[q_node][r_node].get("relation", "")
                        if rel in ["fixes", "resolves"]: graph_boost += 0.4
                        elif rel in ["caused_by"]: graph_boost += 0.25
                        elif rel in ["depends_on"]: graph_boost += 0.15
                        else: graph_boost += 0.1

            final_importance = base_importance + graph_boost
            
            ranked.append(SearchResult(
                chunk_id=str(r_id),
                text=payload.get("text", ""),
                score=score,
                importance=final_importance,
                source_file=payload.get("source_file", "unknown"),
                entities=result_entities
            ))
        return ranked

    async def _step7_context_compression(self, ranked: List[SearchResult], compress: bool, request: SearchRequest) -> List[SearchResult]:
        if not compress: return ranked
        profile = "coding" if any(w in request.query.lower() for w in ["code", "fix", "debug", "error", "failure"]) else "research"
        max_tokens = getattr(request, 'max_tokens', 1500)
        return self.compressor.compress(ranked, max_tokens=max_tokens, profile=profile)

    async def _step8_assemble(self, request: SearchRequest) -> SearchResponse:
        norm_query = await self._step1_understand_query(request.query)
        intent = await self._step2_classify_intent(norm_query)
        
        # Extract base entities from query and combine with explicit ones
        extracted_entities = await self._step3_extract_entities(request.query)
        all_query_entities = list(set(extracted_entities + request.entities))
        
        # Expand via Graph
        expanded_entities = await self._step4_graph_expansion(all_query_entities)
        
        raw_results = await self._step5_vector_retrieval(norm_query, expanded_entities, intent, request.limit)
        
        # Graph-Aware Rerank
        ranked_results = await self._step6_rerank(raw_results, all_query_entities)
        
        # Compress
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
