"""
Episodic Memory Schema for UAMS.

Defines the structure for storing EXPERIENCES (not raw conversations).
Each episodic memory captures:
  - Context (where, when, what environment)
  - Emotional state (frustration, excitement, confidence levels)
  - Outcome (what happened, consequences)
  - Importance (weighted score for long-term survival)
  - Relationships (linked memories, participants)
  - Meaning (interpreted significance, extracted learnings)
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class EmotionalState(BaseModel):
    """Emotional metadata for an episodic memory event."""
    frustration: float = Field(default=0.0)
    excitement: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    stress: float = Field(default=0.0)
    satisfaction: float = Field(default=0.0)

    @field_validator("frustration", "excitement", "confidence", "stress", "satisfaction")
    @classmethod
    def clamp_values(cls, v):
        return max(0.0, min(1.0, v))

    def dominant_emotion(self) -> str:
        """Return the name of the highest-scoring emotion."""
        emotions = {
            "frustration": self.frustration,
            "excitement": self.excitement,
            "confidence": self.confidence,
            "stress": self.stress,
            "satisfaction": self.satisfaction,
        }
        return max(emotions, key=emotions.get)

    def intensity(self) -> float:
        """Average emotional intensity across all dimensions."""
        values = [self.frustration, self.excitement, self.confidence, self.stress, self.satisfaction]
        return sum(values) / len(values)


class ContextData(BaseModel):
    """Contextual metadata for an episodic memory."""
    location: Optional[str] = None
    platform: Optional[str] = None
    time_of_day: Optional[str] = None
    participants_count: int = 0
    tools_used: List[str] = Field(default_factory=list)
    external_systems: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class OutcomeData(BaseModel):
    """Outcome metadata for an episodic memory."""
    success: Optional[bool] = None
    resolution: Optional[str] = None
    consequences: List[str] = Field(default_factory=list)
    lessons_learned: List[str] = Field(default_factory=list)
    follow_up_actions: List[str] = Field(default_factory=list)


class EpisodicMemory(BaseModel):
    """
    Full episodic memory record — stores EXPERIENCES, not raw transcripts.
    
    Contains interpreted meaning, emotional metadata, consequences,
    and extracted learnings for high-quality retrieval.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = Field(
        description="Type of event: conversation, decision, failure, success, error, deployment, meeting"
    )
    summary: str = Field(
        description="Short, actionable summary of the experience"
    )
    participants: List[str] = Field(
        default_factory=list,
        description="List of participant identifiers (agent names, user names)"
    )
    emotional_state: EmotionalState = Field(default_factory=EmotionalState)
    importance: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Weighted importance score (0.0–1.0). High-value memories survive consolidation."
    )
    context: ContextData = Field(default_factory=ContextData)
    outcome: OutcomeData = Field(default_factory=OutcomeData)
    related_memories: List[str] = Field(
        default_factory=list,
        description="IDs of related episodic memories"
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding for semantic search"
    )
    source: str = Field(
        default="system",
        description="Source agent that created this memory"
    )
    tags: List[str] = Field(default_factory=list)
    raw_excerpt: Optional[str] = Field(
        default=None,
        description="Optional short excerpt from the original interaction"
    )

    def to_payload(self) -> Dict[str, Any]:
        """Convert to a flat dictionary suitable for storage."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "summary": self.summary,
            "participants": self.participants,
            "emotional_state": self.emotional_state.model_dump(),
            "importance": self.importance,
            "context": self.context.model_dump(exclude_none=True),
            "outcome": self.outcome.model_dump(exclude_none=True),
            "related_memories": self.related_memories,
            "source": self.source,
            "tags": self.tags,
            "raw_excerpt": self.raw_excerpt,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "EpisodicMemory":
        """Reconstruct an EpisodicMemory from stored payload."""
        return cls(
            id=payload.get("id", str(uuid.uuid4())),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            event_type=payload.get("event_type", "conversation"),
            summary=payload.get("summary", ""),
            participants=payload.get("participants", []),
            emotional_state=EmotionalState(**payload.get("emotional_state", {})),
            importance=payload.get("importance", 0.5),
            context=ContextData(**payload.get("context", {})),
            outcome=OutcomeData(**payload.get("outcome", {})),
            related_memories=payload.get("related_memories", []),
            source=payload.get("source", "system"),
            tags=payload.get("tags", []),
            raw_excerpt=payload.get("raw_excerpt"),
        )

    def to_markdown(self) -> str:
        """Convert to UAMS-compatible Markdown with YAML frontmatter."""
        fm = {
            "type": "episodic",
            "date": self.timestamp[:10],
            "event_type": self.event_type,
            "participants": self.participants,
            "importance": self.importance,
            "source": self.source,
            "tags": [f"#{self.event_type}", f"#{self.context.platform}" if self.context.platform else ""],
        }
        fm_tags = [t for t in fm["tags"] if t]
        fm["tags"] = fm_tags

        lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {self.summary}")
        lines.append("")
        lines.append(f"**Event:** {self.event_type} | **Importance:** {self.importance:.2f}")
        lines.append("")
        lines.append(f"**Participants:** {', '.join(self.participants) if self.participants else 'N/A'}")
        lines.append("")
        lines.append("**Emotional State:**")
        lines.append(f"- Frustration: {self.emotional_state.frustration:.2f}")
        lines.append(f"- Excitement: {self.emotional_state.excitement:.2f}")
        lines.append(f"- Confidence: {self.emotional_state.confidence:.2f}")
        lines.append(f"- Stress: {self.emotional_state.stress:.2f}")
        lines.append(f"- Satisfaction: {self.emotional_state.satisfaction:.2f}")
        lines.append("")

        if self.context.model_dump(exclude_none=True):
            lines.append("**Context:**")
            ctx = self.context.model_dump(exclude_none=True)
            for k, v in ctx.items():
                if v:
                    lines.append(f"- {k}: {v}")
            lines.append("")

        if self.outcome.model_dump(exclude_none=True):
            lines.append("**Outcome:**")
            out = self.outcome.model_dump(exclude_none=True)
            if out.get("success") is not None:
                lines.append(f"- Success: {out['success']}")
            if out.get("resolution"):
                lines.append(f"- Resolution: {out['resolution']}")
            if out.get("consequences"):
                lines.append(f"- Consequences: {', '.join(out['consequences'])}")
            if out.get("lessons_learned"):
                lines.append(f"- Lessons: {', '.join(out['lessons_learned'])}")
            lines.append("")

        if self.related_memories:
            lines.append(f"**Related Memories:** {', '.join(self.related_memories)}")
            lines.append("")

        return "\n".join(lines)
