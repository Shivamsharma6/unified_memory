import pytest
from pathlib import Path
from fastapi import HTTPException

try:
    from api.routers.memory_edit import DeleteRequest, delete_memory
except ImportError:
    from memory_watcher.api.routers.memory_edit import DeleteRequest, delete_memory


@pytest.mark.asyncio
async def test_delete_memory_creates_durable_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    # Create a note in Concepts
    concepts = tmp_path / "Concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    note = concepts / "old-concept.md"
    note.write_text("# Old Concept\n\nImportant knowledge.", encoding="utf-8")

    req = DeleteRequest(path="Concepts/old-concept.md", reason="deprecated")
    result = await delete_memory(req)

    assert result["status"] == "success"
    assert "backup" in result
    assert not note.exists()
    assert (tmp_path / result["archived_to"]).exists()
    assert (tmp_path / result["backup"]).exists()
    assert "Important knowledge." in (tmp_path / result["backup"]).read_text(encoding="utf-8")
