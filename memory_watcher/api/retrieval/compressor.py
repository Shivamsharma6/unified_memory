import logging
import re
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher
from api.models import SearchResult

logger = logging.getLogger(__name__)

class ContextCompressor:
    """
    Intelligent context compression engine to maximize RAG token efficiency.
    """
    def __init__(self, sim_threshold: float = 0.8):
        self.sim_threshold = sim_threshold

    def _estimate_tokens(self, text: str) -> int:
        # Rough heuristic: 1 word ~ 1.3 tokens
        return int(len(text.split()) * 1.3)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Fast string similarity for semantic deduplication without re-embedding."""
        return SequenceMatcher(None, text1, text2).ratio()

    def _score_importance(self, result: SearchResult, profile: str) -> float:
        """
        Dynamically score chunk importance based on the target agent profile.
        """
        base_score = result.score
        
        # Heuristics
        has_code = "```" in result.text
        entity_density = min(len(result.entities) / 5.0, 1.0)
        is_episodic = "episodic" in result.source_file.lower()
        
        if profile == "coding":
            # Coding agents need code blocks and exact procedures
            code_boost = 0.3 if has_code else 0.0
            return base_score * 0.5 + code_boost + (result.importance * 0.2)
            
        elif profile == "research":
            # Research agents need entity-dense semantic information
            return base_score * 0.5 + (entity_density * 0.3) + (result.importance * 0.2)
            
        elif profile == "conversational":
            # Conversational agents need recent episodic history
            episodic_boost = 0.3 if is_episodic else 0.0
            return base_score * 0.5 + episodic_boost + (result.importance * 0.2)
            
        return base_score # Default fallback

    def _semantic_deduplication(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove highly redundant chunks while preserving full provenance and evidence IDs."""
        deduped = []
        for res in results:
            is_duplicate = False
            for existing in deduped:
                if self._text_similarity(res.text, existing.text) > self.sim_threshold:
                    is_duplicate = True
                    # Merge entities, evidence_ids, and rank_sources into the existing result
                    existing.entities = list(dict.fromkeys(existing.entities + res.entities))
                    existing.evidence_ids = list(dict.fromkeys(existing.evidence_ids + res.evidence_ids))
                    existing.rank_sources = list(dict.fromkeys(existing.rank_sources + res.rank_sources))
                    break
            if not is_duplicate:
                deduped.append(
                    SearchResult(
                        chunk_id=res.chunk_id,
                        text=res.text,
                        score=res.score,
                        importance=res.importance,
                        source_file=res.source_file,
                        entities=list(res.entities),
                        memory_id=res.memory_id,
                        revision_id=res.revision_id,
                        memory_type=res.memory_type,
                        rank_sources=list(res.rank_sources),
                        evidence_ids=list(res.evidence_ids),
                    )
                )
        return deduped

    def _hierarchical_summarization(self, text: str, max_chunk_tokens: int) -> str:
        """Extractive summarization for excessively long histories."""
        tokens = self._estimate_tokens(text)
        if tokens <= max_chunk_tokens:
            return text

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if len(sentences) <= 4:
            return text

        summary = " ".join(sentences[:2]) + "\n... [Content Compressed] ...\n" + " ".join(sentences[-2:])
        return summary

    def compress(self, results: List[SearchResult], max_tokens: int = 2000, profile: str = "research") -> List[SearchResult]:
        """
        Main compression pipeline.
        1. Semantic deduplication preserving reranker order and evidence IDs
        2. Greedy knapsack packing within max_tokens
        """
        if not results:
            return []

        unique_results = self._semantic_deduplication(results)
        final_results = []
        current_tokens = 0

        for r in unique_results:
            chunk_tokens = self._estimate_tokens(r.text)
            if current_tokens + chunk_tokens <= max_tokens:
                final_results.append(r)
                current_tokens += chunk_tokens
            else:
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens >= 40 and chunk_tokens > remaining_tokens:
                    summarized_text = self._hierarchical_summarization(r.text, remaining_tokens)
                    if self._estimate_tokens(summarized_text) <= remaining_tokens:
                        r.text = summarized_text
                        final_results.append(r)
                        current_tokens += self._estimate_tokens(summarized_text)
                # Continue checking subsequent chunks
                continue

        return final_results

