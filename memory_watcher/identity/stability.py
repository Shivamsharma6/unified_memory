"""
Stability Engine for Identity Kernel.

Without stability, identity becomes chaotic.

Implements:
  - confidence decay over time
  - reinforcement thresholds
  - contradiction handling
  - slow evolution (NOT single-interaction rewrites)

Pipeline:
  New evidence
  ↓
  small adjustment
  ↓
  long-term reinforcement
  ↓
  identity update
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from identity.models import (
    IdentityProfile,
    StabilityScore,
    TraitObject,
    TraitEvidence,
)

logger = logging.getLogger(__name__)


class StabilityEngine:
    """
    Maintains identity stability through slow, evidence-based evolution.
    
    Key principles:
      - New evidence causes small adjustments, not rewrites
      - Traits need long-term reinforcement to change significantly
      - Contradictions lower confidence and require more evidence
      - Core traits evolve slower than adaptive/temporary traits
    """

    # Decay rates by category (per day)
    DECAY_RATES = {
        "core": 0.001,       # Very slow decay — core traits are sticky
        "persistent": 0.003,  # Moderate decay
        "adaptive": 0.01,     # Faster decay — adaptive traits shift with context
        "temporary": 0.03,    # Fast decay — temporary states fade quickly
    }

    # Reinforcement thresholds (evidences needed for 10% confidence shift)
    REINFORCEMENT_THRESHOLDS = {
        "core": 10,
        "persistent": 5,
        "adaptive": 3,
        "temporary": 1,
    }

    # Contradiction penalty
    CONTRADICTION_PENALTY = 0.15

    # Minimum confidence to keep a trait active
    MIN_ACTIVE_CONFIDENCE = 0.2

    # Dormancy threshold (below this, trait is dormant but not deleted)
    DORMANCY_THRESHOLD = 0.15

    def __init__(
        self,
        decay_rates: Optional[Dict[str, float]] = None,
        reinforcement_thresholds: Optional[Dict[str, int]] = None,
    ):
        if decay_rates:
            self.DECAY_RATES = decay_rates
        if reinforcement_thresholds:
            self.REINFORCEMENT_THRESHOLDS = reinforcement_thresholds

    def apply_stability(self, profile: IdentityProfile) -> IdentityProfile:
        """
        Apply stability rules to an identity profile.
        
        This is the main entry point — call periodically (e.g., daily)
        to maintain identity stability.
        """
        logger.info(f"[Stability] Applying stability to profile for '{profile.entity_name}'")

        for trait_id, trait in profile.traits.items():
            self._apply_trait_stability(trait)

        # Update global confidence
        active = [t for t in profile.traits.values() if t.confidence >= self.MIN_ACTIVE_CONFIDENCE]
        if active:
            profile.global_confidence = round(
                sum(t.confidence for t in active) / len(active), 4
            )

        profile.updated_at = datetime.now(timezone.utc).isoformat()
        return profile

    def _apply_trait_stability(self, trait: TraitObject) -> None:
        """Apply stability rules to a single trait."""
        category = trait.category
        decay_rate = self.DECAY_RATES.get(category, 0.01)

        # Apply time-based decay
        if trait.last_reinforced:
            last_dt = datetime.fromisoformat(trait.last_reinforced)
            days_since = (datetime.now(timezone.utc) - last_dt).days
            if days_since > 0:
                decay = decay_rate * days_since
                trait.confidence = max(
                    self.MIN_ACTIVE_CONFIDENCE,
                    trait.confidence - decay
                )

        # Check for dormancy
        if trait.confidence < self.DORMANCY_THRESHOLD:
            trait.confidence = 0.0  # Dormant, not deleted

        # Update stability score
        trait.stability = self._recalculate_stability(trait)

        # Record evolution if confidence changed significantly
        if trait.evolution_history:
            last = trait.evolution_history[-1]
            if abs(last.get("confidence_after", 0) - trait.confidence) > 0.05:
                trait.evolution_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "stability_decay",
                    "confidence_before": last.get("confidence_after", trait.confidence),
                    "confidence_after": trait.confidence,
                    "decay_applied": round(decay_rate * (
                        (datetime.now(timezone.utc) - datetime.fromisoformat(trait.last_reinforced)).days
                        if trait.last_reinforced else 0
                    ), 4),
                })

    def _recalculate_stability(self, trait: TraitObject) -> StabilityScore:
        """Recalculate stability score based on current evidence."""
        if not trait.evidence:
            return StabilityScore(
                raw_score=0.0, evidence_count=0,
                time_span_days=0.0, reinforcement_rate=0.0,
                contradiction_count=0, category=trait.category,
            )

        timestamps = [datetime.fromisoformat(e.detected_at) for e in trait.evidence]
        timestamps.sort()
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0

        if time_span > 0:
            reinforcement_rate = len(trait.evidence) / max(time_span / 30.0, 1.0)
        else:
            reinforcement_rate = float(len(trait.evidence))

        evidence_score = min(1.0, len(trait.evidence) / 5.0)
        time_score = min(1.0, time_span / 90.0)

        category_modifiers = {
            "core": 1.2, "persistent": 1.0,
            "adaptive": 0.7, "temporary": 0.4,
        }
        mod = category_modifiers.get(trait.category, 0.5)

        raw = min(1.0, (evidence_score * 0.5 + time_score * 0.3 + reinforcement_rate * 0.2) * mod)

        return StabilityScore(
            raw_score=round(raw, 4),
            evidence_count=len(trait.evidence),
            time_span_days=round(time_span, 1),
            reinforcement_rate=round(reinforcement_rate, 4),
            contradiction_count=0,
            category=trait.category,
        )

    def reinforce_trait(self, profile: IdentityProfile, trait_id: str, evidence_strength: float) -> bool:
        """
        Reinforce a trait with new evidence.
        
        Returns True if the trait was significantly reinforced.
        """
        trait = profile.get_trait(trait_id)
        if not trait:
            return False

        threshold = self.REINFORCEMENT_THRESHOLDS.get(trait.category, 3)

        # Add reinforcing evidence
        ev = TraitEvidence(
            source_memory_id="stability_reinforcement",
            source_type="system",
            content=f"Stability reinforcement (strength: {evidence_strength})",
            strength=evidence_strength,
            context={"reinforcement": True},
        )
        trait.add_evidence(ev)

        # Check if threshold crossed
        if len(trait.evidence) >= threshold:
            logger.info(
                f"[Stability] Trait '{trait_id}' reinforced (evidences: {len(trait.evidence)}, "
                f"confidence: {trait.confidence:.3f})"
            )
            return True

        return False

    def suppress_trait(self, profile: IdentityProfile, trait_id: str, reason: str = "contradiction") -> None:
        """Suppress a trait due to contradictions or lack of reinforcement."""
        trait = profile.get_trait(trait_id)
        if not trait:
            return

        trait.confidence = max(
            self.DORMANCY_THRESHOLD,
            trait.confidence - self.CONTRADICTION_PENALTY
        )

        trait.evolution_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "suppressed",
            "reason": reason,
            "confidence_before": trait.confidence + self.CONTRADICTION_PENALTY,
            "confidence_after": trait.confidence,
        })

        logger.info(f"[Stability] Trait '{trait_id}' suppressed (reason: {reason})")

    def get_dormant_traits(self, profile: IdentityProfile) -> List[TraitObject]:
        """Return traits that have fallen below the dormancy threshold."""
        return [
            t for t in profile.traits.values()
            if t.confidence < self.DORMANCY_THRESHOLD and t.confidence > 0
        ]

    def get_active_traits(self, profile: IdentityProfile) -> List[TraitObject]:
        """Return traits above the minimum active confidence."""
        return [
            t for t in profile.traits.values()
            if t.confidence >= self.MIN_ACTIVE_CONFIDENCE
        ]
