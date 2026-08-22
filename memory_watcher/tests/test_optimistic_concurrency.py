import hashlib
import pytest
from pathlib import Path
from fastapi import HTTPException

try:
    from api.routers.memory_edit import EditRequest, edit_memory
except ImportError:
    from memory_watcher.api.routers.memory_edit import EditRequest, edit_memory


@pytest.mark.asyncio
async def test_edit_memory_succeeds_with_matching_expected_hash(tmp_path, monkeypatch):
    test_file = tmp_path / "Concepts" / "Concurrency.md"
    test_file.parent.mkdir(parents=True)
    content = "---\ntype: semantic\n---\n# Concurrency Note\nOriginal text content."
    test_file.write_text(content, encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)

    req = EditRequest(
        path="Concepts/Concurrency.md",
        old_text="Original text content.",
        new_text="Updated text content.",
        expected_hash=content_hash,
    )

    res = await edit_memory(req)
    assert res["status"] == "success"
    assert "Updated text content." in test_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_edit_memory_rejects_with_409_conflict_on_hash_mismatch(tmp_path, monkeypatch):
    test_file = tmp_path / "Concepts" / "Concurrency.md"
    test_file.parent.mkdir(parents=True)
    content = "---\ntype: semantic\n---\n# Concurrency Note\nOriginal text content."
    test_file.write_text(content, encoding="utf-8")

    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)

    req = EditRequest(
        path="Concepts/Concurrency.md",
        old_text="Original text content.",
        new_text="Conflicting text content.",
        expected_hash="stale_hash_from_older_read_1234567890",
    )

    with pytest.raises(HTTPException) as exc_info:
        await edit_memory(req)

    assert exc_info.value.status_code == 409
    assert "Conflict" in exc_info.value.detail
