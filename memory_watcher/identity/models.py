"""
Core Identity Kernel Models.

Defines the structured self-model that answers "Who is [entity]?"
without hardcoding. Identity is:
  - inferred from evidence
  - scored with confidence
  - versioned over time
  - explainable via supporting memories

12 identity domains split identity into dimensions:
  core_traits, cognitive_style, communication_style,
  motivations, values, decision_patterns,
  emotional_patterns, behavioral_patterns,
  long_term_drives, social_patterns,
  creative_patterns, stress_patterns
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Trait Categories ──────────────────────────────────────────────

class TraitCategory(str, Enum):
    """Categories that determine trait stability and influence."""
    CORE = "core"              # Central to identity, high stability
    PERSISTENT = "persistent"  # Long-term but adaptable
    ADAPTIVE = "adaptive"      # Context-dependent
    TEMPORARY = "temporary"    # State-level, low stability


# ── Identity Domains ──────────────────────────────────────────────

class IdentityDomain(BaseModel):
    """A single dimension of identity."""
    domain_id: str = Field(description="Unique domain identifier")
    name: str = Field(description="Human-readable domain name")
    description: str = Field(description="What this domain captures")
    trait_ids: List[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Domain influence weight")

    def to_payload(self) -> Dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "trait_ids": self.trait_ids,
            "weight": self.weight,
        }


class IdentityDomains(BaseModel):
    """Registry of all 12 identity domains."""
    domains: Dict[str, IdentityDomain] = Field(default_factory=dict)

    def register(self, domain: IdentityDomain) -> None:
        self.domains[domain.domain_id] = domain

    def get(self, domain_id: str) -> Optional[IdentityDomain]:
        return self.domains.get(domain_id)

    def get_trait_domains(self, trait_id: str) -> List[str]:
        """Return all domains that contain this trait."""
        return [
            did for did, d in self.domains.items()
            if trait_id in d.trait_ids
        ]


# ── Trait Evidence ────────────────────────────────────────────────

class TraitEvidence(BaseModel):
    """A single piece of evidence supporting a trait."""
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_memory_id: str = Field(default="", description="ID of the episodic memory this came from")
    source_type: str = Field(default="episodic", description="episodic | procedural | reflection")
    content: str = Field(default="", description="The actual evidence text")
    context_snippet: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="How strongly this supports the trait")
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.context_snippet and not self.content:
            self.content = self.context_snippet
        elif self.content and not self.context_snippet:
            self.context_snippet = self.content
        if self.confidence and not self.strength:
            self.strength = self.confidence
        elif self.strength and not self.confidence:
            self.confidence = self.strength

    def to_payload(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_memory_id": self.source_memory_id,
            "source_type": self.source_type,
            "content": self.content,
            "context_snippet": self.context_snippet,
            "confidence": self.confidence,
            "strength": self.strength,
            "detected_at": self.detected_at,
            "context": self.context,
        }


# ── Stability Score ───────────────────────────────────────────────

class StabilityScore(BaseModel):
    """How stable/reliable a trait is over time."""
    raw_score: float = Field(default=0.0, description="0.0–1.0 stability")
    evidence_count: int = Field(default=0, description="Number of supporting evidences")
    time_span_days: float = Field(default=0.0, description="Days between first and last evidence")
    reinforcement_rate: float = Field(default=0.0, description="How often trait is reinforced")
    contradiction_count: int = Field(default=0, description="Number of contradictions found")
    category: str = Field(default="adaptive", description="core | persistent | adaptive | temporary")
    label: str = Field(default="adaptive")

    @field_validator("raw_score")
    @classmethod
    def clamp(cls, v):
        return max(0.0, min(1.0, v))

    def compute(self) -> float:
        freq_factor = min(self.evidence_count / 10.0, 1.0)
        time_factor = min(self.time_span_days / 90.0, 1.0)
        contra_penalty = min(self.contradiction_count * 0.2, 0.6)
        self.raw_score = round(
            max(0.0, min(1.0, (freq_factor * 0.4 + time_factor * 0.4 + self.reinforcement_rate * 0.2) - contra_penalty)),
            4
        )
        return self.raw_score

    def get_tier(self) -> str:
        if self.raw_score >= 0.8:
            return "core"
        if self.raw_score >= 0.5:
            return "medium"
        if self.raw_score >= 0.25:
            return "low"
        return "unstable"

    def to_payload(self) -> Dict[str, Any]:
        return {
            "raw_score": self.raw_score,
            "evidence_count": self.evidence_count,
            "time_span_days": self.time_span_days,
            "reinforcement_rate": self.reinforcement_rate,
            "contradiction_count": self.contradiction_count,
            "category": self.category,
            "label": self.label,
        }


# ── Trait Object ──────────────────────────────────────────────────

class TraitObject(BaseModel):
    """
    A single trait within an identity profile.
    
    Contains evidence, confidence, evolution history,
    and supporting memories for auditability.
    """
    trait_id: str = Field(default="trait", description="Unique trait identifier, e.g. 'systems_thinker'")
    domain_id: str = Field(default="general", description="Which identity domain this belongs to")
    label: str = Field(default="Trait", description="Human-readable label, e.g. 'Systems Thinker'")
    name: Optional[str] = None
    value: Optional[Any] = None
    stability_score: Optional[float] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Current confidence in this trait")
    stability: StabilityScore = Field(default_factory=lambda: StabilityScore(
        raw_score=0.0, evidence_count=0, time_span_days=0.0,
        reinforcement_rate=0.0, contradiction_count=0, category="adaptive"
    ))
    evidence: List[TraitEvidence] = Field(default_factory=list)
    supporting_memory_ids: List[str] = Field(default_factory=list)
    first_detected: Optional[str] = None
    last_reinforced: Optional[str] = None
    evolution_history: List[Dict[str, Any]] = Field(default_factory=list)
    category: str = Field(default="adaptive", description="core | persistent | adaptive | temporary")
    tags: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.name and not self.trait_id:
            self.trait_id = self.name
        if self.name and not self.label:
            self.label = self.name
        if self.stability_score is not None:
            self.stability.raw_score = self.stability_score

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, v))

    def add_evidence(self, evidence: TraitEvidence) -> None:
        """Add evidence and update confidence."""
        self.evidence.append(evidence)
        self.supporting_memory_ids.append(evidence.source_memory_id)

        if self.first_detected is None:
            self.first_detected = evidence.detected_at
        self.last_reinforced = evidence.detected_at

        # Record evolution
        self.evolution_history.append({
            "timestamp": evidence.detected_at,
            "action": "evidence_added",
            "confidence_before": self.confidence,
            "confidence_after": self.confidence,
            "evidence_strength": evidence.strength,
        })

        # Update confidence based on new evidence
        if self.evidence:
            avg_strength = sum(e.strength for e in self.evidence) / len(self.evidence)
            self.confidence = round(
                self.confidence * 0.7 + avg_strength * 0.3, 4
            )
            self.confidence = max(0.0, min(1.0, self.confidence))

    def to_payload(self) -> Dict[str, Any]:
        return {
            "trait_id": self.trait_id,
            "domain_id": self.domain_id,
            "label": self.label,
            "name": self.name or self.trait_id,
            "value": self.value,
            "confidence": self.confidence,
            "stability_score": self.stability.raw_score,
            "stability": self.stability.to_payload(),
            "evidence": [e.to_payload() for e in self.evidence],
            "evidence_count": len(self.evidence),
            "supporting_memory_ids": self.supporting_memory_ids,
            "first_detected": self.first_detected,
            "last_reinforced": self.last_reinforced,
            "evolution_history": self.evolution_history,
            "category": self.category,
            "tags": self.tags,
        }

    @classmethod
    def from_payload(cls, data: Dict[str, Any]) -> "TraitObject":
        ev_list = []
        for e in data.get("evidence", []):
            if isinstance(e, TraitEvidence):
                ev_list.append(e)
            elif isinstance(e, dict):
                ev_list.append(TraitEvidence(**e))

        stability_data = data.get("stability", {})
        if isinstance(stability_data, dict) and stability_data:
            stability = StabilityScore(**stability_data)
        elif isinstance(stability_data, StabilityScore):
            stability = stability_data
        else:
            raw_s = float(data.get("stability_score", 0.0))
            stability = StabilityScore(
                raw_score=raw_s, evidence_count=len(ev_list), time_span_days=0.0,
                reinforcement_rate=0.0, contradiction_count=0, category="adaptive"
            )

        return cls(
            trait_id=data.get("trait_id") or data.get("name", "trait"),
            domain_id=data.get("domain_id", "general"),
            label=data.get("label") or data.get("name", "Trait"),
            name=data.get("name"),
            value=data.get("value"),
            stability_score=data.get("stability_score"),
            confidence=float(data.get("confidence", 0.5)),
            stability=stability,
            evidence=ev_list,
            supporting_memory_ids=data.get("supporting_memory_ids", []),
            first_detected=data.get("first_detected"),
            last_reinforced=data.get("last_reinforced"),
            evolution_history=data.get("evolution_history", []),
            category=data.get("category", "adaptive"),
            tags=data.get("tags", []),
        )



# ── Identity Profile ──────────────────────────────────────────────

class IdentityProfile(BaseModel):
    """
    The complete structured self-model for an entity.
    
    This is the output of the Identity Kernel — a continuously
    evolving, evidence-based identity profile.
    """
    entity_id: str = Field(description="Entity identifier, e.g. 'Shivam Sharma'")
    entity_name: str = Field(description="Human-readable name")
    domains: Dict[str, IdentityDomain] = Field(default_factory=dict)
    traits: Dict[str, TraitObject] = Field(default_factory=dict)
    global_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall confidence in this profile")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    memory_count: int = Field(default=0, description="Total episodic memories used")
    version: int = Field(default=1, description="Current identity version number")

    def add_trait(self, trait: TraitObject) -> None:
        """Add a trait to the profile and register it in its domain."""
        self.traits[trait.trait_id] = trait
        if trait.domain_id in self.domains:
            if trait.trait_id not in self.domains[trait.domain_id].trait_ids:
                self.domains[trait.domain_id].trait_ids.append(trait.trait_id)

    def get_trait(self, trait_id: str) -> Optional[TraitObject]:
        return self.traits.get(trait_id)

    def get_domain_traits(self, domain_id: str) -> List[TraitObject]:
        domain = self.domains.get(domain_id)
        if not domain:
            return []
        return [
            self.traits[tid] for tid in domain.trait_ids
            if tid in self.traits
        ]

    def get_top_traits(self, count: int = 5, min_confidence: float = 0.3) -> List[TraitObject]:
        """Return the most confident, stable traits."""
        candidates = [
            t for t in self.traits.values()
            if t.confidence >= min_confidence
        ]
        candidates.sort(key=lambda t: (t.stability.raw_score, t.confidence), reverse=True)
        return candidates[:count]

    def get_active_states(self) -> List[TraitObject]:
        """Return temporary/adaptive traits (current states, not deep identity)."""
        return [
            t for t in self.traits.values()
            if t.category in ("temporary", "adaptive")
        ]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "domains": {k: v.to_payload() for k, v in self.domains.items()},
            "traits": {k: v.to_payload() for k, v in self.traits.items()},
            "global_confidence": self.global_confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "memory_count": self.memory_count,
            "version": self.version,
        }


# ── Identity Version ──────────────────────────────────────────────

class IdentityVersion(BaseModel):
    """A snapshot of identity at a point in time."""
    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version_number: int = Field(default=1, description="Sequential version number")
    entity_id: str = Field(default="", description="Which entity this belongs to")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    traits_snapshot: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    change_summary: str = Field(default="", description="What changed from previous version")
    trigger: str = Field(default="manual", description="manual | extraction | stability_update | contradiction")

    @property
    def version(self) -> int:
        return self.version_number

    @property
    def commit_message(self) -> str:
        return self.change_summary

    def to_payload(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp,
            "traits_snapshot": self.traits_snapshot,
            "change_summary": self.change_summary,
            "trigger": self.trigger,
        }



# ── Identity Weight ───────────────────────────────────────────────

class IdentityWeight(BaseModel):
    """How much a trait influences agent reasoning."""
    trait_id: str = Field(description="Which trait this weight applies to")
    reasoning_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Influence on reasoning")
    retrieval_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Influence on memory retrieval")
    planning_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Influence on planning priorities")
    emotional_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Influence on emotional interpretation")
    source: str = Field(default="system", description="system | manual | inferred")

    def to_payload(self) -> Dict[str, Any]:
        return {
            "trait_id": self.trait_id,
            "reasoning_weight": self.reasoning_weight,
            "retrieval_weight": self.retrieval_weight,
            "planning_weight": self.planning_weight,
            "emotional_weight": self.emotional_weight,
            "source": self.source,
        }


# ── Default Domain Registry ───────────────────────────────────────

IDENTITY_DOMAINS = IdentityDomains()

# Register the 12 identity domains
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="core_traits",
    name="Core Traits",
    description="Fundamental personality characteristics that define the entity",
    weight=1.0,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="cognitive_style",
    name="Cognitive Style",
    description="How the entity processes information and solves problems",
    weight=0.9,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="communication_style",
    name="Communication Style",
    description="Preferred communication patterns and preferences",
    weight=0.8,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="motivations",
    name="Motivations",
    description="What drives the entity's actions and decisions",
    weight=0.9,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="values",
    name="Values",
    description="Core principles and ethical boundaries",
    weight=0.95,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="decision_patterns",
    name="Decision Patterns",
    description="How the entity makes decisions under various conditions",
    weight=0.85,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="emotional_patterns",
    name="Emotional Patterns",
    description="Recurring emotional responses and triggers",
    weight=0.7,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="behavioral_patterns",
    name="Behavioral Patterns",
    description="Recurring action patterns and habits",
    weight=0.8,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="long_term_drives",
    name="Long-Term Drives",
    description="Deep, enduring motivations that persist across contexts",
    weight=0.95,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="social_patterns",
    name="Social Patterns",
    description="How the entity interacts with others in social contexts",
    weight=0.75,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="creative_patterns",
    name="Creative Patterns",
    description="Approach to creativity, innovation, and novel problem-solving",
    weight=0.7,
))
IDENTITY_DOMAINS.register(IdentityDomain(
    domain_id="stress_patterns",
    name="Stress Patterns",
    description="How the entity responds under pressure and stress",
    weight=0.65,
))


def get_domain(domain_id: str) -> Optional[IdentityDomain]:
    return IDENTITY_DOMAINS.get(domain_id)


def get_all_domains() -> List[IdentityDomain]:
    return list(IDENTITY_DOMAINS.domains.values())


def get_trait_categories() -> List[TraitCategory]:
    return list(TraitCategory)
