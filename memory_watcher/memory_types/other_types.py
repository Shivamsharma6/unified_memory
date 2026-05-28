"""
Additional memory type schemas: identity, goal, reflection, relationship.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IdentityMemory(BaseModel):
    """Stable personality traits, preferences, and identity markers."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trait: str = Field(description="Name of the trait")
    value: Any = Field(description="The trait value")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="system")
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = Field(default=None)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id, "trait": self.trait, "value": self.value,
            "confidence": self.confidence, "source": self.source, "tags": self.tags,
        }


class GoalMemory(BaseModel):
    """Ongoing objectives, tasks, and project states."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    title: str = Field(description="Goal title")
    description: str = Field(default="", description="Goal description")
    status: str = Field(default="active", description="active, paused, completed, abandoned")
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    milestones: List[str] = Field(default_factory=list)
    related_memories: List[str] = Field(default_factory=list)
    source: str = Field(default="system")
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = Field(default=None)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "status": self.status, "priority": self.priority, "progress": self.progress,
            "milestones": self.milestones, "related_memories": self.related_memories,
            "source": self.source, "tags": self.tags,
        }


class ReflectionMemory(BaseModel):
    """Self-analysis, lessons learned, and pattern recognition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    insight: str = Field(description="The reflective insight or lesson")
    category: str = Field(default="insight", description="Category: pattern, mistake, improvement, insight")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="system")
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = Field(default=None)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id, "insight": self.insight, "category": self.category,
            "confidence": self.confidence, "source": self.source, "tags": self.tags,
        }


class RelationshipMemory(BaseModel):
    """Person-specific dynamics, communication styles, and interaction history."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    person: str = Field(description="Person identifier")
    communication_style: str = Field(description="e.g., 'direct', 'diplomatic', 'technical'")
    preferences: Dict[str, Any] = Field(default_factory=dict)
    interaction_count: int = Field(default=0)
    last_interaction: Optional[str] = None
    key_dynamics: List[str] = Field(default_factory=list)
    related_memories: List[str] = Field(default_factory=list)
    source: str = Field(default="system")
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = Field(default=None)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id, "person": self.person, "communication_style": self.communication_style,
            "preferences": self.preferences, "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction, "key_dynamics": self.key_dynamics,
            "related_memories": self.related_memories, "source": self.source, "tags": self.tags,
        }
