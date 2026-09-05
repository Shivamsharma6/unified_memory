import logging
import os
import re
import json
import networkx as nx
from pathlib import Path
from typing import List, Dict, Any
from api.models import SearchRequest, SearchResult, SearchResponse
from storage.qdrant_store import QdrantStore
from embeddings.generator import EmbeddingGenerator
from api.retrieval.compressor import ContextCompressor
from api.retrieval.reranker import CrossEncoderReranker
from graph.store import KnowledgeGraphStore
from storage.postgres_store import PostgresStore
from api.retrieval.hybrid import HybridRetrieval
from pipelines.reconciliation import Reconciler

logger = logging.getLogger(__name__)

class RetrievalPipeline:
    def __init__(self, control_store=None, vector_store=None, embedder=None):
        self.vector_store = vector_store or QdrantStore()
        self.embedder = embedder or EmbeddingGenerator()
        self.control_store = control_store or PostgresStore()
        self.hybrid = None
        self.reconciler = None
        self._control_open = False
        self.compressor = ContextCompressor(sim_threshold=0.85)
        self.kg_store = KnowledgeGraphStore()
        self.reranker = CrossEncoderReranker()
        self.entity_pattern = re.compile(r'\[\[(.*?)\]\]')
        # Fallback regex for Capitalized entities if wikilinks aren't used in prompt
        self.fallback_entity_pattern = re.compile(r'\b[A-Z][a-zA-Z0-9]+\b')
        self.identity_store = None

    async def initialize(self):
        try:
            await self.vector_store.initialize_collections()
        except Exception as e:
            logger.warning("Vector store unavailable during startup: %s", e)

        from models.memory_record import get_vault_root
        vault_root = get_vault_root()

        try:
            await self.control_store.open()
            self._control_open = True
            await self.control_store.migrate()
            if not await self.control_store.ping():
                raise RuntimeError("PostgreSQL control plane did not answer its readiness query")
            self.hybrid = HybridRetrieval(
                self.control_store,
                self.vector_store,
                self.embedder,
                reranker=self.reranker,
                compressor=self.compressor,
            )
            self.reconciler = Reconciler(vault_root, self.control_store)
        except Exception as error:
            logger.warning("PostgreSQL control plane unavailable; using legacy retrieval: %s", error)
            self.hybrid = None
            self.reconciler = None
        
        # Load the graph database / local JSON
        try:
            candidates = [
                Path("knowledge_graph.json"),
                vault_root / "knowledge_graph.json",
                vault_root / "memory_watcher" / "knowledge_graph.json",
                Path(__file__).resolve().parents[2] / "knowledge_graph.json",
            ]
            loaded = False
            for kg_path in candidates:
                if kg_path.exists():
                    with open(kg_path, "r", encoding="utf-8") as f:
                        self.kg_store.G = nx.node_link_graph(json.load(f))
                        logger.info("Loaded Knowledge Graph from %s for Graph-Aware Retrieval.", kg_path)
                        loaded = True
                        break
            if not loaded:
                logger.warning("Starting with empty Knowledge Graph.")
        except Exception as e:
            logger.warning("Starting with empty Knowledge Graph: %s", e)
        
        try:
            from identity.store import IdentityStore
            from models.memory_record import get_vault_root
            self.identity_store = IdentityStore(str(get_vault_root()))
        except Exception:
            logger.warning("Identity store unavailable for retrieval boosts")


    async def shutdown(self):
        if self._control_open:
            await self.control_store.close()
            self._control_open = False

    def _temporal_boost(self, date_str: str) -> float:
        """Calculate recency boost from a date string with bounded dynamic scaling."""
        if not date_str:
            return 0.0
        try:
            from datetime import datetime, timezone
            if isinstance(date_str, str):
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                dt = date_str
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
            return round(min(0.15, 0.15 * (2.0 ** (-age_days / 14.0))), 4)
        except (ValueError, TypeError, OverflowError):
            return 0.0


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

        collection = "summaries" if intent == "summary" else (
            f"{intent}_memory" if intent in ["semantic", "episodic", "procedural"] else "semantic_memory"
        )
        
        results = []
        seen_ids = set()

        async def add_results(entity_filter: str | None = None):
            matches = await self.vector_store.hybrid_search(
                query_vector,
                collection,
                limit=limit,
                entity_filter=entity_filter,
            )
            for match in matches:
                match_id = match.get("id") if isinstance(match, dict) else getattr(match, "id", None)
                dedupe_key = str(match_id or id(match))
                if dedupe_key in seen_ids:
                    continue
                seen_ids.add(dedupe_key)
                results.append(match)

        await add_results()
        for entity in expanded_entities:
            await add_results(entity)

        return results

    async def _step6_rerank(self, results: List[Any], query_entities: List[str], query: str = "") -> List[SearchResult]:
        """Graph-Aware Reranking using Knowledge Graph edges, enhanced with cross-encoder scoring."""
        ranked = []
        for r in results:
            # Handle both actual Qdrant objects and mocked dicts (for tests)
            if isinstance(r, dict):
                score = r.get('score', 0.5)
                payload = r.get('payload', {})
                r_id = r.get('id', 'mock_id')
            else:
                score = getattr(r, 'score', 0.5)
                payload = getattr(r, 'payload', {}) or {}
                r_id = getattr(r, 'id', 'mock_id')
            
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

            # Identity boost
            identity_boost = 0.0
            if self.identity_store and query:
                try:
                    boosts = self.identity_store.get_retrieval_boosts("default", query)
                    if boosts:
                        identity_boost = sum(boosts.values()) * 0.1
                except Exception:
                    pass

            # Temporal boost
            date_str = payload.get("date", "")
            temporal = self._temporal_boost(date_str)
            raw_importance = float(payload.get("importance") or payload.get("frontmatter", {}).get("importance", 1.0))
            final_importance = (base_importance + graph_boost + identity_boost + temporal) * (0.8 + 0.2 * min(2.0, max(0.5, raw_importance)))
            
            ranked.append(SearchResult(
                chunk_id=str(r_id),
                text=payload.get("text", ""),
                score=score,
                importance=round(final_importance, 4),
                source_file=payload.get("source_file", "unknown"),
                entities=result_entities
            ))


        # Cross-encoder reranking pass
        if query:
            ranked = await self.reranker.rerank(query, ranked)

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
        ranked_results = await self._step6_rerank(raw_results, all_query_entities, query=norm_query)
        ranked_results.sort(key=lambda r: (r.importance, r.score), reverse=True)
        ranked_results = ranked_results[: max(request.limit, 0)]
        
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
        if self.hybrid is not None:
            return await self.hybrid.search(request)
        return await self._step8_assemble(request)
