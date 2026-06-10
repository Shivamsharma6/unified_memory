"""
Identity Kernel for UAMS.

The cognitive core that transforms retrieval infrastructure into
cognitive infrastructure. Identity emerges from:
  - persistent patterns
  - behavioral consistency
  - motivational structure
  - stable cognitive tendencies

This module answers: "Who is [entity]?" without hardcoding.

Components:
  models          - Identity domains, trait objects, stability scores
  extraction      - Episodic memory → trait inference pipeline
  stability       - Confidence decay, reinforcement, slow evolution
  contradiction   - Internal consistency checks
  weighting       - Central vs peripheral trait prioritization
  versioning      - Identity evolution tracking
  injection       - Identity → agent reasoning integration
"""

from identity.models import (
    IdentityDomain,
    IdentityDomains,
    TraitObject,
    TraitEvidence,
    StabilityScore,
    IdentityProfile,
    IdentityVersion,
    IdentityWeight,
    TraitCategory,
    IDENTITY_DOMAINS,
    get_domain,
    get_all_domains,
    get_trait_categories,
)

from identity.extraction import IdentityExtractionEngine

from identity.stability import StabilityEngine

from identity.contradiction import ContradictionEngine

from identity.weighting import IdentityWeightingEngine

from identity.versioning import IdentityVersioningEngine

from identity.injection import IdentityInjector

__all__ = [
    # Models
    "IdentityDomain", "IdentityDomains", "TraitObject",
    "TraitEvidence", "StabilityScore", "IdentityProfile",
    "IdentityVersion", "IdentityWeight", "TraitCategory",
    "IDENTITY_DOMAINS", "get_domain",
    "get_all_domains", "get_trait_categories",
    # Engines
    "IdentityExtractionEngine", "StabilityEngine",
    "ContradictionEngine", "IdentityWeightingEngine",
    "IdentityVersioningEngine", "IdentityInjector",
]
