"""
Contradiction Engine for Identity Kernel.

Handles internal consistency checks between traits.

Example:
  Existing trait: "prefers concise answers"
  New evidence: asks repeatedly for extremely deep explanations
  
  System:
    - lowers confidence
    - flags conflict
    - waits for more evidence

Humans work similarly — we don't rewrite identity on one contradiction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from identity.models import (
    IdentityProfile,
    TraitObject,
    TraitEvidence,
)

logger = logging.getLogger(__name__)


# Known contradiction pairs (trait_id pairs that conflict)
KNOWN_CONTRADICTIONS: List[Tuple[str, str]] = [
    ("concise_communicator", "detailed_communicator"),
    ("risk_averse", "risk_tolerant"),
    ("autonomous", "collaborative"),
    ("perfectionist", "pragmatic"),
    ("big_bang_builder", "iterative_builder"),
    ("deadline_driver", "quality_under_pressure"),
    ("abstract_thinker", "concrete_thinker"),
    ("frustration_trigger", "excitement_trigger"),
]

# Semantic contradiction patterns (text-based detection)
CONTRADICTION_PATTERNS = [
    (r"always.*short", r"always.*detailed"),
    (r"never.*collaborate", r"always.*team"),
    (r"prefers.*solo", r"prefers.*pair"),
    (r"quick.*decision", r"deliberate.*process"),
    (r"shallow.*answer", r"deep.*dive"),
    (r"minimal.*code", r"comprehensive.*solution"),
]


class ContradictionEngine:
    """
    Detects and handles contradictions within an identity profile.
    
    When contradictions are found:
      - Confidence of conflicting traits is lowered
      - Contradictions are logged with evidence
      - Traits are flagged for review
      - More evidence is required before resolution
    """

    CONTRADICTION_CONFIDENCE_PENALTY = 0.15
    RESOLUTION_THRESHOLD = 0.6  # Confidence needed to resolve a contradiction
    MAX_CONTRADICTIONS_PER_TRAIT = 5  # After this, trait is suppressed

    def __init__(
        self,
        known_contradictions: Optional[List[Tuple[str, str]]] = None,
    ):
        if known_contradictions:
            self.KNOWN_CONTRADICTIONS = known_contradictions

    def check_profile(self, profile: IdentityProfile) -> List[Dict[str, Any]]:
        """
        Check an identity profile for internal contradictions.
        
        Returns a list of contradiction findings.
        """
        findings: List[Dict[str, Any]] = []
        active_traits = [
            t for t in profile.traits.values()
            if t.confidence >= self.RESOLUTION_THRESHOLD
        ]

        # Check known contradiction pairs
        for trait_a_id, trait_b_id in self.KNOWN_CONTRADICTIONS:
            trait_a = profile.get_trait(trait_a_id)
            trait_b = profile.get_trait(trait_b_id)

            if trait_a and trait_b and trait_a.confidence >= 0.4 and trait_b.confidence >= 0.4:
                # Both traits are active — potential contradiction
                severity = min(trait_a.confidence, trait_b.confidence) * 0.5
                finding = {
                    "type": "known_contradiction",
                    "trait_a": trait_a_id,
                    "trait_b": trait_b_id,
                    "trait_a_confidence": trait_a.confidence,
                    "trait_b_confidence": trait_b.confidence,
                    "severity": round(severity, 4),
                    "resolved": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                findings.append(finding)

                # Apply penalty to both
                trait_a.confidence = max(
                    0.0, trait_a.confidence - self.CONTRADICTION_CONFIDENCE_PENALTY * 0.5
                )
                trait_b.confidence = max(
                    0.0, trait_b.confidence - self.CONTRADICTION_CONFIDENCE_PENALTY * 0.5
                )

                # Record in evolution history
                for trait in (trait_a, trait_b):
                    trait.evolution_history.append({
                        "timestamp": finding["timestamp"],
                        "action": "contradiction_detected",
                        "conflicting_trait": trait_b_id if trait is trait_a else trait_a_id,
                        "confidence_before": trait.confidence + self.CONTRADICTION_CONFIDENCE_PENALTY * 0.5,
                        "confidence_after": trait.confidence,
                        "severity": round(severity, 4),
                    })

        # Check semantic contradictions in evidence text
        semantic_findings = self._check_semantic_contradictions(profile)
        findings.extend(semantic_findings)

        # Update contradiction counts in stability scores
        for finding in findings:
            trait_id = finding.get("trait_a") or finding.get("trait_b")
            trait = profile.get_trait(trait_id)
            if trait:
                trait.stability.contradiction_count += 1

                # Suppress if too many contradictions
                if trait.stability.contradiction_count >= self.MAX_CONTRADICTIONS_PER_TRAIT:
                    trait.confidence = max(0.0, trait.confidence - 0.2)
                    trait.evolution_history.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "action": "suppressed_too_many_contradictions",
                        "contradiction_count": trait.stability.contradiction_count,
                    })

        return findings

    def _check_semantic_contradictions(self, profile: IdentityProfile) -> List[Dict[str, Any]]:
        """Check evidence text for semantic contradictions."""
        findings: List[Dict[str, Any]] = []

        # Group traits by domain
        domain_traits: Dict[str, List[TraitObject]] = {}
        for trait in profile.traits.values():
            if trait.confidence < 0.3:
                continue
            domain = trait.domain_id
            if domain not in domain_traits:
                domain_traits[domain] = []
            domain_traits[domain].append(trait)

        # Within each domain, check for semantic contradictions
        for domain_id, traits in domain_traits.items():
            if len(traits) < 2:
                continue

            for i, trait_a in enumerate(traits):
                for trait_b in traits[i + 1:]:
                    semantic_conflict = self._check_text_contradiction(trait_a, trait_b)
                    if semantic_conflict:
                        findings.append({
                            "type": "semantic_contradiction",
                            "domain": domain_id,
                            "trait_a": trait_a.trait_id,
                            "trait_b": trait_b.trait_id,
                            "trait_a_confidence": trait_a.confidence,
                            "trait_b_confidence": trait_b.confidence,
                            "severity": semantic_conflict,
                            "resolved": False,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

        return findings

    def _check_text_contradiction(self, trait_a: TraitObject, trait_b: TraitObject) -> float:
        """Check if two traits have contradictory evidence text."""
        # Get all evidence text
        texts_a = [ev.content.lower() for ev in trait_a.evidence]
        texts_b = [ev.content.lower() for ev in trait_b.evidence]

        if not texts_a or not texts_b:
            return 0.0

        conflict_count = 0
        total_checks = 0

        for pattern_a, pattern_b in CONTRADICTION_PATTERNS:
            for text_a in texts_a:
                for text_b in texts_b:
                    total_checks += 1
                    has_a = bool(self._compile_regex(pattern_a)) and any(
                        self._compile_regex(pattern_a).search(text_a)
                        for _ in [None]
                    )
                    has_b = bool(self._compile_regex(pattern_b)) and any(
                        self._compile_regex(pattern_b).search(text_b)
                        for _ in [None]
                    )
                    # Simplified: check if both patterns appear in combined text
                    combined = f"{text_a} {text_b}"
                    if self._compile_regex(pattern_a) and self._compile_regex(pattern_b):
                        if (self._compile_regex(pattern_a).search(text_a) and
                                self._compile_regex(pattern_b).search(text_b)):
                            conflict_count += 1

        if total_checks == 0:
            return 0.0

        return min(1.0, conflict_count / max(total_checks, 1) * 2)

    def _compile_regex(self, pattern: str):
        """Compile a regex pattern safely."""
        import re
        try:
            return re.compile(pattern)
        except re.error:
            return None

    def resolve_contradiction(
        self, profile: IdentityProfile, trait_a_id: str, trait_b_id: str,
        winning_trait_id: str, evidence: str
    ) -> bool:
        """
        Resolve a contradiction by reinforcing the winning trait
        and suppressing the losing one.
        """
        trait_a = profile.get_trait(trait_a_id)
        trait_b = profile.get_trait(trait_b_id)

        if not trait_a or not trait_b:
            return False

        winner = profile.get_trait(winning_trait_id)
        if not winner:
            return False

        # Reinforce winner
        ev = TraitEvidence(
            source_memory_id="contradiction_resolution",
            source_type="system",
            content=evidence,
            strength=0.9,
            context={"resolution": True, "resolved_pair": (trait_a_id, trait_b_id)},
        )
        winner.add_evidence(ev)

        # Suppress loser
        loser = trait_b if winning_trait_id == trait_a_id else trait_a
        loser.confidence = max(
            0.0, loser.confidence - self.CONTRADICTION_CONFIDENCE_PENALTY
        )

        loser.evolution_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "contradiction_resolved",
            "winner": winning_trait_id,
            "confidence_before": loser.confidence + self.CONTRADICTION_CONFIDENCE_PENALTY,
            "confidence_after": loser.confidence,
        })

        logger.info(
            f"[Contradiction] Resolved: '{winning_trait_id}' wins over "
            f"'{loser.trait_id}' (confidence: {loser.confidence:.3f})"
        )

        return True

    def get_contradiction_report(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Generate a full contradiction report for a profile."""
        findings = self.check_profile(profile)

        return {
            "entity_id": profile.entity_id,
            "total_contradictions": len(findings),
            "findings": findings,
            "suppressed_traits": [
                t.trait_id for t in profile.traits.values()
                if t.stability.contradiction_count >= self.MAX_CONTRADICTIONS_PER_TRAIT
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
