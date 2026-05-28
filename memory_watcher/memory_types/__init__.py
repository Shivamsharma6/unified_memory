"""
Memory Types Package for UAMS.

Provides 7 memory categories with schemas, ingestion pipeline,
importance scoring, and consolidation system.

Categories:
  semantic      - facts and concepts
  episodic      - experiences and events (with emotional metadata)
  procedural    - how-to knowledge
  identity      - stable personality traits
  goal          - ongoing objectives
  reflection    - self-analysis and learning
  relationship  - people-specific dynamics
"""

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

from memory_watcher.memory_types.consolidation import MemoryConsolidator, ConsolidationResult

__all__ = [
    # Memory types
    "MemoryCategory", "MemoryTypeConfig", "MEMORY_TYPES",
    "get_memory_type", "get_all_memory_types",
    "get_enabled_memory_types", "get_collection_names",
    # Episodic
    "EpisodicMemory", "EmotionalState", "ContextData", "OutcomeData",
    # Other types
    "IdentityMemory", "GoalMemory", "ReflectionMemory", "RelationshipMemory",
    # Pipeline
    "MemoryIngestionPipeline",
    # Scoring
    "ImportanceScorer", "ImportanceScore",
    # Consolidation
    "MemoryConsolidator", "ConsolidationResult",
]
