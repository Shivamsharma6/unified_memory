import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

try:
    from api.models import RememberRequest
    from api.memory_writer import write_memory
except ImportError:
    from memory_watcher.api.models import RememberRequest
    from memory_watcher.api.memory_writer import write_memory


def test_write_memory_suppresses_exact_duplicate_noop(tmp_path):
    req1 = RememberRequest(
        text="# Python Conventions\nWe use black and flake8 for formatting.",
        category="procedural",
    )
    res1 = write_memory(req1, vault_root=tmp_path)
    assert res1.decision == "ADD"

    # Second write of the exact same content
    req2 = RememberRequest(
        text="# Python Conventions\nWe use black and flake8 for formatting.",
        category="procedural",
    )
    res2 = write_memory(req2, vault_root=tmp_path)
    assert res2.decision == "NOOP"
    assert res2.memory_id == res1.memory_id
    assert res2.path == res1.path

    # Verify only 1 file exists
    tasks_dir = tmp_path / "Tasks"
    assert len(list(tasks_dir.glob("*.md"))) == 1


def test_write_memory_updates_existing_note(tmp_path):
    req1 = RememberRequest(
        text="# PostgreSQL Configuration\nDefault port is 5432.",
        category="semantic",
    )
    res1 = write_memory(req1, vault_root=tmp_path)
    assert res1.decision == "ADD"

    # Update with new fact
    req2 = RememberRequest(
        text="# PostgreSQL Configuration\nDefault port is 5432.\nAdded SSL mode verify-full requirement.",
        category="semantic",
    )
    res2 = write_memory(req2, vault_root=tmp_path)
    assert res2.decision == "UPDATE"
    assert res2.memory_id == res1.memory_id

    # Verify content in file contains the update
    content = res1.path.read_text()
    assert "SSL mode verify-full" in content
