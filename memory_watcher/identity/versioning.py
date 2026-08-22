"""
Identity Versioning Engine.

Tracks identity evolution over time for:
  - drift analysis
  - psychological continuity
  - rollback capability
  - temporal simulation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from identity.models import (
    IdentityProfile,
    IdentityVersion,
)

logger = logging.getLogger(__name__)


import json
from pathlib import Path

class IdentityVersioningEngine:
    """
    Manages identity versions — snapshots of identity at points in time.
    
    Enables:
      - Tracking how identity evolves
      - Detecting major shifts
      - Rolling back to previous states
      - Simulating "what if" temporal paths
    """

    def __init__(self, max_versions: int = 50, storage_dir: Optional[Any] = None):
        self.versions: Dict[str, List[IdentityVersion]] = {}  # entity_id -> versions
        self.max_versions = max_versions
        self.storage_dir = Path(storage_dir) if storage_dir else None
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_all_versions()

    def _safe_id(self, entity_id: str) -> str:
        return entity_id.replace(" ", "_").replace("/", "_")

    def _load_all_versions(self) -> None:
        if not self.storage_dir:
            return
        for file in self.storage_dir.glob("*_versions.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    versions = [IdentityVersion(**item) for item in data]
                    if versions:
                        self.versions[versions[0].entity_id] = versions
            except Exception as e:
                logger.warning(f"Failed to load versions from {file}: {e}")

    def _save_versions(self, entity_id: str) -> None:
        if not self.storage_dir or entity_id not in self.versions:
            return
        try:
            safe = self._safe_id(entity_id)
            target = self.storage_dir / f"{safe}_versions.json"
            payload = [v.to_payload() for v in self.versions[entity_id]]
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to persist versions for {entity_id}: {e}")

    def create_version(
        self,
        profile_or_entity: Any,
        profile_or_trigger: Any = "manual",
        change_summary: str = "",
        trigger: str = "manual",
    ) -> IdentityVersion:
        """Create a versioned snapshot of the current identity profile."""
        if isinstance(profile_or_entity, str):
            entity_id = profile_or_entity
            profile = profile_or_trigger
            summary = change_summary
            trig = trigger
        else:
            profile = profile_or_entity
            entity_id = profile.entity_id
            trig = profile_or_trigger if isinstance(profile_or_trigger, str) else "manual"
            summary = change_summary

        entity_versions = self.versions.get(entity_id, [])

        next_number = max((v.version_number for v in entity_versions), default=0) + 1

        traits_snapshot = {
            tid: trait.to_payload() for tid, trait in profile.traits.items()
        }

        version = IdentityVersion(
            version_number=next_number,
            entity_id=entity_id,
            traits_snapshot=traits_snapshot,
            change_summary=summary or self._summarize_changes(
                entity_versions[-1] if entity_versions else None,
                traits_snapshot
            ),
            trigger=trig,
        )

        if entity_id not in self.versions:
            self.versions[entity_id] = []
        self.versions[entity_id].append(version)

        while len(self.versions[entity_id]) > self.max_versions:
            self.versions[entity_id].pop(0)

        if hasattr(profile, "version"):
            profile.version = next_number

        self._save_versions(entity_id)

        logger.info(
            f"[Versioning] Created v{next_number} for '{entity_id}' "
            f"(trigger: {trig})"
        )

        return version

    def get_version(self, entity_id: str, version_number: int) -> Optional[IdentityVersion]:
        """Retrieve a specific version by number."""
        entity_versions = self.versions.get(entity_id, [])
        for v in entity_versions:
            if v.version_number == version_number:
                return v
        return None

    def get_latest_version(self, entity_id: str) -> Optional[IdentityVersion]:
        """Get the most recent version for an entity."""
        entity_versions = self.versions.get(entity_id, [])
        return entity_versions[-1] if entity_versions else None

    def get_history(self, entity_id: str) -> List[IdentityVersion]:
        """Get the full list of IdentityVersion objects for an entity."""
        return self.versions.get(entity_id, [])

    def get_version_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get the full version history payload for an entity."""
        entity_versions = self.versions.get(entity_id, [])
        return [v.to_payload() for v in entity_versions]


    def detect_drift(self, entity_id: str) -> Dict[str, Any]:
        """
        Detect identity drift by comparing versions.
        
        Returns drift analysis with trait changes.
        """
        entity_versions = self.versions.get(entity_id, [])
        if len(entity_versions) < 2:
            return {"entity_id": entity_id, "drift_detected": False, "changes": []}

        latest = entity_versions[-1]
        previous = entity_versions[-2]

        changes = []
        latest_traits = latest.traits_snapshot
        previous_traits = previous.traits_snapshot

        all_trait_ids = set(latest_traits.keys()) | set(previous_traits.keys())

        for trait_id in all_trait_ids:
            latest_trait = latest_traits.get(trait_id)
            previous_trait = previous_traits.get(trait_id)

            if latest_trait and not previous_trait:
                changes.append({
                    "trait_id": trait_id,
                    "change_type": "new",
                    "confidence": latest_trait.get("confidence", 0),
                })
            elif previous_trait and not latest_trait:
                changes.append({
                    "trait_id": trait_id,
                    "change_type": "removed",
                    "previous_confidence": previous_trait.get("confidence", 0),
                })
            elif latest_trait and previous_trait:
                conf_diff = latest_trait.get("confidence", 0) - previous_trait.get("confidence", 0)
                if abs(conf_diff) > 0.1:
                    changes.append({
                        "trait_id": trait_id,
                        "change_type": "shifted",
                        "confidence_before": previous_trait.get("confidence", 0),
                        "confidence_after": latest_trait.get("confidence", 0),
                        "confidence_delta": round(conf_diff, 4),
                    })

        return {
            "entity_id": entity_id,
            "drift_detected": len(changes) > 0,
            "version_from": previous.version_number,
            "version_to": latest.version_number,
            "changes": changes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def rollback_to_version(
        self, entity_id: str, version_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Rollback an identity to a previous version.
        
        Returns the traits snapshot at that version.
        """
        version = self.get_version(entity_id, version_number)
        if not version:
            return None

        logger.info(
            f"[Versioning] Rolling back '{entity_id}' to v{version_number}"
        )

        return version.traits_snapshot

    def _summarize_changes(
        self, previous: Optional[IdentityVersion],
        current_traits: Dict[str, Any]
    ) -> str:
        """Generate a human-readable change summary."""
        if not previous:
            return f"Initial identity profile with {len(current_traits)} traits"

        previous_traits = previous.traits_snapshot
        changes = []

        for trait_id in set(current_traits.keys()) | set(previous_traits.keys()):
            curr = current_traits.get(trait_id)
            prev = previous_traits.get(trait_id)

            if curr and not prev:
                changes.append(f"new:{trait_id}")
            elif prev and not curr:
                changes.append(f"removed:{trait_id}")
            elif curr and prev:
                diff = curr.get("confidence", 0) - prev.get("confidence", 0)
                if abs(diff) > 0.1:
                    direction = "up" if diff > 0 else "down"
                    changes.append(f"{trait_id}:{direction}:{abs(diff):.2f}")

        if not changes:
            return "No significant changes"

        return "; ".join(changes[:5])
