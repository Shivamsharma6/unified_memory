import pytest
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from graph.extractor import ProjectedClaim, extract_projection
    from models.memory_record import parse_memory
except ImportError:
    from memory_watcher.graph.extractor import ProjectedClaim, extract_projection
    from memory_watcher.models.memory_record import parse_memory


def test_projected_claim_has_validity_fields():
    claim = ProjectedClaim(
        subject="Project Alpha",
        predicate="uses",
        object="Qdrant",
        status="explicit",
        confidence=1.0,
        evidence_memory_id=uuid.uuid4(),
        evidence_path="Daily/2026-08-01.md",
        valid_from="2026-08-01T00:00:00Z",
        valid_to=None,
        invalidated_by=None,
    )
    assert claim.valid_from == "2026-08-01T00:00:00Z"
    assert claim.valid_to is None
    assert claim.invalidated_by is None


def test_extract_projection_populates_validity_from_note_date():
    raw = """---
type: episodic
date: 2026-08-15
related_to: ["[[PostgreSQL]]"]
---
# Architecture Update
We use [[PostgreSQL]] for metadata storage.
"""
    record = parse_memory(Path("Daily/2026-08-15.md"), raw)
    projection = extract_projection(record)
    assert len(projection.claims) >= 1
    claim = projection.claims[0]
    assert claim.valid_from is not None
    assert "2026-08-15" in claim.valid_from
