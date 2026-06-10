"""
Identity Weighting Engine.

Not all traits are equal. This engine assigns influence weights:
  - central traits (high influence on reasoning)
  - peripheral traits (moderate influence)
  - temporary states (low influence, high context-dependence)

Weights influence:
  - response tone
  - retrieval weighting
  - planning priorities
  - emotional interpretation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identity.models import (
    IdentityProfile,
    IdentityWeight,
    TraitObject,
)

logger = logging.getLogger(__name__)


class IdentityWeightingEngine:
    """
    Assigns influence weights to traits based on their category,
    stability, and domain importance.
    """

    # Base weights by trait category
    CATEGORY_BASE_WEIGHTS = {
        "core": 0.9,
        "persistent": 0.7,
        "adaptive": 0.4,
        "temporary": 0.15,
    }

    # Domain importance multipliers
    DOMAIN_MULTIPLIERS = {
        "core_traits": 1.2,
        "motivations": 1.1,
        "values": 1.15,
        "long_term_drives": 1.1,
        "cognitive_style": 0.9,
        "decision_patterns": 0.85,
        "communication_style": 0.8,
        "behavioral_patterns": 0.75,
        "social_patterns": 0.65,
        "creative_patterns": 0.6,
        "emotional_patterns": 0.55,
        "stress_patterns": 0.5,
    }

    def __init__(self):
        self.weights: Dict[str, IdentityWeight] = {}

    def compute_weights(self, profile: IdentityProfile) -> Dict[str, IdentityWeight]:
        """Compute weights for all active traits in a profile."""
        self.weights = {}

        for trait_id, trait in profile.traits.items():
            if trait.confidence < 0.1:
                continue  # Skip dormant traits

            weight = self._compute_trait_weight(trait, profile)
            self.weights[trait_id] = weight

        logger.info(
            f"[Weighting] Computed weights for {len(self.weights)} traits "
            f"in profile for '{profile.entity_name}'"
        )

        return self.weights

    def _compute_trait_weight(self, trait: TraitObject, profile: IdentityProfile) -> IdentityWeight:
        """Compute influence weights for a single trait."""
        category = trait.category
        domain_id = trait.domain_id

        # Base weight from category
        base = self.CATEGORY_BASE_WEIGHTS.get(category, 0.3)

        # Domain multiplier
        domain_mult = self.DOMAIN_MULTIPLIERS.get(domain_id, 0.5)

        # Stability factor
        stability_factor = trait.stability.raw_score

        # Confidence factor
        confidence_factor = trait.confidence

        # Combined weight
        combined = base * domain_mult * (0.5 * stability_factor + 0.5 * confidence_factor)
        combined = min(1.0, max(0.0, combined))

        # Reasoning weight: how much this trait influences reasoning
        reasoning = combined * 1.0

        # Retrieval weight: how much this trait influences memory retrieval
        retrieval = combined * 0.9

        # Planning weight: how much this trait influences planning priorities
        planning = combined * 0.85

        # Emotional weight: how much this trait influences emotional interpretation
        emotional = combined * 0.7

        return IdentityWeight(
            trait_id=trait.trait_id,
            reasoning_weight=round(reasoning, 4),
            retrieval_weight=round(retrieval, 4),
            planning_weight=round(planning, 4),
            emotional_weight=round(emotional, 4),
            source="inferred",
        )

    def get_reasoning_profile(self, profile: IdentityProfile) -> Dict[str, Any]:
        """
        Get a weighted reasoning profile for injection into agent cognition.
        
        This is the key output used by the injection layer.
        """
        if not self.weights:
            self.compute_weights(profile)

        # Top weighted traits for reasoning
        sorted_weights = sorted(
            self.weights.values(),
            key=lambda w: w.reasoning_weight,
            reverse=True,
        )

        return {
            "entity_id": profile.entity_id,
            "entity_name": profile.entity_name,
            "global_confidence": profile.global_confidence,
            "top_reasoning_traits": [
                {
                    "trait_id": w.trait_id,
                    "reasoning_weight": w.reasoning_weight,
                }
                for w in sorted_weights[:10]
            ],
            "top_retrieval_traits": [
                {
                    "trait_id": w.trait_id,
                    "retrieval_weight": w.retrieval_weight,
                }
                for w in sorted_weights[:10]
            ],
            "top_planning_traits": [
                {
                    "trait_id": w.trait_id,
                    "planning_weight": w.planning_weight,
                }
                for w in sorted_weights[:10]
            ],
            "trait_weights": {w.trait_id: w.to_payload() for w in sorted_weights},
        }

    def get_retrieval_boost(self, profile: IdentityProfile, query: str) -> Dict[str, float]:
        """
        Get retrieval weight boosts based on identity traits.
        
        Returns a mapping of trait_id -> boost factor for use in
        memory retrieval ranking.
        """
        if not self.weights:
            self.compute_weights(profile)

        query_lower = query.lower()
        boosts: Dict[str, float] = {}

        for trait_id, weight in self.weights.items():
            # Check if query relates to this trait's domain
            trait = profile.get_trait(trait_id)
            if not trait:
                continue

            # Boost if query keywords match trait context
            trait_keywords = trait.tags + [trait.trait_id]
            if any(kw in query_lower for kw in trait_keywords):
                boosts[trait_id] = weight.retrieval_weight

        return boosts

    def get_planning_priorities(self, profile: IdentityProfile) -> List[str]:
        """Get planning priority hints based on identity traits."""
        if not self.weights:
            self.compute_weights(profile)

        sorted_weights = sorted(
            self.weights.values(),
            key=lambda w: w.planning_weight,
            reverse=True,
        )

        return [w.trait_id for w in sorted_weights if w.planning_weight > 0.3]

    def get_emotional_interpretation(self, profile: IdentityProfile) -> Dict[str, float]:
        """Get emotional interpretation weights."""
        if not self.weights:
            self.compute_weights(profile)

        return {
            w.trait_id: w.emotional_weight
            for w in self.weights.values()
            if w.emotional_weight > 0.1
        }
