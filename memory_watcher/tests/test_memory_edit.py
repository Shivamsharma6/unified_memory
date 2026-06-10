# tests/test_memory_edit.py
import sys
import pytest
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from api.routers.memory_edit import edit_memory, delete_memory, add_link, EditRequest, DeleteRequest, AddLinkRequest


def _create_test_file(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    note = daily / "test-note.md"
    note.write_text("---\ntype: test\n---\n# Test\nOriginal content here.\n")
    return note


@pytest.mark.asyncio
async def test_edit_memory(tmp_path, monkeypatch):
    note = _create_test_file(tmp_path)
    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)
    request = EditRequest(path="Daily/test-note.md", old_text="Original", new_text="Updated")
    result = await edit_memory(request)
    assert result["status"] == "success"
    assert "Updated" in note.read_text()


@pytest.mark.asyncio
async def test_delete_memory(tmp_path, monkeypatch):
    note = _create_test_file(tmp_path)
    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)
    request = DeleteRequest(path="Daily/test-note.md")
    result = await delete_memory(request)
    assert result["status"] == "success"
    assert not note.exists()
    assert (tmp_path / "Archive" / "test-note.md").exists()


@pytest.mark.asyncio
async def test_add_link(tmp_path, monkeypatch):
    note = _create_test_file(tmp_path)
    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)
    request = AddLinkRequest(path="Daily/test-note.md", entity="NewEntity")
    result = await add_link(request)
    assert result["status"] == "success"
    assert "[[NewEntity]]" in note.read_text()


@pytest.mark.asyncio
async def test_add_link_noop(tmp_path, monkeypatch):
    note = _create_test_file(tmp_path)
    note.write_text("---\ntype: test\n---\n# Test\nSee [[ExistingEntity]].\n")
    monkeypatch.setattr("api.routers.memory_edit._vault_root", lambda: tmp_path)
    request = AddLinkRequest(path="Daily/test-note.md", entity="ExistingEntity")
    result = await add_link(request)
    assert result["status"] == "noop"