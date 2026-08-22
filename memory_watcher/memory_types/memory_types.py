"""
Memory Type Definitions for UAMS.

Defines the 7 memory categories that structure all stored experiences:
  semantic      - facts and concepts
  episodic      - experiences and events
  procedural    - how-to knowledge
  identity      - stable personality traits
  goal          - ongoing objectives
  reflection    - self-analysis and learning
  relationship  - person-specific dynamics
"""

import os
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class MemoryCategory(str, Enum):
    """The 7 memory categories for UAMS."""
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    IDENTITY = "identity"
    GOAL = "goal"
    REFLECTION = "reflection"
    RELATIONSHIP = "relationship"


CANONICAL_TYPE_ALIASES: Dict[str, str] = {
    "concept": MemoryCategory.SEMANTIC.value,
    "concepts": MemoryCategory.SEMANTIC.value,
    "semantic": MemoryCategory.SEMANTIC.value,
    "daily": MemoryCategory.EPISODIC.value,
    "episodic": MemoryCategory.EPISODIC.value,
    "task": MemoryCategory.PROCEDURAL.value,
    "tasks": MemoryCategory.PROCEDURAL.value,
    "procedure": MemoryCategory.PROCEDURAL.value,
    "procedures": MemoryCategory.PROCEDURAL.value,
    "procedural": MemoryCategory.PROCEDURAL.value,
    "profile": MemoryCategory.IDENTITY.value,
    "identity": MemoryCategory.IDENTITY.value,
    "goal": MemoryCategory.GOAL.value,
    "goals": MemoryCategory.GOAL.value,
    "objective": MemoryCategory.GOAL.value,
    "reflection": MemoryCategory.REFLECTION.value,
    "reflections": MemoryCategory.REFLECTION.value,
    "review": MemoryCategory.REFLECTION.value,
    "relationship": MemoryCategory.RELATIONSHIP.value,
    "relationships": MemoryCategory.RELATIONSHIP.value,
    "dynamics": MemoryCategory.RELATIONSHIP.value,
    "summary": MemoryCategory.SEMANTIC.value,
    "summaries": MemoryCategory.SEMANTIC.value,
}


def normalize_memory_type(val: Any) -> str:
    """Normalize any type string or alias to a canonical MemoryCategory value."""
    if not val:
        return MemoryCategory.SEMANTIC.value
    cleaned = str(val).strip().lower()
    return CANONICAL_TYPE_ALIASES.get(cleaned, MemoryCategory.SEMANTIC.value)


class MemoryTypeConfig(BaseModel):
    """Configuration for a single memory category."""
    model_config = ConfigDict(use_enum_values=True)

    name: MemoryCategory
    description: str
    collection_name: str
    vector_size: int = Field(default_factory=lambda: int(os.getenv("UAMS_EMBED_DIMENSION", "1024")))
    distance: str = "Cosine"
    enabled: bool = True
    retention_policy: str = "indefinite"  # indefinite, rolling, archival
    min_importance_threshold: float = 0.0  # 0.0–1.0, below this gets pruned



# Registry of all memory types
MEMORY_TYPES: Dict[MemoryCategory, MemoryTypeConfig] = {
    MemoryCategory.SEMANTIC: MemoryTypeConfig(
        name=MemoryCategory.SEMANTIC,
        description="Facts, concepts, and domain knowledge. Static knowledge that doesn't change frequently.",
        collection_name="semantic_memory",
        retention_policy="indefinite",
    ),
    MemoryCategory.EPISODIC: MemoryTypeConfig(
        name=MemoryCategory.EPISODIC,
        description="Experiences, events, and interactions. Time-stamped records of what happened, with emotional and contextual metadata.",
        collection_name="episodic_memory",
        retention_policy="rolling",
        min_importance_threshold=0.3,
    ),
    MemoryCategory.PROCEDURAL: MemoryTypeConfig(
        name=MemoryCategory.PROCEDURAL,
        description="How-to knowledge, workflows, and procedures. Actionable instructions for doing things.",
        collection_name="procedural_memory",
        retention_policy="indefinite",
    ),
    MemoryCategory.IDENTITY: MemoryTypeConfig(
        name=MemoryCategory.IDENTITY,
        description="Stable personality traits, preferences, and identity markers. Slowly evolving self-model.",
        collection_name="identity_memory",
        retention_policy="indefinite",
    ),
    MemoryCategory.GOAL: MemoryTypeConfig(
        name=MemoryCategory.GOAL,
        description="Ongoing objectives, tasks, and project states. Active goals that get updated as progress is made.",
        collection_name="goal_memory",
        retention_policy="rolling",
    ),
    MemoryCategory.REFLECTION: MemoryTypeConfig(
        name=MemoryCategory.REFLECTION,
        description="Self-analysis, lessons learned, and pattern recognition. Meta-cognitive insights derived from experiences.",
        collection_name="reflection_memory",
        retention_policy="rolling",
        min_importance_threshold=0.4,
    ),
    MemoryCategory.RELATIONSHIP: MemoryTypeConfig(
        name=MemoryCategory.RELATIONSHIP,
        description="Person-specific dynamics, communication styles, and interaction history. How to work with each person.",
        collection_name="relationship_memory",
        retention_policy="rolling",
    ),
}


def get_memory_type(category: MemoryCategory) -> MemoryTypeConfig:
    """Retrieve configuration for a memory category."""
    return MEMORY_TYPES[category]


def get_all_memory_types() -> List[MemoryTypeConfig]:
    """Return all configured memory types."""
    return list(MEMORY_TYPES.values())


def get_enabled_memory_types() -> List[MemoryTypeConfig]:
    """Return only enabled memory types."""
    return [t for t in MEMORY_TYPES.values() if t.enabled]


def get_collection_names() -> List[str]:
    """Return all collection names for memory categories."""
    return [t.collection_name for t in MEMORY_TYPES.values()]
