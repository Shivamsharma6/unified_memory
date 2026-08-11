import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import configured_vault_root


def test_watcher_entrypoint_honors_authoritative_vault_environment(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    assert configured_vault_root() == tmp_path.resolve()
