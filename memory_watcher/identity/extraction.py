"""
Identity Extraction Engine.

Pipeline:
  episodic memories
  ↓
  pattern clustering
  ↓
  trait inference
  ↓
  confidence scoring
  ↓
  identity updates

Traits emerge from repeated evidence and long-term consistency,
NOT one-off interactions.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from identity.models import (
    IdentityDomain,
    IdentityDomains,
    IdentityProfile,
    TraitCategory,
    TraitEvidence,
    TraitObject,
    IDENTITY_DOMAINS,
    get_all_domains,
    get_domain,
)

logger = logging.getLogger(__name__)


# ── Keyword Mappings ──────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "core_traits": [
        "personality", "character", "nature", "fundamental", "inherent",
        "always", "never", "consistently", "by nature", "essentially",
    ],
    "cognitive_style": [
        "systems", "architecture", "abstraction", "pattern", "model",
        "framework", "design", "structure", "holistic", "reductionist",
        "analytical", "synthetic", "first-principles", "top-down", "bottom-up",
    ],
    "communication_style": [
        "concise", "detailed", "verbose", "direct", "diplomatic",
        "technical", "plain", "jargon", "metaphor", "analogy",
        "brief", "thorough", "explicit", "implicit", "structured",
    ],
    "motivations": [
        "drive", "motivation", "passion", "obsession", "focus",
        "priority", "important", "care about", "values", "cared",
        "wants", "wishes", "aspires", "seeks", "pursues",
    ],
    "values": [
        "principle", "ethical", "boundary", "non-negotiable", "fundamental",
        "belief", "conviction", "integrity", "honesty", "quality",
        "pragmatic", "idealistic", "principle-driven", "value",
    ],
    "decision_patterns": [
        "decided", "decision", "chose", "chooses", "prefers", "preference",
        "chooses to", "opted", "opted for", "went with", "settled on",
        "risk", "cautious", "bold", "conservative", "aggressive",
    ],
    "emotional_patterns": [
        "frustrated", "excited", "stuck", "stuck on", "annoyed",
        "satisfied", "happy", "disappointed", "surprised", "impressed",
        "confident", "uncertain", "anxious", "relieved", "pleased",
    ],
    "behavioral_patterns": [
        "habit", "routine", "pattern", "tends to", "usually", "often",
        "repeatedly", "consistently", "always", "never", "avoids",
        "seeks out", "prefers", "default", "goes back to",
    ],
    "long_term_drives": [
        "goal", "vision", "mission", "long-term", "lifetime", "legacy",
        "building", "creating", "transforming", "revolutionizing",
        "dream", "ambition", "purpose", "meaning", "impact",
    ],
    "social_patterns": [
        "team", "collaborate", "lead", "follow", "mentor", "mentored",
        "independent", "solo", "pair", "group", "community",
        "network", "relationship", "trust", "respect", "authority",
    ],
    "creative_patterns": [
        "creative", "innovative", "novel", "original", "unconventional",
        "experimental", "prototype", "hack", "workaround", "elegant",
        "clever", "brilliant", "elegant solution", "lateral thinking",
    ],
    "stress_patterns": [
        "pressure", "deadline", "urgent", "rushed", "tight",
        "bottleneck", "blocker", "critical", "emergency", "fire",
        "crisis", "escalate", "triage", "prioritize", "cut corners",
    ],
}

# Trait-level keyword mappings for finer-grained inference
TRAIT_KEYWORDS = {
    # Core traits
    "systems_thinker": ["systems", "architecture", "architecture-level", "holistic", "big picture", "interconnected"],
    "detail_oriented": ["detail", "details", "meticulous", "thorough", "edge case", "edge cases"],
    "pragmatic": ["pragmatic", "practical", "works", "functional", "ship", "shipping", "minimum viable"],
    "perfectionist": ["perfect", "polish", "refine", "elegant", "beautiful", "quality", "high quality"],
    "autonomous": ["independent", "solo", "self-directed", "self-driven", "on my own", "by myself"],
    "collaborative": ["collaborate", "together", "pair", "team", "review", "feedback", "pair programming"],
    # Cognitive style
    "first_principles": ["first principles", "fundamental", "root cause", "why", "base case", "reduced to"],
    "optimization_driven": ["optimize", "optimization", "performance", "efficient", "efficiency", "bottleneck"],
    "abstract_thinker": ["abstract", "abstraction", "generalize", "generalization", "pattern", "meta"],
    "concrete_thinker": ["concrete", "specific", "example", "examples", "tangible", "practical example"],
    # Communication
    "concise_communicator": ["concise", "brief", "short", "TL;DR", "summary", "high-level", "executive summary"],
    "detailed_communicator": ["detailed", "thorough", "comprehensive", "deep dive", "full context", "all the details"],
    "technical_communicator": ["technical", "API", "implementation", "code", "architecture", "specification"],
    # Motivations
    "quality_driven": ["quality", "high quality", "best", "excellent", "world-class", "production-grade"],
    "learning_driven": ["learn", "learning", "understand", "understanding", "explore", "curious", "curiosity"],
    "impact_driven": ["impact", "scale", "users", "users at scale", "massive", "transformative", "disruptive"],
    # Values
    "transparency_valued": ["transparent", "open", "honest", "clear", "explicit", "no hidden"],
    "simplicity_valued": ["simple", "simplicity", "clean", "minimal", "minimalist", "elegant", "KISS"],
    # Decision patterns
    "risk_averse": ["cautious", "careful", "safe", "conservative", "proven", "battle-tested", "avoid risk"],
    "risk_tolerant": ["bold", "aggressive", "experimental", "try", "experiment", "take the leap", "push boundaries"],
    # Emotional
    "frustration_trigger": ["frustrated", "annoyed", "waste of time", "shallow", "superficial", "sloppy"],
    "excitement_trigger": ["excited", "love", "passion", "thrilled", "elegant", "beautiful solution"],
    # Behavioral
    "iterative_builder": ["iterate", "iteration", "prototype", "MVP", "v1", "v2", "refine", "improve"],
    "big_bang_builder": ["big bang", "complete", "full rewrite", "from scratch", "complete solution"],
    # Stress
    "deadline_driver": ["deadline", "urgent", "time pressure", "rushed", "time crunch"],
    "quality_under_pressure": ["quality", "even under pressure", "never compromise quality", "standards"],
}


class IdentityExtractionEngine:
    """
    Extracts traits from episodic memories through pattern analysis.
    
    Pipeline:
      1. Analyze episodic memories for keyword patterns
      2. Cluster evidence by trait
      3. Infer traits with confidence scores
      4. Update identity profile
    """

    MIN_EVIDENCE_FOR_INFERENCE = 2  # Minimum evidences before inferring a trait
    MIN_CONFIDENCE_FOR_ACTIVE = 0.3  # Below this, trait is dormant
    EVIDENCE_STRENGTH_BASE = 0.4  # Base strength for a keyword match

    def __init__(self, domains: Optional[IdentityDomains] = None):
        self.domains = domains or IDENTITY_DOMAINS

    def extract_from_memories(
        self,
        episodic_memories: List[Dict[str, Any]],
        entity_id: str,
        entity_name: str = "Unknown",
    ) -> IdentityProfile:
        """
        Main entry point: extract identity profile from episodic memories.
        
        Args:
            episodic_memories: List of memory dicts with 'id', 'summary', 'tags', etc.
            entity_id: Entity identifier
            entity_name: Human-readable name
            
        Returns:
            IdentityProfile with inferred traits
        """
        logger.info(f"[Identity Extraction] Processing {len(episodic_memories)} memories for '{entity_name}'")

        # Step 1: Collect all evidence
        all_evidence = self._collect_evidence(episodic_memories)

        # Step 2: Cluster evidence into traits
        trait_evidence_map = self._cluster_into_traits(all_evidence)

        # Step 3: Build trait objects
        traits = self._build_traits(trait_evidence_map, entity_id)

        # Step 4: Build profile
        profile = IdentityProfile(
            entity_id=entity_id,
            entity_name=entity_name,
            memory_count=len(episodic_memories),
        )

        # Register domains
        for domain in get_all_domains():
            profile.domains[domain.domain_id] = domain

        # Add traits
        for trait in traits.values():
            profile.add_trait(trait)

        # Calculate global confidence
        active_traits = [t for t in traits.values() if t.confidence >= self.MIN_CONFIDENCE_FOR_ACTIVE]
        if active_traits:
            profile.global_confidence = round(
                sum(t.confidence for t in active_traits) / len(active_traits), 4
            )
        else:
            profile.global_confidence = 0.0

        logger.info(
            f"[Identity Extraction] Found {len(traits)} traits, "
            f"{len(active_traits)} active, global confidence: {profile.global_confidence:.2f}"
        )

        return profile

    def _collect_evidence(self, memories: List[Dict[str, Any]]) -> List[TraitEvidence]:
        """Scan memories for trait-relevant keywords."""
        evidences: List[TraitEvidence] = []

        for mem in memories:
            mem_id = mem.get("id", "unknown")
            summary = mem.get("summary", "")
            content = mem.get("content", "")
            tags = mem.get("tags", [])
            event_type = mem.get("event_type", "")
            participants = mem.get("participants", [])

            # Combine all text for analysis
            text = f"{summary} {content}".lower()
            tag_text = " ".join(tags).lower()
            full_text = f"{text} {tag_text} {event_type}".lower()

            # Check domain keywords
            for domain_id, keywords in DOMAIN_KEYWORDS.items():
                matched_keywords = [kw for kw in keywords if kw in full_text]
                if matched_keywords:
                    strength = min(1.0, len(matched_keywords) / max(len(keywords), 1) * 2)
                    evidence = TraitEvidence(
                        source_memory_id=mem_id,
                        source_type=mem.get("type", "episodic"),
                        content=summary[:200],
                        strength=strength,
                        context={
                            "matched_keywords": matched_keywords,
                            "domain_id": domain_id,
                            "event_type": event_type,
                            "tags": tags,
                        },
                    )
                    evidences.append(evidence)

            # Check trait-level keywords for finer inference
            for trait_id, keywords in TRAIT_KEYWORDS.items():
                matched = [kw for kw in keywords if kw in full_text]
                if matched:
                    strength = min(1.0, len(matched) / max(len(keywords), 1) * 2.5)
                    evidence = TraitEvidence(
                        source_memory_id=mem_id,
                        source_type=mem.get("type", "episodic"),
                        content=summary[:200],
                        strength=strength,
                        context={
                            "matched_keywords": matched,
                            "trait_id": trait_id,
                            "event_type": event_type,
                            "tags": tags,
                        },
                    )
                    evidences.append(evidence)

        return evidences

    def _cluster_into_traits(self, evidences: List[TraitEvidence]) -> Dict[str, List[TraitEvidence]]:
        """Group evidences by trait_id from context."""
        clusters: Dict[str, List[TraitEvidence]] = defaultdict(list)

        for ev in evidences:
            trait_id = ev.context.get("trait_id")
            if trait_id:
                clusters[trait_id].append(ev)
            else:
                # Map to domain
                domain_id = ev.context.get("domain_id", "core_traits")
                # Use domain as fallback trait key
                clusters[f"domain_{domain_id}"].append(ev)

        return dict(clusters)

    def _build_traits(
        self, trait_evidence_map: Dict[str, List[TraitEvidence]], entity_id: str
    ) -> Dict[str, TraitObject]:
        """Build TraitObject instances from clustered evidence."""
        traits: Dict[str, TraitObject] = {}

        for trait_id, evidences in trait_evidence_map.items():
            if len(evidences) < self.MIN_EVIDENCE_FOR_INFERENCE:
                continue  # Not enough evidence for a trait

            # Determine domain
            domain_id = evidences[0].context.get("domain_id", "core_traits")
            domain = get_domain(domain_id)
            domain_name = domain.name if domain else domain_id

            # Determine category based on trait_id patterns
            category = self._infer_category(trait_id, evidences)

            # Calculate stability
            stability = self._calculate_stability(evidences, category)

            # Build trait
            trait = TraitObject(
                trait_id=trait_id,
                domain_id=domain_id,
                label=trait_id.replace("_", " ").title(),
                confidence=round(
                    sum(e.strength for e in evidences) / len(evidences), 4
                ),
                stability=stability,
                category=category,
            )

            for ev in evidences:
                trait.add_evidence(ev)

            traits[trait_id] = trait

        return traits

    def _infer_category(self, trait_id: str, evidences: List[TraitEvidence]) -> str:
        """Infer the trait category (core/persistent/adaptive/temporary)."""
        # Core traits: fundamental personality markers
        core_indicators = ["systems_thinker", "autonomous", "collaborative", "perfectionist", "pragmatic"]
        if any(ind in trait_id for ind in core_indicators):
            return "core"

        # Long-term drives are persistent
        if "long_term" in trait_id or "drive" in trait_id or "motivation" in trait_id:
            return "persistent"

        # Stress patterns are adaptive (context-dependent)
        if "stress" in trait_id or "pressure" in trait_id:
            return "adaptive"

        # Emotional triggers are temporary
        if "trigger" in trait_id:
            return "temporary"

        # Default: adaptive
        return "adaptive"

    def _calculate_stability(self, evidences: List[TraitEvidence], category: str) -> Any:
        """Calculate stability score for a trait."""
        if len(evidences) < 2:
            return StabilityScore(
                raw_score=0.0, evidence_count=len(evidences),
                time_span_days=0.0, reinforcement_rate=0.0,
                contradiction_count=0, category=category,
            )

        # Time span
        timestamps = [datetime.fromisoformat(e.detected_at) for e in evidences]
        timestamps.sort()
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0

        # Reinforcement rate (evidences per 30 days)
        if time_span > 0:
            reinforcement_rate = len(evidences) / max(time_span / 30.0, 1.0)
        else:
            reinforcement_rate = float(len(evidences))

        # Base score from evidence count
        evidence_score = min(1.0, len(evidences) / 5.0)

        # Time span bonus
        time_score = min(1.0, time_span / 90.0)  # 90 days = max time bonus

        # Category modifier
        category_modifiers = {
            "core": 1.2,
            "persistent": 1.0,
            "adaptive": 0.7,
            "temporary": 0.4,
        }
        mod = category_modifiers.get(category, 0.5)

        raw = min(1.0, (evidence_score * 0.5 + time_score * 0.3 + reinforcement_rate * 0.2) * mod)

        return StabilityScore(
            raw_score=round(raw, 4),
            evidence_count=len(evidences),
            time_span_days=round(time_span, 1),
            reinforcement_rate=round(reinforcement_rate, 4),
            contradiction_count=0,
            category=category,
        )

    def update_from_new_memory(
        self, profile: IdentityProfile, new_memory: Dict[str, Any]
    ) -> IdentityProfile:
        """Incrementally update an existing profile with a new memory."""
        new_evidences = self._collect_evidence([new_memory])

        for ev in new_evidences:
            trait_id = ev.context.get("trait_id")
            if not trait_id:
                continue

            trait = profile.get_trait(trait_id)
            if trait is None:
                # New trait detected — only add if strong evidence
                if ev.strength >= 0.7 and len(new_evidences) >= 2:
                    # Create new trait (will be low confidence until more evidence)
                    domain_id = ev.context.get("domain_id", "core_traits")
                    new_trait = TraitObject(
                        trait_id=trait_id,
                        domain_id=domain_id,
                        label=trait_id.replace("_", " ").title(),
                        confidence=ev.strength * 0.5,  # Start low
                        category=self._infer_category(trait_id, [ev]),
                    )
                    new_trait.add_evidence(ev)
                    profile.add_trait(new_trait)
                continue

            # Update existing trait
            trait.add_evidence(ev)

            # Update stability
            trait.stability = self._calculate_stability(trait.evidence, trait.category)

        # Update timestamps
        profile.updated_at = datetime.now(timezone.utc).isoformat()

        # Recalculate global confidence
        active = [t for t in profile.traits.values() if t.confidence >= self.MIN_CONFIDENCE_FOR_ACTIVE]
        if active:
            profile.global_confidence = round(
                sum(t.confidence for t in active) / len(active), 4
            )

        return profile
