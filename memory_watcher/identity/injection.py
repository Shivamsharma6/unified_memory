"""
Identity Injection Layer.

Before reasoning:

Retrieve:
  - relevant memories
  - relevant traits
  - active goals
  - emotional state

Inject them into agent cognition.

This is where the system starts behaving consistently.

IMPORTANT: Identity is NOT stored as prompts.
Bad: "You are Shivam-like..."
Good: Structured cognitive profile derived from evidence
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identity.models import (
    IdentityProfile,
    IdentityWeight,
)
from identity.weighting import IdentityWeightingEngine

logger = logging.getLogger(__name__)


class IdentityInjector:
    """
    Injects identity into agent reasoning by providing:
      - Core trait summaries
      - Communication style preferences
      - Decision pattern hints
      - Emotional state context
      - Retrieval weight boosts
      - Planning priority suggestions
    """

    def __init__(self, weighting_engine: Optional[IdentityWeightingEngine] = None):
        self.weighting_engine = weighting_engine or IdentityWeightingEngine()

    def inject(
        self,
        profile: IdentityProfile,
        query: str = "",
        task_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Main entry point: inject identity into agent cognition.
        
        Returns a structured injection block that agents can use
        to ground their reasoning in evidence-based identity.
        """
        if profile.global_confidence < 0.1:
            return self._empty_injection(profile)

        # Compute weights
        reasoning_profile = self.weighting_engine.get_reasoning_profile(profile)

        # Build injection blocks
        injection = {
            "entity_id": profile.entity_id,
            "entity_name": profile.entity_name,
            "identity_version": profile.version,
            "global_confidence": profile.global_confidence,
            "injected_at": datetime.now(timezone.utc).isoformat(),
            "task_type": task_type,
            "query_context": query[:100] if query else "",
        }

        # Core identity summary
        injection["core_identity"] = self._build_core_identity(profile)

        # Communication style
        injection["communication_context"] = self._build_communication_context(profile)

        # Decision patterns
        injection["decision_context"] = self._build_decision_context(profile)

        # Motivations
        injection["motivation_context"] = self._build_motivation_context(profile)

        # Retrieval boosts
        if query:
            injection["retrieval_boosts"] = self.weighting_engine.get_retrieval_boost(profile, query)

        # Planning priorities
        injection["planning_priorities"] = self.weighting_engine.get_planning_priorities(profile)

        # Emotional interpretation
        injection["emotional_context"] = self.weighting_engine.get_emotional_interpretation(profile)

        # Active states (temporary/adaptive traits)
        injection["active_states"] = [
            t.to_payload() for t in profile.get_active_states()
        ]

        # Top traits for reasoning
        injection["top_traits"] = profile.get_top_traits(count=5)

        return injection

    def inject_as_text(self, profile: IdentityProfile, query: str = "", task_type: str = "general") -> str:
        """
        Inject identity as a text block for prompt injection.
        
        This is the human-readable version used in agent prompts.
        """
        injection = self.inject(profile, query, task_type)

        lines = [f"[identity_injection entity={injection['entity_id']} v{injection['identity_version']}]"]

        # Core identity
        core = injection.get("core_identity", {})
        if core.get("top_traits"):
            lines.append(f"  Core identity: {', '.join(t['label'] for t in core['top_traits'][:3])}")

        # Communication
        comm = injection.get("communication_context", {})
        if comm.get("preferred_style"):
            lines.append(f"  Communication: {comm['preferred_style']}")
        if comm.get("length_preference"):
            lines.append(f"  Length: {comm['length_preference']}")

        # Decision patterns
        decisions = injection.get("decision_context", {})
        if decisions.get("default_pattern"):
            lines.append(f"  Decision style: {decisions['default_pattern']}")

        # Motivations
        motivations = injection.get("motivation_context", {})
        if motivations.get("primary_drivers"):
            lines.append(f"  Drivers: {', '.join(motivations['primary_drivers'][:2])}")

        # Planning
        priorities = injection.get("planning_priorities", [])
        if priorities:
            lines.append(f"  Planning focus: {', '.join(priorities[:2])}")

        lines.append("[/identity_injection]")

        return "\n".join(lines)

    def _empty_injection(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Return an empty injection when no identity is established."""
        return {
            "entity_id": profile.entity_id,
            "entity_name": profile.entity_name,
            "identity_version": profile.version,
            "global_confidence": 0.0,
            "core_identity": {},
            "communication_context": {},
            "decision_context": {},
            "motivation_context": {},
            "retrieval_boosts": {},
            "planning_priorities": [],
            "emotional_context": {},
            "active_states": [],
            "top_traits": [],
        }

    def _build_core_identity(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Build core identity summary."""
        top = profile.get_top_traits(count=5, min_confidence=0.3)

        return {
            "top_traits": [t.to_payload() for t in top],
            "domain_summaries": {
                did: {
                    "name": d.name,
                    "active_trait_count": len([
                        t for t in profile.get_domain_traits(did)
                        if t.confidence >= 0.3
                    ]),
                }
                for did, d in profile.domains.items()
            },
        }

    def _build_communication_context(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Build communication style context."""
        comm_traits = profile.get_domain_traits("communication_style")
        active = [t for t in comm_traits if t.confidence >= 0.3]

        if not active:
            return {}

        # Determine preferred style
        style_scores = {}
        for t in active:
            if "concise" in t.trait_id or "brief" in t.trait_id:
                style_scores["concise"] = t.confidence
            elif "detailed" in t.trait_id or "thorough" in t.trait_id:
                style_scores["detailed"] = t.confidence
            elif "technical" in t.trait_id:
                style_scores["technical"] = t.confidence

        preferred = max(style_scores, key=style_scores.get) if style_scores else "balanced"

        return {
            "preferred_style": preferred,
            "length_preference": "concise" if "concise" in preferred else "detailed",
            "active_traits": [t.to_payload() for t in active],
        }

    def _build_decision_context(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Build decision pattern context."""
        decision_traits = profile.get_domain_traits("decision_patterns")
        active = [t for t in decision_traits if t.confidence >= 0.3]

        if not active:
            return {}

        # Determine default pattern
        risk_scores = {}
        for t in active:
            if "risk" in t.trait_id:
                risk_scores[t.trait_id] = t.confidence

        default = max(risk_scores, key=risk_scores.get) if risk_scores else "balanced"

        return {
            "default_pattern": default,
            "active_traits": [t.to_payload() for t in active],
        }

    def _build_motivation_context(self, profile: IdentityProfile) -> Dict[str, Any]:
        """Build motivation context."""
        motivation_traits = profile.get_domain_traits("motivations")
        drive_traits = profile.get_domain_traits("long_term_drives")

        active = [t for t in motivation_traits + drive_traits if t.confidence >= 0.3]

        if not active:
            return {}

        return {
            "primary_drivers": [t.label for t in sorted(active, key=lambda t: t.confidence, reverse=True)[:3]],
            "active_traits": [t.to_payload() for t in active],
        }
