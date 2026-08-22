import pytest
from pathlib import Path

try:
    from api.routers.validation import validate_entire_vault
except ImportError:
    from memory_watcher.api.routers.validation import validate_entire_vault


@pytest.mark.asyncio
async def test_validate_entire_vault_bounds_scan_with_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    # Create 5 test notes
    concepts = tmp_path / "Concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (concepts / f"note_{i}.md").write_text(
            f"---\ntype: semantic\n---\n# Note {i}\nContent {i}\n",
            encoding="utf-8",
        )

    # Validate with limit 2
    summary = await validate_entire_vault(limit=2)
    assert summary.total_scanned == 2

    # Validate default
    summary_all = await validate_entire_vault(limit=100)
    assert summary_all.total_scanned == 5
