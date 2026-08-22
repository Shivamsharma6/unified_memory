import os
from pathlib import Path
import pytest

try:
    from models.memory_record import get_vault_root, resolve_vault_path
    from api.models import RememberRequest
    from api.memory_writer import write_memory
    from pipelines.reconciliation import Reconciler
except ImportError:
    from memory_watcher.models.memory_record import get_vault_root, resolve_vault_path
    from memory_watcher.api.models import RememberRequest
    from memory_watcher.api.memory_writer import write_memory
    from memory_watcher.pipelines.reconciliation import Reconciler


def test_get_vault_root_prioritizes_explicit_then_env_then_default(tmp_path, monkeypatch):
    custom_vault_1 = tmp_path / "vault_1"
    custom_vault_2 = tmp_path / "vault_2"
    custom_vault_1.mkdir()
    custom_vault_2.mkdir()

    # 1. Explicit root overrides everything
    monkeypatch.setenv("UAMS_VAULT_PATH", str(custom_vault_1))
    assert get_vault_root(custom_vault_2) == custom_vault_2.resolve()

    # 2. Environment variable is respected when no explicit path is passed
    assert get_vault_root() == custom_vault_1.resolve()

    # 3. Default fallback when unset
    monkeypatch.delenv("UAMS_VAULT_PATH", raising=False)
    default_root = get_vault_root()
    assert default_root.exists()


def test_write_memory_and_reconciler_honor_uams_vault_path(tmp_path, monkeypatch):
    custom_vault = tmp_path / "custom_agent_vault"
    custom_vault.mkdir()
    monkeypatch.setenv("UAMS_VAULT_PATH", str(custom_vault))

    req = RememberRequest(
        text="# Custom Vault Memory\n\nTesting external vault resolution.",
        category="semantic",
        source_agent="Hermes",
    )

    write_result = write_memory(req)
    assert custom_vault in write_result.path.parents or write_result.path.parent.parent == custom_vault
    assert write_result.path.exists()
    assert (custom_vault / write_result.vault_path).exists()


    reconciler = Reconciler(store=None)
    assert reconciler.vault_root == custom_vault.resolve()
    memory_paths = reconciler.iter_memory_paths()
    assert memory_paths[0].name.startswith("custom-vault-memory")
    assert memory_paths[0].suffix == ".md"

