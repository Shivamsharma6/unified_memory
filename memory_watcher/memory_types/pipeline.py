"""
Memory Ingestion Pipeline for UAMS.

Processes raw interactions through:
  Conversation/Event -> Summarization -> Emotion extraction ->
  Importance scoring -> Memory classification -> Storage
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from memory_watcher.memory_types.memory_types import MemoryCategory, get_memory_type, get_all_memory_types
from memory_watcher.memory_types.episodic import EpisodicMemory, EmotionalState, ContextData, OutcomeData
from memory_watcher.memory_types.other_types import (
    IdentityMemory, GoalMemory, ReflectionMemory, RelationshipMemory,
)

logger = logging.getLogger(__name__)


class MemoryIngestionPipeline:
    """Processes raw interactions into structured memories."""

    def __init__(self, source: str = "system"):
        self.source = source

    def classify_interaction(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryCategory:
        """Classify an interaction into the appropriate memory category."""
        content_lower = content.lower()
        meta = metadata or {}

        goal_keywords = ["goal", "objective", "target", "milestone", "deadline", "project"]
        if any(kw in content_lower for kw in goal_keywords):
            return MemoryCategory.GOAL

        procedural_keywords = ["how to", "steps", "procedure", "workflow", "process", "instructions"]
        if any(kw in content_lower for kw in procedural_keywords):
            return MemoryCategory.PROCEDURAL

        reflection_keywords = ["learned", "realized", "insight", "pattern", "mistake", "improvement"]
        if any(kw in content_lower for kw in reflection_keywords):
            return MemoryCategory.REFLECTION

        # Relationship checked BEFORE identity (identity has "preference"/"prefers")
        relationship_keywords = ["communication", "style", "person", "dynamic"]
        if any(kw in content_lower for kw in relationship_keywords):
            return MemoryCategory.RELATIONSHIP

        # Identity keywords (includes "preference", "prefers")
        identity_keywords = ["personality", "trait", "preference", "habit", "tendency", "prefers", "values"]
        if any(kw in content_lower for kw in identity_keywords):
            return MemoryCategory.IDENTITY

        return MemoryCategory.EPISODIC

    def summarize(self, content: str, max_length: int = 120) -> str:
        """Create a short, actionable summary."""
        summary = " ".join(content.strip().split())
        if len(summary) > max_length:
            cutoff = summary.rfind(" ", 0, max_length)
            if cutoff == -1:
                cutoff = max_length
            summary = summary[:cutoff].rstrip() + "..."
        return summary

    def extract_emotional_state(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> EmotionalState:
        """Extract emotional state from interaction content."""
        content_lower = content.lower()
        frustration_words = ["frustrated", "annoyed", "stuck", "error", "bug", "fail", "broken", "issue"]
        excitement_words = ["excited", "great", "awesome", "love", "perfect", "works", "success"]
        confidence_words = ["confident", "sure", "certain", "know", "definitely", "clear"]
        stress_words = ["urgent", "pressure", "deadline", "rushed", "tight", "stress"]
        satisfaction_words = ["satisfied", "happy", "pleased", "good", "solved", "resolved"]

        def _score(words):
            count = sum(1 for w in words if w in content_lower)
            return min(1.0, count / max(len(words), 1))

        return EmotionalState(
            frustration=_score(frustration_words),
            excitement=_score(excitement_words),
            confidence=_score(confidence_words),
            stress=_score(stress_words),
            satisfaction=_score(satisfaction_words),
        )

    def score_importance(self, content: str, emotional_state: EmotionalState, metadata: Optional[Dict[str, Any]] = None) -> float:
        """Score memory importance (0.0–1.0)."""
        meta = metadata or {}
        content_lower = content.lower()
        emotional_weight = emotional_state.intensity()

        common_words = {"the", "a", "an", "is", "are", "was", "were", "it", "this", "that"}
        words = set(content.lower().split())
        novel_ratio = len(words - common_words) / max(len(words), 1)
        novelty = min(1.0, novel_ratio * 3)

        goal_keywords = ["goal", "objective", "target", "milestone", "priority", "critical", "important", "must", "need", "require", "deadline", "project", "deliverable", "specification"]
        goal_score = sum(1 for kw in goal_keywords if kw in content_lower)
        goal_relevance = min(1.0, goal_score / max(len(goal_keywords), 1) * 2)

        mention_count = meta.get("mention_count", 0)
        repetition = min(1.0, mention_count / 5.0)

        importance = emotional_weight * 0.3 + novelty * 0.2 + goal_relevance * 0.3 + repetition * 0.2
        return round(min(1.0, max(0.0, importance)), 4)

    def create_episodic_memory(self, content: str, event_type: str = "conversation", metadata: Optional[Dict[str, Any]] = None) -> EpisodicMemory:
        """Create a full episodic memory from raw interaction content."""
        meta = metadata or {}
        summary = self.summarize(content)
        emotional_state = self.extract_emotional_state(content, meta)
        importance = self.score_importance(content, emotional_state, meta)

        context = ContextData(
            platform=meta.get("platform", "unknown"),
            session_id=meta.get("session_id"),
            participants_count=meta.get("participants_count", 0),
            tools_used=meta.get("tools_used", []),
            external_systems=meta.get("external_systems", []),
        )

        outcome = OutcomeData(
            success=meta.get("success"),
            resolution=meta.get("resolution"),
            consequences=meta.get("consequences", []),
            lessons_learned=meta.get("lessons_learned", []),
            follow_up_actions=meta.get("follow_up_actions", []),
        )

        return EpisodicMemory(
            event_type=event_type,
            summary=summary,
            participants=meta.get("participants", []),
            emotional_state=emotional_state,
            importance=importance,
            context=context,
            outcome=outcome,
            source=self.source,
            tags=meta.get("tags", []),
            raw_excerpt=content[:200] if len(content) > 200 else content,
        )

    def create_memory(self, content: str, memory_type: Optional[MemoryCategory] = None, metadata: Optional[Dict[str, Any]] = None):
        """Create the appropriate memory type from raw content."""
        meta = metadata or {}

        if memory_type is None:
            memory_type = self.classify_interaction(content, meta)

        if memory_type == MemoryCategory.EPISODIC:
            return self.create_episodic_memory(content, metadata=meta)

        elif memory_type == MemoryCategory.IDENTITY:
            trait = meta.get("trait", content.split(":")[0].strip() if ":" in content else content[:50])
            value = meta.get("value", content.split(":")[-1].strip() if ":" in content else content)
            return IdentityMemory(
                trait=trait, value=value,
                confidence=meta.get("confidence", 0.5),
                source=self.source,
                tags=meta.get("tags", []),
            )

        elif memory_type == MemoryCategory.GOAL:
            title = meta.get("title", self.summarize(content, 60))
            return GoalMemory(
                title=title, description=content,
                status=meta.get("status", "active"),
                priority=meta.get("priority", 0.5),
                source=self.source,
                tags=meta.get("tags", []),
            )

        elif memory_type == MemoryCategory.REFLECTION:
            insight = meta.get("insight", self.summarize(content, 100))
            return ReflectionMemory(
                insight=insight,
                category=meta.get("category", "insight"),
                confidence=meta.get("confidence", 0.5),
                source=self.source,
                tags=meta.get("tags", []),
            )

        elif memory_type == MemoryCategory.RELATIONSHIP:
            person = meta.get("person", "unknown")
            return RelationshipMemory(
                person=person,
                communication_style=meta.get("communication_style", "unknown"),
                preferences=meta.get("preferences", {}),
                source=self.source,
                tags=meta.get("tags", []),
            )

        else:
            return self.create_episodic_memory(content, metadata=meta)

    def get_collection_for_category(self, category: MemoryCategory) -> str:
        """Get the Qdrant collection name for a memory category."""
        config = get_memory_type(category)
        return config.collection_name

    def get_all_collections(self) -> List[str]:
        """Return all memory collection names."""
        return get_all_memory_types()
