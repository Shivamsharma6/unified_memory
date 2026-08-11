import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.models import RememberRequest
from api import memory_writer
from models.memory_record import parse_memory, resolve_vault_path


def test_existing_note_gets_deterministic_memory_id(tmp_path):
    path = tmp_path / "Concepts" / "Qdrant.md"
    content = "---\ntype: semantic\n---\n# Qdrant\n"

    first = parse_memory(path, content, vault_root=tmp_path)
    second = parse_memory(path, content, vault_root=tmp_path)

    assert first.memory_id == second.memory_id


def test_workflow_status_is_preserved_for_lifecycle_mapping(tmp_path):
    path = tmp_path / "Projects" / "Approved Design.md"
    content = "---\ntype: semantic\nstatus: approved\n---\n# Approved Design\n"

    record = parse_memory(path, content, vault_root=tmp_path)

    assert record.status == "approved"


def test_nested_yaml_wikilink_lists_are_flattened(tmp_path):
    path = tmp_path / "Concepts" / "WiFi Sensing.md"
    content = """---
type: concept
entities:
  - [[ESP32]]
---
# WiFi Sensing
"""

    record = parse_memory(path, content, vault_root=tmp_path)

    assert record.entities == ["ESP32"]


def test_resolve_vault_path_rejects_escape(tmp_path):
    try:
        resolve_vault_path(tmp_path, "../outside.md")
    except ValueError as error:
        assert "outside" in str(error)
    else:
        raise AssertionError("Expected a vault path escape to be rejected")


def test_parallel_writes_use_unique_names_and_managed_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_writer, "VAULT_ROOT", tmp_path)
    request = RememberRequest(
        text="Fixed a stale vector cleanup bug in [[Qdrant]].",
        category="episodic",
        tags=["bug-fix"],
        source_agent="test-agent",
        project="Unified Memory",
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: memory_writer.write_memory(request), range(8)))

    paths = [result.path for result in results]
    assert len(set(paths)) == 8
    assert all(path.exists() for path in paths)
    assert all("fixed-a-stale-vector-cleanup-bug" in path.name for path in paths)

    for result in results:
        text = result.path.read_text(encoding="utf-8")
        metadata = yaml.safe_load(text.split("---", 2)[1])
        assert str(metadata["memory_id"]) == str(result.memory_id)
        assert metadata["type"] == "episodic"
        assert metadata["status"] == "active"
        assert metadata["aliases"] == []
        assert metadata["entities"] == []
        assert metadata["tags"] == ["#bug-fix"]
        assert metadata["source_agent"] == "test-agent"
        assert metadata["project"] == "Unified Memory"
        assert metadata["timestamps"]["created"]
        assert metadata["timestamps"]["updated"]
        assert result.index_status == "pending"
