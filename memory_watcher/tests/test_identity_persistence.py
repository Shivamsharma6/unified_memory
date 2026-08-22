import pytest
from pathlib import Path

try:
    from identity.models import TraitObject, TraitEvidence, IdentityProfile
    from identity.versioning import IdentityVersioningEngine
    from identity.store import IdentityStore
except ImportError:
    from memory_watcher.identity.models import TraitObject, TraitEvidence, IdentityProfile
    from memory_watcher.identity.versioning import IdentityVersioningEngine
    from memory_watcher.identity.store import IdentityStore


def test_trait_object_round_trip_preserves_evidence_and_history():
    trait = TraitObject(
        name="prefers_concise_answers",
        value=True,
        confidence=0.9,
        stability_score=0.85,
        evidence=[
            TraitEvidence(
                source_memory_id="mem-123",
                context_snippet="User requested short bullet points",
                confidence=0.95,
            )
        ],
        evolution_history=[
            {"timestamp": "2026-05-01T00:00:00Z", "old_value": False, "new_value": True, "reason": "Explicit instruction"}
        ],
    )

    payload = trait.to_payload()
    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["source_memory_id"] == "mem-123"
    assert len(payload["evolution_history"]) == 1

    restored = TraitObject.from_payload(payload)
    assert len(restored.evidence) == 1
    assert restored.evidence[0].source_memory_id == "mem-123"
    assert restored.evidence[0].context_snippet == "User requested short bullet points"
    assert len(restored.evolution_history) == 1
    assert restored.evolution_history[0]["reason"] == "Explicit instruction"


def test_versioning_engine_persists_across_instances(tmp_path):
    storage_dir = tmp_path / "Identity"
    storage_dir.mkdir()

    profile = IdentityProfile(entity_id="shivam", entity_name="Shivam Sharma", traits={})
    
    # Instance 1 creates a version
    engine1 = IdentityVersioningEngine(storage_dir=storage_dir)
    v1 = engine1.create_version("shivam", profile, "initial commit", "agent")
    assert v1.version == 1

    # Instance 2 initializes from disk and loads version 1
    engine2 = IdentityVersioningEngine(storage_dir=storage_dir)
    history = engine2.get_history("shivam")
    assert len(history) == 1
    assert history[0].version == 1
    assert history[0].commit_message == "initial commit"
