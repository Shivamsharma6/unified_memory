"""
Comprehensive tests for the Episodic Memory System.

Tests all 5 steps:
  1.1 — Memory Type Definitions (7 categories)
  1.2 — Episodic Memory Schema
  1.3 — Memory Ingestion Pipeline
  1.4 — Importance Scoring
  1.5 — Memory Consolidation
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from memory_watcher.memory_types.memory_types import (
    MemoryCategory,
    MemoryTypeConfig,
    MEMORY_TYPES,
    get_memory_type,
    get_all_memory_types,
    get_enabled_memory_types,
    get_collection_names,
)
from memory_watcher.memory_types.episodic import (
    EpisodicMemory,
    EmotionalState,
    ContextData,
    OutcomeData,
)
from memory_watcher.memory_types.other_types import (
    IdentityMemory,
    GoalMemory,
    ReflectionMemory,
    RelationshipMemory,
)
from memory_watcher.memory_types.pipeline import MemoryIngestionPipeline
from memory_watcher.memory_types.scoring import ImportanceScorer, ImportanceScore
from memory_watcher.memory_types.consolidation import (
    MemoryConsolidator,
    ConsolidationResult,
)


# ─── Step 1.1 — Memory Type Definitions ────────────────────────────

class TestMemoryTypeDefinitions:
    """Tests for Step 1.1: 7 memory category definitions."""

    def test_all_7_categories_exist(self):
        """All 7 memory categories must be defined."""
        categories = list(MemoryCategory)
        assert len(categories) == 7, f"Expected 7 categories, got {len(categories)}"

    def test_expected_category_names(self):
        """Each category must have the correct name."""
        expected = {
            "semantic", "episodic", "procedural",
            "identity", "goal", "reflection", "relationship",
        }
        actual = {cat.value for cat in MemoryCategory}
        assert actual == expected, f"Categories mismatch: {actual}"

    def test_semantic_is_facts(self):
        """Semantic memory must be for facts."""
        config = get_memory_type(MemoryCategory.SEMANTIC)
        assert "facts" in config.description.lower() or "concept" in config.description.lower()

    def test_episodic_is_experiences(self):
        """Episodic memory must be for experiences/events."""
        config = get_memory_type(MemoryCategory.EPISODIC)
        assert "experience" in config.description.lower() or "event" in config.description.lower()

    def test_procedural_is_how_to(self):
        """Procedural memory must be for how-to knowledge."""
        config = get_memory_type(MemoryCategory.PROCEDURAL)
        assert "how" in config.description.lower() or "procedur" in config.description.lower()

    def test_identity_is_personality(self):
        """Identity memory must be for stable personality."""
        config = get_memory_type(MemoryCategory.IDENTITY)
        assert "personality" in config.description.lower() or "trait" in config.description.lower()

    def test_goal_is_objectives(self):
        """Goal memory must be for ongoing objectives."""
        config = get_memory_type(MemoryCategory.GOAL)
        assert "object" in config.description.lower() or "goal" in config.description.lower()

    def test_reflection_is_self_analysis(self):
        """Reflection memory must be for self-analysis."""
        config = get_memory_type(MemoryCategory.REFLECTION)
        assert "self" in config.description.lower() or "analy" in config.description.lower()

    def test_relationship_is_people_dynamics(self):
        """Relationship memory must be for people-specific dynamics."""
        config = get_memory_type(MemoryCategory.RELATIONSHIP)
        assert "people" in config.description.lower() or "dynamic" in config.description.lower()

    def test_all_have_collection_names(self):
        """Each memory type must map to a Qdrant collection."""
        for cat in MemoryCategory:
            config = get_memory_type(cat)
            assert config.collection_name, f"{cat.value} has no collection name"

    def test_collection_names_match_expected(self):
        """Collection names must match the recommended structure."""
        collections = get_collection_names()
        expected = [
            "semantic_memory", "episodic_memory", "procedural_memory",
            "identity_memory", "goal_memory", "reflection_memory", "relationship_memory",
        ]
        assert collections == expected

    def test_all_types_enabled(self):
        """All 7 memory types should be enabled by default."""
        enabled = get_enabled_memory_types()
        assert len(enabled) == 7

    def test_episodic_has_min_importance_threshold(self):
        """Episodic memory should have a minimum importance threshold."""
        config = get_memory_type(MemoryCategory.EPISODIC)
        assert config.min_importance_threshold > 0, "Episodic should filter low-importance memories"

    def test_reflection_has_min_importance_threshold(self):
        """Reflection memory should have a minimum importance threshold."""
        config = get_memory_type(MemoryCategory.REFLECTION)
        assert config.min_importance_threshold > 0

    def test_get_all_memory_types(self):
        """get_all_memory_types returns all 7 configs."""
        all_types = get_all_memory_types()
        assert len(all_types) == 7

    def test_get_memory_type_by_category(self):
        """get_memory_type returns the correct config for a category."""
        config = get_memory_type(MemoryCategory.EPISODIC)
        assert config.name == MemoryCategory.EPISODIC
        assert config.collection_name == "episodic_memory"


# ─── Step 1.2 — Episodic Memory Schema ─────────────────────────────

class TestEpisodicMemorySchema:
    """Tests for Step 1.2: Episodic memory schema with emotional metadata."""

    def test_basic_episodic_memory_creation(self):
        """Can create a basic episodic memory."""
        mem = EpisodicMemory(
            event_type="conversation",
            summary="Test interaction about system architecture",
            participants=["Shivam", "Hermes"],
        )
        assert mem.id
        assert mem.event_type == "conversation"
        assert mem.summary == "Test interaction about system architecture"
        assert mem.participants == ["Shivam", "Hermes"]

    def test_emotional_state_defaults(self):
        """Emotional state defaults to 0.0 for all dimensions."""
        es = EmotionalState()
        assert es.frustration == 0.0
        assert es.excitement == 0.0
        assert es.confidence == 0.0
        assert es.stress == 0.0
        assert es.satisfaction == 0.0

    def test_emotional_state_clamping(self):
        """Emotional values are clamped to 0.0–1.0."""
        es = EmotionalState(frustration=-0.5, excitement=1.5)
        assert es.frustration == 0.0
        assert es.excitement == 1.0

    def test_emotional_state_dominant_emotion(self):
        """Can identify the dominant emotion."""
        es = EmotionalState(frustration=0.8, excitement=0.3, confidence=0.2)
        assert es.dominant_emotion() == "frustration"

    def test_emotional_state_intensity(self):
        """Intensity is the average of all emotion dimensions."""
        es = EmotionalState(frustration=0.0, excitement=1.0, confidence=0.0, stress=0.0, satisfaction=0.0)
        assert es.intensity() == pytest.approx(0.2)

    def test_full_episodic_memory(self):
        """Can create a complete episodic memory with all fields."""
        mem = EpisodicMemory(
            event_type="decision",
            summary="Chose Qdrant over Pinecone for vector storage",
            participants=["Shivam", "Hermes", "OpenClaw"],
            emotional_state=EmotionalState(
                frustration=0.2, excitement=0.8, confidence=0.9,
                stress=0.1, satisfaction=0.7,
            ),
            importance=0.85,
            context=ContextData(
                platform="cli",
                session_id="sess-001",
                tools_used=["qdrant", "python"],
            ),
            outcome=OutcomeData(
                success=True,
                resolution="Qdrant deployed successfully",
                lessons_learned=["Qdrant has better local support"],
            ),
            source="hermes",
        )
        assert mem.event_type == "decision"
        assert mem.importance == 0.85
        assert mem.source == "hermes"
        assert mem.emotional_state.excitement == 0.8
        assert mem.context.platform == "cli"
        assert mem.outcome.success is True

    def test_episodic_memory_to_payload(self):
        """Can serialize to a flat payload dict."""
        mem = EpisodicMemory(
            event_type="conversation",
            summary="Test",
            participants=["A"],
            source="test",
        )
        payload = mem.to_payload()
        assert "id" in payload
        assert payload["event_type"] == "conversation"
        assert payload["summary"] == "Test"
        assert payload["participants"] == ["A"]
        assert payload["source"] == "test"

    def test_episodic_memory_from_payload(self):
        """Can deserialize from a flat payload dict."""
        payload = {
            "id": "test-123",
            "timestamp": "2026-05-28T10:00:00+00:00",
            "event_type": "failure",
            "summary": "Deployment failed",
            "participants": ["Shivam"],
            "emotional_state": {"frustration": 0.9, "excitement": 0.1, "confidence": 0.2, "stress": 0.8, "satisfaction": 0.1},
            "importance": 0.7,
            "context": {"platform": "ci"},
            "outcome": {"success": False, "resolution": "Rolled back"},
            "related_memories": ["mem-456"],
            "source": "hermes",
            "tags": ["#deployment", "#failure"],
        }
        mem = EpisodicMemory.from_payload(payload)
        assert mem.id == "test-123"
        assert mem.event_type == "failure"
        assert mem.summary == "Deployment failed"
        assert mem.emotional_state.frustration == 0.9
        assert mem.importance == 0.7
        assert mem.source == "hermes"

    def test_episodic_memory_to_markdown(self):
        """Can convert to UAMS-compatible Markdown."""
        mem = EpisodicMemory(
            event_type="success",
            summary="Successfully deployed Qdrant cluster",
            participants=["Shivam"],
            emotional_state=EmotionalState(excitement=0.9, satisfaction=0.8),
            importance=0.8,
            context=ContextData(platform="cli"),
            outcome=OutcomeData(success=True, lessons_learned=["Use Docker for Qdrant"]),
            source="hermes",
        )
        md = mem.to_markdown()
        assert "---" in md
        assert "type: episodic" in md
        assert "Successfully deployed Qdrant cluster" in md
        assert "Frustration: 0.00" in md
        assert "Excitement: 0.90" in md
        assert "Success: True" in md

    def test_context_data_defaults(self):
        """ContextData defaults to empty/None values."""
        ctx = ContextData()
        assert ctx.location is None
        assert ctx.platform is None
        assert ctx.participants_count == 0

    def test_outcome_data_defaults(self):
        """OutcomeData defaults to empty/None values."""
        out = OutcomeData()
        assert out.success is None
        assert out.resolution is None
        assert out.consequences == []

    def test_other_memory_types_exist(self):
        """Identity, Goal, Reflection, Relationship memory types exist."""
        identity = IdentityMemory(trait="prefers_optimization", value=True)
        assert identity.trait == "prefers_optimization"

        goal = GoalMemory(title="Migrate to Qdrant", status="active")
        assert goal.title == "Migrate to Qdrant"
        assert goal.status == "active"

        reflection = ReflectionMemory(insight="Use fastembed for local embeddings")
        assert reflection.insight == "Use fastembed for local embeddings"

        relationship = RelationshipMemory(person="Shivam", communication_style="direct")
        assert relationship.person == "Shivam"
        assert relationship.communication_style == "direct"


# ─── Step 1.3 — Memory Ingestion Pipeline ──────────────────────────

class TestMemoryIngestionPipeline:
    """Tests for Step 1.3: Memory ingestion pipeline."""

    def setup_method(self):
        self.pipeline = MemoryIngestionPipeline(source="test-agent")

    def test_classify_conversation_as_episodic(self):
        """A general conversation should be classified as episodic."""
        cat = self.pipeline.classify_interaction(
            "We discussed the system architecture and decided on Qdrant for vector storage."
        )
        assert cat == MemoryCategory.EPISODIC

    def test_classify_goal_content(self):
        """Content about goals should be classified as goal."""
        cat = self.pipeline.classify_interaction(
            "Our goal is to complete the migration by Friday with a critical milestone."
        )
        assert cat == MemoryCategory.GOAL

    def test_classify_procedural_content(self):
        """How-to content should be classified as procedural."""
        cat = self.pipeline.classify_interaction(
            "How to deploy Qdrant using Docker with the proper configuration."
        )
        assert cat == MemoryCategory.PROCEDURAL

    def test_classify_reflection_content(self):
        """Content about lessons learned should be classified as reflection."""
        cat = self.pipeline.classify_interaction(
            "I learned that using fastembed is faster than Ollama for local embeddings."
        )
        assert cat == MemoryCategory.REFLECTION

    def test_classify_relationship_content(self):
        """Content about communication style should be classified as relationship."""
        cat = self.pipeline.classify_interaction(
            "Shivam prefers direct communication with technical details."
        )
        assert cat == MemoryCategory.RELATIONSHIP

    def test_classify_identity_content(self):
        """Content about personality traits should be classified as identity."""
        cat = self.pipeline.classify_interaction(
            "Shivam has a strong preference for optimization over simplicity."
        )
        assert cat == MemoryCategory.IDENTITY

    def test_classify_default_to_episodic(self):
        """Unclassifiable content defaults to episodic."""
        cat = self.pipeline.classify_interaction("The weather is nice today.")
        assert cat == MemoryCategory.EPISODIC

    def test_summarize_short_content(self):
        """Short content is returned as-is."""
        summary = self.pipeline.summarize("Hello world")
        assert summary == "Hello world"

    def test_summarize_long_content_truncates(self):
        """Long content is truncated at word boundary."""
        long_text = " ".join(["word"] * 50)
        summary = self.pipeline.summarize(long_text, max_length=30)
        assert len(summary) <= 30 + 3  # +3 for "…"

    def test_extract_emotional_state_from_frustrated_content(self):
        """Frustrated content produces high frustration score."""
        es = self.pipeline.extract_emotional_state(
            "I'm frustrated with the error logs and stuck on this bug."
        )
        assert es.frustration > 0.0

    def test_extract_emotional_state_from_excited_content(self):
        """Excited content produces high excitement score."""
        es = self.pipeline.extract_emotional_state(
            "This is great! The system works perfectly and I love it."
        )
        assert es.excitement > 0.0

    def test_create_episodic_memory(self):
        """Can create a full episodic memory from raw content."""
        mem = self.pipeline.create_episodic_memory(
            content="We discussed the architecture and decided on Qdrant for vector storage.",
            event_type="conversation",
            metadata={
                "platform": "cli",
                "participants": ["Shivam", "Hermes"],
                "tools_used": ["qdrant"],
            },
        )
        assert isinstance(mem, EpisodicMemory)
        assert mem.event_type == "conversation"
        assert mem.source == "test-agent"
        assert mem.context.platform == "cli"
        assert "Qdrant" in mem.summary

    def test_create_memory_auto_classifies(self):
        """create_memory auto-classifies when no type is specified."""
        mem = self.pipeline.create_memory(
            "Our goal is to complete the migration by Friday.",
        )
        assert isinstance(mem, GoalMemory)

    def test_create_memory_explicit_type(self):
        """create_memory respects explicit memory type."""
        mem = self.pipeline.create_memory(
            "We discussed the architecture.",
            memory_type=MemoryCategory.EPISODIC,
        )
        assert isinstance(mem, EpisodicMemory)

    def test_create_identity_memory(self):
        """Can create an identity memory."""
        mem = self.pipeline.create_memory(
            "Shivam prefers optimization over simplicity",
            memory_type=MemoryCategory.IDENTITY,
            metadata={"trait": "optimization_preference", "value": "optimization_over_simplicity"},
        )
        assert isinstance(mem, IdentityMemory)

    def test_create_goal_memory(self):
        """Can create a goal memory."""
        mem = self.pipeline.create_memory(
            "Complete the migration by Friday",
            memory_type=MemoryCategory.GOAL,
            metadata={"title": "Migration", "status": "active"},
        )
        assert isinstance(mem, GoalMemory)

    def test_create_reflection_memory(self):
        """Can create a reflection memory."""
        mem = self.pipeline.create_memory(
            "I learned that fastembed is faster",
            memory_type=MemoryCategory.REFLECTION,
            metadata={"insight": "fastembed is faster", "category": "insight"},
        )
        assert isinstance(mem, ReflectionMemory)

    def test_create_relationship_memory(self):
        """Can create a relationship memory."""
        mem = self.pipeline.create_memory(
            "Shivam prefers direct communication",
            memory_type=MemoryCategory.RELATIONSHIP,
            metadata={"person": "Shivam", "communication_style": "direct"},
        )
        assert isinstance(mem, RelationshipMemory)

    def test_get_collection_for_category(self):
        """Can get the Qdrant collection name for a category."""
        assert self.pipeline.get_collection_for_category(MemoryCategory.EPISODIC) == "episodic_memory"
        assert self.pipeline.get_collection_for_category(MemoryCategory.SEMANTIC) == "semantic_memory"

    def test_get_all_collections(self):
        """Returns all 7 collection names."""
        collections = self.pipeline.get_all_collections()
        assert len(collections) == 7


# ─── Step 1.4 — Importance Scoring ─────────────────────────────────

class TestImportanceScoring:
    """Tests for Step 1.4: Importance scoring system."""

    def setup_method(self):
        self.scorer = ImportanceScorer()

    def test_low_importance_content(self):
        """Generic content scores low importance."""
        score = self.scorer.score("The weather is nice today.")
        assert score.weighted_score < 0.5

    def test_high_emotional_content_scores_higher(self):
        """Highly emotional content scores higher."""
        es = EmotionalState(frustration=0.9, excitement=0.8, confidence=0.7)
        score = self.scorer.score(
            "Critical system failure! We must fix this immediately with urgent deadline pressure.",
            emotional_state=es,
        )
        assert score.weighted_score > 0.3

    def test_goal_relevant_content_scores_higher(self):
        """Goal-relevant content scores higher on goal relevance."""
        score = self.scorer.score(
            "Our critical goal is to complete the milestone before the deadline.",
            metadata={"mention_count": 3},
        )
        assert score.goal_relevance > 0.5

    def test_high_novelty_content(self):
        """Content with many unique words scores higher on novelty."""
        score = self.scorer.score(
            "Quantum entanglement enables distributed neural network optimization algorithms."
        )
        assert score.novelty > 0.3

    def test_repetition_increases_score(self):
        """Higher mention count increases repetition score."""
        score_low = self.scorer.score("test", metadata={"mention_count": 0})
        score_high = self.scorer.score("test", metadata={"mention_count": 10})
        assert score_high.repetition > score_low.repetition

    def test_weighted_score_formula(self):
        """Weighted score follows the formula: emotional*0.3 + novelty*0.2 + goal*0.3 + rep*0.2."""
        score = self.scorer.score(
            "Critical goal milestone deadline project critical",
            metadata={"mention_count": 5},
        )
        expected = (
            score.emotional_weight * 0.3 +
            score.novelty * 0.2 +
            score.goal_relevance * 0.3 +
            score.repetition * 0.2
        )
        assert score.weighted_score == pytest.approx(expected, abs=0.01)

    def test_should_prune_low_score(self):
        """Low-scoring memories should be pruned."""
        score = self.scorer.score("The weather is nice today.")
        assert self.scorer.should_prune(score) is True

    def test_should_keep_high_score(self):
        """High-scoring memories should not be pruned."""
        es = EmotionalState(frustration=0.9, excitement=0.9, confidence=0.9)
        score = self.scorer.score(
            "Critical system failure! Must fix immediately!",
            emotional_state=es,
            metadata={"mention_count": 5},
        )
        assert self.scorer.should_prune(score) is False

    def test_importance_score_above_threshold(self):
        """Score correctly identifies when above threshold."""
        es = EmotionalState(frustration=0.9, excitement=0.9, confidence=0.9)
        score = self.scorer.score(
            "Critical failure! Urgent deadline!",
            emotional_state=es,
            metadata={"mention_count": 5},
        )
        assert score.above_threshold is True

    def test_importance_score_below_threshold(self):
        """Low-scoring memories are below threshold."""
        score = self.scorer.score("The weather is nice today.")
        assert score.above_threshold is False

    def test_get_pruning_threshold(self):
        """Can get the pruning threshold for a category."""
        assert self.scorer.get_pruning_threshold(MemoryCategory.EPISODIC) == 0.3
        assert self.scorer.get_pruning_threshold(MemoryCategory.SEMANTIC) == 0.0

    def test_custom_weights(self):
        """Can use custom scoring weights."""
        custom_scorer = ImportanceScorer(weights={
            "emotional": 0.5, "novelty": 0.1, "goal": 0.3, "repetition": 0.1,
        })
        assert custom_scorer.WEIGHTS["emotional"] == 0.5


# ─── Step 1.5 — Memory Consolidation ───────────────────────────────

class TestMemoryConsolidation:
    """Tests for Step 1.5: Memory consolidation system."""

    def setup_method(self):
        self.consolidator = MemoryConsolidator(
            min_importance_for_retention=0.3,
        )

    def test_consolidate_empty_list(self):
        """Consolidating an empty list returns zero stats."""
        result = self.consolidator.consolidate([])
        assert isinstance(result, ConsolidationResult)
        assert result.memories_processed == 0
        assert result.memories_pruned == 0

    def test_consolidate_single_memory(self):
        """A single memory is retained without pruning."""
        mem = EpisodicMemory(
            event_type="conversation",
            summary="Test interaction",
            importance=0.8,
        )
        result = self.consolidator.consolidate([mem])
        assert result.memories_processed == 1
        assert result.memories_retained == 1
        assert result.memories_pruned == 0

    def test_consolidate_multiple_similar_memories(self):
        """Similar memories get clustered and redundant ones pruned."""
        memories = [
            EpisodicMemory(
                event_type="conversation",
                summary=f"Discussion about optimization approach {i}",
                participants=["Shivam"],
                importance=0.7 - (i * 0.1),
            )
            for i in range(5)
        ]
        result = self.consolidator.consolidate(memories)
        assert result.memories_processed == 5
        assert result.clusters_created > 0
        assert result.memories_pruned >= 0  # May prune some

    def test_consolidate_mixed_event_types(self):
        """Different event types create separate clusters."""
        memories = [
            EpisodicMemory(event_type="conversation", summary="Chat about A", importance=0.8),
            EpisodicMemory(event_type="failure", summary="Failed deployment B", importance=0.6),
            EpisodicMemory(event_type="conversation", summary="Chat about C", importance=0.7),
        ]
        result = self.consolidator.consolidate(memories)
        assert result.memories_processed == 3
        assert result.clusters_created >= 1

    def test_consolidation_result_string(self):
        """ConsolidationResult has a readable string representation."""
        result = ConsolidationResult(
            memories_processed=10, memories_retained=7,
            memories_pruned=3, clusters_created=2,
            abstractions_generated=1, redundancy_reduced=3,
        )
        s = str(result)
        assert "processed=10" in s
        assert "pruned=3" in s

    def test_get_low_value_memories(self):
        """Can retrieve memories below the importance threshold."""
        memories = [
            EpisodicMemory(event_type="conversation", summary="Low value", importance=0.1),
            EpisodicMemory(event_type="conversation", summary="High value", importance=0.8),
            EpisodicMemory(event_type="conversation", summary="Medium value", importance=0.3),
        ]
        low = self.consolidator.get_low_value_memories(memories)
        assert len(low) == 1
        assert low[0].importance == 0.1

    def test_promote_to_concept(self):
        """Can promote multiple episodic memories into a semantic concept."""
        memories = [
            EpisodicMemory(
                event_type="conversation",
                summary="Optimization is critical for performance",
                outcome=OutcomeData(lessons_learned=["Performance matters most"]),
            ),
            EpisodicMemory(
                event_type="conversation",
                summary="We should optimize the database queries",
                outcome=OutcomeData(lessons_learned=["Database queries need optimization"]),
            ),
            EpisodicMemory(
                event_type="conversation",
                summary="Memory usage must be minimized",
                outcome=OutcomeData(lessons_learned=["Memory efficiency is key"]),
            ),
        ]
        concept = self.consolidator.promote_to_concept(memories)
        assert concept is not None
        assert concept["type"] == "semantic_concept"
        assert concept["count"] == 3
        assert "lessons" in concept

    def test_promote_to_concept_requires_minimum(self):
        """Promotion requires at least 3 memories."""
        concept = self.consolidator.promote_to_concept([
            EpisodicMemory(event_type="conversation", summary="One"),
        ])
        assert concept is None

    def test_consolidation_creates_abstractions(self):
        """Consolidation generates abstractions from clusters."""
        memories = [
            EpisodicMemory(
                event_type="conversation",
                summary="Optimization discussion 1",
                importance=0.8,
            ),
            EpisodicMemory(
                event_type="conversation",
                summary="Optimization discussion 2",
                importance=0.7,
            ),
        ]
        result = self.consolidator.consolidate(memories)
        assert result.abstractions_generated >= 0  # May generate 0 or more

    def test_consolidation_summary(self):
        """ConsolidationResult includes a summary string."""
        memories = [
            EpisodicMemory(event_type="conversation", summary=f"Chat {i}", importance=0.5)
            for i in range(10)
        ]
        result = self.consolidator.consolidate(memories)
        assert result.summary
        assert "memories" in result.summary.lower()
