import pytest
from pathlib import Path
import yaml

try:
    from intelligence.distiller import MemoryDistiller
except ImportError:
    from memory_watcher.intelligence.distiller import MemoryDistiller


def test_promote_referenced_entities_promotes_after_2_references(tmp_path):
    distiller = MemoryDistiller()
    
    daily_dir = tmp_path / "Daily"
    concepts_dir = tmp_path / "Concepts"
    daily_dir.mkdir(parents=True, exist_ok=True)
    concepts_dir.mkdir(parents=True, exist_ok=True)

    # Note 1 references [[Qdrant Optimization]]
    note1 = daily_dir / "2026-08-10.md"
    note1.write_text(
        "---\ntype: episodic\n---\n# Architecture Sync\nDiscussed [[Qdrant Optimization]] settings."
    )

    # Note 2 also references [[Qdrant Optimization]]
    note2 = daily_dir / "2026-08-11.md"
    note2.write_text(
        "---\ntype: episodic\n---\n# Benchmarks\nVerified [[Qdrant Optimization]] performance."
    )

    promoted = distiller.promote_referenced_entities(tmp_path)
    assert "Qdrant Optimization" in promoted

    # Check that Concepts/Qdrant Optimization.md was created
    concept_file = concepts_dir / "Qdrant Optimization.md"
    assert concept_file.exists()
    content = concept_file.read_text()
    assert "type: semantic" in content
    assert "[[Qdrant Optimization]]" in content
    assert "2026-08-10" in content
    assert "2026-08-11" in content
