import pytest
from pathlib import Path

try:
    from memory_types.consolidation import MemoryConsolidator, ConsolidationResult
    from memory_types.episodic import EpisodicMemory, ContextData, OutcomeData, EmotionalState
except ImportError:
    from memory_watcher.memory_types.consolidation import MemoryConsolidator, ConsolidationResult
    from memory_watcher.memory_types.episodic import EpisodicMemory, ContextData, OutcomeData, EmotionalState


def test_memories_pruned_count_is_accurate():
    consolidator = MemoryConsolidator()
    m1 = EpisodicMemory(
        event_type="meeting",
        summary="Architecture sync 1",
        participants=["Shivam", "Hermes"],
        emotional_state=EmotionalState(frustration=0.1, satisfaction=0.8),
        importance=0.8,
        context=ContextData(platform="cli"),
        outcome=OutcomeData(lessons_learned=["Lesson A"]),
    )
    m2 = EpisodicMemory(
        event_type="meeting",
        summary="Architecture sync 2",
        participants=["Shivam", "Hermes"],
        emotional_state=EmotionalState(frustration=0.1, satisfaction=0.5),
        importance=0.4,
        context=ContextData(platform="cli"),
        outcome=OutcomeData(lessons_learned=["Lesson B"]),
    )
    result = consolidator.consolidate([m1, m2])
    assert result.memories_processed == 2
    assert result.memories_pruned == 1
    assert result.memories_retained == 1
    assert result.redundancy_reduced == 1


def test_consolidate_vault_writes_concepts(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()

    for i in range(3):
        note = daily / f"2026-06-0{i+1}-Sync.md"
        note.write_text(f"""---
type: episodic
date: 2026-06-0{i+1}
---
# Sync {i+1}
Discussed [[Knowledge Graph]] and [[Qdrant]] architecture with [[Shivam]].
- Lessons learned: Keep vectors normalized.
""")

    consolidator = MemoryConsolidator(vault_path=str(tmp_path))
    result = consolidator.consolidate_vault()
    assert result.memories_processed == 3
    concept_files = list(concepts.glob("*.md"))
    assert len(concept_files) >= 1
    created_concept = concept_files[0].read_text()
    assert "type: semantic" in created_concept
    assert "[[Shivam]]" in created_concept or "Knowledge Graph" in created_concept
