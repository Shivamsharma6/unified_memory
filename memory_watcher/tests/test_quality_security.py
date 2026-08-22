import pytest
from pathlib import Path
from fastapi import HTTPException

try:
    from api.routers.quality import QualityRequest, memory_quality, batch_quality
except ImportError:
    from memory_watcher.api.routers.quality import QualityRequest, memory_quality, batch_quality


@pytest.mark.asyncio
async def test_memory_quality_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    # Attacking with traversal
    req = QualityRequest(path="../../../../etc/passwd")

    with pytest.raises(HTTPException) as exc_info:
        await memory_quality(req)

    assert exc_info.value.status_code == 400
    assert "outside the memory vault" in exc_info.value.detail


@pytest.mark.asyncio
async def test_batch_quality_handles_path_traversal_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    res = await batch_quality(["../../../../etc/shadow", "non_existent.md"])
    assert len(res["results"]) == 2
    assert "invalid_path" in res["results"][0]["error"]
    assert "not_found" in res["results"][1]["error"]
