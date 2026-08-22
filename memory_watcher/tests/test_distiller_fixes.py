import pytest
from datetime import datetime
from pathlib import Path

try:
    from intelligence.distiller import MemoryDistiller
    from llm.provider import LLMConfig
except ImportError:
    from memory_watcher.intelligence.distiller import MemoryDistiller
    from memory_watcher.llm.provider import LLMConfig


@pytest.mark.asyncio
async def test_distiller_preserves_summary_when_promoted(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    tasks = tmp_path / "Tasks"
    tasks.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()

    # Note that is > 2 days old AND has high importance (eligible for both B and C in same cycle)
    note = daily / "2026-06-01-Important-Work.md"
    note.write_text("""---
type: episodic
date: 2026-06-01
importance: 0.95
---
# Work Session
Crucial error: Docker port collision fixed by changing to 6334.
[[Qdrant]] [[PostgreSQL]] [[Docker]]
""")

    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(
        str(tmp_path),
        llm_config=config,
        now=lambda: datetime(2026, 6, 5),
    )
    await distiller.distill_cycle()

    # Verify daily note still has the distilled summary header and content
    content = note.read_text()
    assert "# Distilled Summary" in content, "Summary was clobbered by pre-summary body!"
    assert "Distilled Summary" in content
    assert "lifecycle: distilled" in content or "lifecycle: summarized" in content


def test_decay_calculation_is_idempotent(tmp_path):
    distiller = MemoryDistiller(str(tmp_path))
    fm = {"importance": 0.8, "base_importance": 0.8}
    content = "Test content [[Entity1]]"

    # Day 30 calculation
    score_day30 = distiller._calculate_importance(fm, content, age_days=30)
    # If fm has the updated score, recalculating day 30 should not decay from the decayed score
    fm["importance"] = score_day30
    score_day30_recalc = distiller._calculate_importance(fm, content, age_days=30)
    assert abs(score_day30 - score_day30_recalc) < 1e-4
