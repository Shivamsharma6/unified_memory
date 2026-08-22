import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

try:
    from api.models import RememberRequest
    from api.main import remember, app
    from api.memory_writer import write_memory
except ImportError:
    from memory_watcher.api.models import RememberRequest
    from memory_watcher.api.main import remember, app
    from memory_watcher.api.memory_writer import write_memory


@pytest.mark.asyncio
async def test_remember_with_distill_extracts_facts_and_wikilinks(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))
    req = RememberRequest(
        text="Had a great session with Shivam Sharma discussing Qdrant vector database scaling. We decided to use Cosine distance.",
        category="episodic",
        distill=True,
    )

    mock_distilled = {
        "title": "Qdrant Vector Database Scaling",
        "summary": "Discussed Qdrant vector scaling with Shivam Sharma and decided on Cosine distance.",
        "category": "episodic",
        "entities": ["Shivam Sharma", "Qdrant"],
        "tags": ["architecture", "vector_db"],
        "facts": ["Decided to use Cosine distance for vectors"],
        "action": "ADD",
    }

    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = mock_distilled

    with patch("api.main._get_llm", return_value=mock_llm):
        res = await remember(req)
        assert res["status"] == "success"
        written_path = tmp_path / res["path"]
        assert written_path.exists()
        content = written_path.read_text()
        assert "type: episodic" in content
        assert "[[Shivam Sharma]]" in content
        assert "[[Qdrant]]" in content
        assert "Cosine distance" in content

