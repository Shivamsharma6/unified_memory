import pytest
from pathlib import Path

try:
    from intelligence.reflection import MemoryReflector
    from llm.provider import LLMConfig
except ImportError:
    from memory_watcher.intelligence.reflection import MemoryReflector
    from memory_watcher.llm.provider import LLMConfig


@pytest.mark.asyncio
async def test_reflect_and_persist_writes_file_and_extracts_insights(tmp_path):
    summaries_dir = tmp_path / "AI" / "Summaries"
    summaries_dir.mkdir(parents=True)
    identity_dir = tmp_path / "Identity"
    identity_dir.mkdir()

    memories = [
        {
            "content": "# Daily\nWorked on [[Qdrant]] and [[PostgreSQL]] vector sync. Shivam prefers concise python code.",
            "source_file": "2026-06-01-Sync.md",
        }
    ]

    config = LLMConfig(provider="mock", model="test")
    reflector = MemoryReflector(llm_config=config)
    result = await reflector.reflect_and_persist(memories, vault_path=str(tmp_path))

    # Verify reflection was generated and saved to AI/Summaries/
    saved_files = list(summaries_dir.glob("*.md"))
    assert len(saved_files) == 1
    content = saved_files[0].read_text()
    assert "type: reflection" in content
    assert "Quality Assessment" in content or "Quality Score" in content or "Recommendations" in content
    assert result.get("status") == "success" or "quality_score" in result
