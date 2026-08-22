"""
Identity Store - Persistence layer for identity profiles.
Loads/saves profiles from JSON files in the vault.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from identity.models import IdentityProfile
from identity.extraction import IdentityExtractionEngine
from identity.stability import StabilityEngine
from identity.contradiction import ContradictionEngine
from identity.weighting import IdentityWeightingEngine
from identity.versioning import IdentityVersioningEngine
from identity.injection import IdentityInjector

logger = logging.getLogger(__name__)


from models.memory_record import get_vault_root


class IdentityStore:
    def __init__(self, vault_path: Optional[str | Path] = None):
        self.vault_path = get_vault_root(vault_path)
        self.identity_dir = self.vault_path / "Identity"
        self.identity_dir.mkdir(parents=True, exist_ok=True)


        self.extraction = IdentityExtractionEngine()
        self.stability = StabilityEngine()
        self.contradiction = ContradictionEngine()
        self.weighting = IdentityWeightingEngine()
        self.versioning = IdentityVersioningEngine(storage_dir=self.identity_dir)
        self.injection = IdentityInjector(self.weighting)

    def _profile_path(self, entity_id: str) -> Path:
        safe_id = entity_id.replace(" ", "_").replace("/", "_")
        return self.identity_dir / f"{safe_id}.json"

    def get_profile(self, entity_id: str) -> Optional[IdentityProfile]:
        path = self._profile_path(entity_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return IdentityProfile(**data)
        except Exception as e:
            logger.error(f"Failed to load identity profile: {e}")
            return None

    def save_profile(self, profile: IdentityProfile) -> None:
        path = self._profile_path(profile.entity_id)
        path.write_text(json.dumps(profile.to_payload(), indent=2))

    def extract_from_memories(self, entity_id: str, entity_name: str, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        profile = self.extraction.extract_from_memories(memories, entity_id, entity_name)
        profile = self.stability.apply_stability(profile)
        findings = self.contradiction.check_profile(profile)
        self.versioning.create_version(profile, trigger="extraction")
        self.save_profile(profile)
        return {
            "entity_id": entity_id,
            "traits_found": len(profile.traits),
            "active_traits": len([t for t in profile.traits.values() if t.confidence >= 0.3]),
            "global_confidence": profile.global_confidence,
            "contradictions": len(findings),
            "version": profile.version,
        }

    def inject_identity(self, entity_id: str, query: str = "", task_type: str = "general") -> Dict[str, Any]:
        profile = self.get_profile(entity_id)
        if not profile:
            return {"error": f"No profile found for '{entity_id}'"}
        return self.injection.inject(profile, query, task_type)

    def inject_as_text(self, entity_id: str, query: str = "", task_type: str = "general") -> str:
        profile = self.get_profile(entity_id)
        if not profile:
            return ""
        return self.injection.inject_as_text(profile, query, task_type)

    def get_retrieval_boosts(self, entity_id: str, query: str) -> Dict[str, float]:
        profile = self.get_profile(entity_id)
        if not profile:
            return {}
        return self.weighting.get_retrieval_boost(profile, query)

    def list_entities(self) -> List[str]:
        return [p.stem.replace("_", " ") for p in self.identity_dir.glob("*.json")]