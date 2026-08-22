"""Hybrid retrieval over Qdrant semantics and PostgreSQL truth."""

from __future__ import annotations

import asyncio
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from api.models import SearchRequest, SearchResponse, SearchResult
from api.retrieval.compressor import ContextCompressor
from api.retrieval.reranker import CrossEncoderReranker
from graph.extractor import normalize_entity_key
from models.document import Chunk, ChunkMetadata, Document


class HybridRetrieval:
    RRF_CONSTANT = 60

    def __init__(
        self,
        control_store,
        vector_store,
        embedder,
        *,
        reranker=None,
        compressor=None,
    ) -> None:
        self.control_store = control_store
        self.vector_store = vector_store
        self.embedder = embedder
        self.reranker = reranker or CrossEncoderReranker()
        self.compressor = compressor or ContextCompressor(sim_threshold=0.85)
        self.wikilink_pattern = re.compile(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]")

    @staticmethod
    def _intent(query: str) -> str:
        lowered = query.casefold()
        if any(word in lowered for word in ("how to", "step", "code", "fix", "debug")):
            return "procedural"
        if "summarize" in lowered:
            return "summary"
        return "semantic"

    def _entity_keys(self, request: SearchRequest) -> list[str]:
        values = [*self.wikilink_pattern.findall(request.query), *request.entities]
        return list(dict.fromkeys(normalize_entity_key(value) for value in values if value.strip()))

    @staticmethod
    def _memory_types(request: SearchRequest) -> list[str]:
        if request.memory_types:
            return request.memory_types
        aliases = {
            "semantic_memory": "semantic",
            "episodic_memory": "episodic",
            "procedural_memory": "procedural",
            "summaries": "summary",
        }
        return [aliases.get(value, value) for value in request.collections]

    async def _query_vector(self, query: str) -> list[float]:
        document = Document(
            path="query",
            raw_content=query,
            chunks=[
                Chunk(
                    content=query,
                    metadata=ChunkMetadata(chunk_id="query", source_file="query"),
                )
            ],
        )
        embedded = await self.embedder.embed(document)
        vector = embedded.chunks[0].embedding
        if vector is None:
            raise RuntimeError("Embedding provider returned no query vector")
        return vector

    @staticmethod
    def _parts(item: Any) -> tuple[str, float, dict[str, Any]]:
        if isinstance(item, dict):
            payload = item.get("payload", {}) or {}
            item_id = item.get("id") or payload.get("chunk_id")
            score = item.get("rank", item.get("score", 0.0))
        else:
            payload = getattr(item, "payload", {}) or {}
            item_id = getattr(item, "id", None) or payload.get("chunk_id")
            score = getattr(item, "score", 0.0)
        return str(payload.get("chunk_id") or item_id), float(score or 0.0), payload

    @staticmethod
    def _temporal_boost(payload: dict[str, Any]) -> float:
        timestamps = payload.get("timestamps") or {}
        value = (
            timestamps.get("occurred")
            or timestamps.get("updated")
            or timestamps.get("created")
            or payload.get("date")
        )
        if not value:
            return 0.0
        try:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
            return round(min(0.15, 0.15 * math.pow(2.0, -age_days / 14.0)), 4)
        except (TypeError, ValueError, OverflowError):
            return 0.0


    async def search(self, request: SearchRequest) -> SearchResponse:
        candidate_limit = max(request.limit * 4, 20)
        entity_keys = self._entity_keys(request)
        filter_values = {
            "memory_types": self._memory_types(request),
            "projects": request.projects,
            "source_agents": request.source_agents,
            "include_historical": request.include_historical,
            "limit": candidate_limit,
        }

        lexical_task = asyncio.create_task(
            self.control_store.fts_search(request.query, **filter_values)
        )
        graph_task = asyncio.create_task(
            self.control_store.expand_verified_entities(entity_keys, limit=20)
        )
        profile_task = asyncio.create_task(
            self.control_store.profile_memory_boosts(request.query, entity_keys)
        )
        try:
            query_vector = await self._query_vector(request.query)
            semantic = await self.vector_store.search_v2(
                query_vector,
                limit=candidate_limit,
                memory_types=filter_values["memory_types"],
                projects=request.projects,
                source_agents=request.source_agents,
            )
        except Exception:
            semantic = []
        lexical, expansion, profile_boosts = await asyncio.gather(
            lexical_task,
            graph_task,
            profile_task,
            return_exceptions=True,
        )
        if isinstance(lexical, Exception):
            raise lexical
        if isinstance(expansion, Exception):
            expansion = {}
        if isinstance(profile_boosts, Exception):
            profile_boosts = {}

        combined: dict[str, dict[str, Any]] = {}
        for source, items in (("semantic", semantic), ("lexical", lexical)):
            for rank, item in enumerate(items, start=1):
                chunk_id, raw_score, payload = self._parts(item)
                if not chunk_id or not payload.get("memory_id") or not payload.get("revision_id"):
                    continue
                aggregate = combined.setdefault(
                    chunk_id,
                    {
                        "chunk_id": chunk_id,
                        "payload": payload,
                        "sources": {},
                        "raw_scores": {},
                        "rrf": 0.0,
                    },
                )
                aggregate["sources"][source] = min(
                    rank,
                    aggregate["sources"].get(source, rank),
                )
                aggregate["raw_scores"][source] = max(
                    raw_score,
                    aggregate["raw_scores"].get(source, 0.0),
                )
                aggregate["rrf"] += 1.0 / (self.RRF_CONSTANT + rank)

        memory_ids = {
            uuid.UUID(item["payload"]["memory_id"])
            for item in combined.values()
        }
        valid_pairs = await self.control_store.valid_revision_pairs(
            memory_ids,
            include_historical=request.include_historical,
        )
        combined = {
            chunk_id: item
            for chunk_id, item in combined.items()
            if (
                uuid.UUID(item["payload"]["memory_id"]),
                uuid.UUID(item["payload"]["revision_id"]),
            )
            in valid_pairs
        }

        maximum_rrf = max((item["rrf"] for item in combined.values()), default=1.0)
        scored: list[tuple[SearchResult, float]] = []
        for item in combined.values():
            payload = item["payload"]
            ranks = item["sources"].values()
            rank_quality = max((1.0 / rank for rank in ranks), default=0.0)
            semantic_score = max(0.0, min(1.0, item["raw_scores"].get("semantic", 0.0)))
            lexical_score = max(0.0, min(1.0, item["raw_scores"].get("lexical", 0.0)))
            raw_relevance = max(semantic_score, 0.5 if "lexical" in item["sources"] else 0.0, lexical_score)
            rrf_normalized = item["rrf"] / maximum_rrf
            base_score = (
                0.55 * rank_quality
                + 0.20 * raw_relevance
                + 0.10 * (len(item["sources"]) / 2.0)
                + 0.15 * rrf_normalized
            )

            result_entity_keys = set(payload.get("entity_keys") or payload.get("entities") or [])
            graph_boost = min(
                0.10,
                max((float(expansion.get(key, 0.0)) for key in result_entity_keys), default=0.0),
            )
            memory_id = uuid.UUID(payload["memory_id"])
            profile_boost = min(
                0.10,
                float(profile_boosts.get(memory_id, profile_boosts.get(str(memory_id), 0.0))),
            )
            memory_importance = float(payload.get("importance") or payload.get("frontmatter", {}).get("importance", 1.0))
            importance_boost = min(0.10, 0.05 * (memory_importance - 1.0)) if memory_importance != 1.0 else 0.0
            temporal_boost = self._temporal_boost(payload)
            total_boost = graph_boost + profile_boost + temporal_boost + importance_boost
            initial_score = min(1.0, base_score + total_boost)
            revision_id = str(payload["revision_id"])
            evidence_id = f"{memory_id}:{revision_id}:{item['chunk_id']}"
            scored.append(
                (
                    SearchResult(
                        chunk_id=item["chunk_id"],
                        text=payload.get("text", ""),
                        score=initial_score,
                        importance=round(min(1.25, memory_importance + graph_boost + profile_boost + temporal_boost), 4),

                        source_file=payload.get("source_file", "unknown"),
                        entities=sorted(result_entity_keys),
                        memory_id=str(memory_id),
                        revision_id=revision_id,
                        memory_type=payload.get("memory_type"),
                        rank_sources=sorted(item["sources"]),
                        evidence_ids=[evidence_id],
                    ),
                    item["rrf"],
                )
            )

        if scored:
            rerank_scores = await self.reranker.score(
                [(request.query, result.text) for result, _ in scored]
            )
            for (result, _), rerank_score in zip(scored, rerank_scores):
                bounded_rerank = max(0.0, min(1.0, float(rerank_score)))
                result.score = min(1.0, result.score * 0.8 + bounded_rerank * 0.2)

        scored.sort(key=lambda value: (value[0].score, value[1]), reverse=True)
        results = [
            result for result, _ in scored if result.score >= request.min_score
        ][: max(request.limit, 0)]
        if request.compress:
            profile = (
                "coding"
                if any(word in request.query.casefold() for word in ("code", "fix", "debug", "error"))
                else "research"
            )
            results = self.compressor.compress(
                results,
                max_tokens=request.max_tokens,
                profile=profile,
            )
        tokens = int(sum(len(result.text.split()) * 1.3 for result in results))
        return SearchResponse(
            query=request.query,
            intent=self._intent(request.query),
            expanded_entities=sorted(set(entity_keys) | set(expansion)),
            results=results,
            context_tokens_used=tokens,
        )
