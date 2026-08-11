import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.postgres_store import PostgresConfig, migration_paths


def test_postgres_config_redacts_password(monkeypatch):
    monkeypatch.setenv("UAMS_POSTGRES_PASSWORD", "secret")

    config = PostgresConfig.from_env()

    assert config.host == "127.0.0.1"
    assert "secret" not in repr(config)


def test_migrations_are_ordered():
    assert [path.name for path in migration_paths()] == [
        "001_control_plane.sql",
        "002_projection_lifecycle.sql",
        "003_reconciliation_failure_paths.sql",
    ]
