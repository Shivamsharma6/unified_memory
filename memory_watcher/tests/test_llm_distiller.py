import pytest
import sys
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.distiller import MemoryDistiller
from llm.provider import LLMConfig


@pytest.fixture
def vault_with_daily(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()
    tasks = tmp_path / "Tasks"
    tasks.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()

    note = daily / "2026-06-01-Test-Work.md"
    note.write_text("""---
type: episodic
date: 2026-06-01
tags: ["#testing"]
---

# Test Work Session

Today I worked on the [[Qdrant]] integration. The [[Embedding Generator]] was producing wrong vectors.

## Error
Got a ConnectionRefused error when connecting to Qdrant on port 6333.

## Fix
Started the Qdrant container with `docker compose up -d`. Verified with health check endpoint.

## Decision
Chose to use fastembed for local embeddings instead of API calls to reduce latency.
""")
    return tmp_path


@pytest.mark.asyncio
async def test_llm_summary_generation(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(str(vault_with_daily), llm_config=config)
    daily_file = vault_with_daily / "Daily" / "2026-06-01-Test-Work.md"
    summary = await distiller._generate_summary_llm(daily_file.read_text())
    assert isinstance(summary, str)
    assert len(summary) > 20


@pytest.mark.asyncio
async def test_llm_lesson_extraction(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(str(vault_with_daily), llm_config=config)
    content = (vault_with_daily / "Daily" / "2026-06-01-Test-Work.md").read_text()
    lessons = await distiller._extract_lessons_llm(content)
    assert isinstance(lessons, list)
    assert len(lessons) > 0
    assert all(isinstance(l, str) for l in lessons)


@pytest.mark.asyncio
async def test_distill_cycle_uses_llm(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(
        str(vault_with_daily),
        llm_config=config,
        now=lambda: datetime(2026, 6, 5),
    )
    await distiller.distill_cycle()
    daily_file = vault_with_daily / "Daily" / "2026-06-01-Test-Work.md"
    content = daily_file.read_text()
    assert "lifecycle" in content
