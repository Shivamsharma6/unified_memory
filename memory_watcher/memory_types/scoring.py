"""
Importance Scoring System for UAMS.

Scores memories on a 0.0–1.0 scale based on:
  emotional_intensity * 0.3 + novelty * 0.2 + goal_relevance * 0.3 + repetition * 0.2
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from memory_watcher.memory_types.memory_types import MemoryCategory, get_memory_type
from memory_watcher.memory_types.episodic import EmotionalState

logger = logging.getLogger(__name__)


@dataclass
class ImportanceScore:
    """Result of importance scoring."""
    raw_score: float
    emotional_weight: float
    novelty: float
    goal_relevance: float
    repetition: float
    weighted_score: float
    above_threshold: bool
    category: str = ""

    def __float__(self):
        return self.weighted_score


class ImportanceScorer:
    """Scores memories for long-term survival."""

    WEIGHTS = {"emotional": 0.3, "novelty": 0.2, "goal": 0.3, "repetition": 0.2}
    THRESHOLDS = {
        MemoryCategory.EPISODIC: 0.3,
        MemoryCategory.REFLECTION: 0.4,
        MemoryCategory.GOAL: 0.0,
        MemoryCategory.PROCEDURAL: 0.0,
        MemoryCategory.IDENTITY: 0.0,
        MemoryCategory.RELATIONSHIP: 0.0,
    }
    # Minimum threshold for unclassified memories (generic content)
    MIN_THRESHOLD = 0.25

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        if weights:
            self.WEIGHTS = weights

    def score(self, content: str, emotional_state: Optional[EmotionalState] = None, metadata: Optional[Dict[str, Any]] = None, category: Optional[MemoryCategory] = None) -> ImportanceScore:
        """Calculate importance score for a memory."""
        meta = metadata or {}
        content_lower = content.lower()

        if emotional_state:
            emotional_weight = emotional_state.intensity()
        else:
            emotional_weight = self._keyword_emotional_score(content_lower)

        novelty = self._calculate_novelty(content)
        goal_relevance = self._calculate_goal_relevance(content_lower, meta)
        repetition = self._calculate_repetition(meta)

        weighted_score = (
            emotional_weight * self.WEIGHTS["emotional"] +
            novelty * self.WEIGHTS["novelty"] +
            goal_relevance * self.WEIGHTS["goal"] +
            repetition * self.WEIGHTS["repetition"]
        )
        weighted_score = round(min(1.0, max(0.0, weighted_score)), 4)

        cat = str(category).lower() if category else ""
        threshold = 0.0
        for mem_cat, thresh in self.THRESHOLDS.items():
            if mem_cat.value in cat:
                threshold = thresh
                break

        # Apply minimum threshold for unclassified memories
        if threshold == 0.0 and category is None:
            threshold = self.MIN_THRESHOLD

        above_threshold = weighted_score >= threshold

        return ImportanceScore(
            raw_score=weighted_score,
            emotional_weight=round(emotional_weight, 4),
            novelty=round(novelty, 4),
            goal_relevance=round(goal_relevance, 4),
            repetition=round(repetition, 4),
            weighted_score=weighted_score,
            above_threshold=above_threshold,
            category=cat,
        )

    def _keyword_emotional_score(self, content_lower: str) -> float:
        words = {"frustrated": 0.8, "annoyed": 0.7, "stuck": 0.6, "error": 0.5,
                 "excited": 0.7, "great": 0.6, "awesome": 0.8, "love": 0.9,
                 "confident": 0.6, "sure": 0.5, "certain": 0.6,
                 "urgent": 0.7, "deadline": 0.6, "pressure": 0.8,
                 "satisfied": 0.6, "happy": 0.7, "solved": 0.7, "resolved": 0.6}
        score = sum(words.get(w, 0) for w in words if w in content_lower)
        return min(1.0, score / max(len(words), 1))

    def _calculate_novelty(self, content: str) -> float:
        common_words = {"the", "a", "an", "is", "are", "was", "were", "it", "this", "that", "to", "of", "and", "in", "for", "on", "with", "at", "by", "from", "as", "be", "has", "had", "have", "not", "but", "or", "can", "will", "just", "so", "up", "out", "if", "about"}
        words = set(content.lower().split())
        if not words:
            return 0.0
        novel_words = words - common_words
        return min(1.0, len(novel_words) / max(len(words), 1) * 3)

    def _calculate_goal_relevance(self, content_lower: str, meta: Dict[str, Any]) -> float:
        goal_keywords = ["goal", "objective", "target", "milestone", "priority", "critical", "important", "must", "need", "require", "deadline", "project", "deliverable", "specification"]
        score = sum(1 for kw in goal_keywords if kw in content_lower)
        return min(1.0, score / max(len(goal_keywords), 1) * 2)

    def _calculate_repetition(self, meta: Dict[str, Any]) -> float:
        mention_count = meta.get("mention_count", 0)
        return min(1.0, mention_count / 5.0)

    def should_prune(self, score: ImportanceScore) -> bool:
        """Determine if a memory should be pruned based on its score."""
        return not score.above_threshold

    def get_pruning_threshold(self, category: MemoryCategory) -> float:
        """Get the pruning threshold for a memory category."""
        return self.THRESHOLDS.get(category, 0.0)
