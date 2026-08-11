"""PostgreSQL connection lifecycle and schema migrations for UAMS."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


_MIGRATION_RE = re.compile(r"^(?P<version>\d+)_.*\.sql$")
_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class PostgresConfig:
    """Runtime PostgreSQL settings with secret-safe diagnostics."""

    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "uams"
    user: str = "uams"
    password: str = field(default="uams-local-only", repr=False)
    min_pool_size: int = 1
    max_pool_size: int = 10
    connect_timeout: int = 5

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            host=os.getenv("UAMS_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("UAMS_POSTGRES_PORT", "5432")),
            database=os.getenv("UAMS_POSTGRES_DB", "uams"),
            user=os.getenv("UAMS_POSTGRES_USER", "uams"),
            password=os.getenv("UAMS_POSTGRES_PASSWORD", "uams-local-only"),
            min_pool_size=int(os.getenv("UAMS_POSTGRES_POOL_MIN", "1")),
            max_pool_size=int(os.getenv("UAMS_POSTGRES_POOL_MAX", "10")),
            connect_timeout=int(os.getenv("UAMS_POSTGRES_CONNECT_TIMEOUT", "5")),
        )

    @property
    def conninfo(self) -> str:
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
            connect_timeout=self.connect_timeout,
        )


def migration_paths(directory: Path | None = None) -> list[Path]:
    """Return numbered SQL migrations in deterministic version order."""

    root = directory or _MIGRATIONS_DIR
    paths = [path for path in root.glob("*.sql") if _MIGRATION_RE.match(path.name)]
    return sorted(paths, key=lambda path: int(_MIGRATION_RE.match(path.name).group("version")))


class PostgresStore:
    """Own the async pool and apply immutable, checksummed migrations."""

    def __init__(
        self,
        config: PostgresConfig | None = None,
        *,
        pool_factory: Callable[..., AsyncConnectionPool] = AsyncConnectionPool,
    ) -> None:
        self.config = config or PostgresConfig.from_env()
        self.pool = pool_factory(
            conninfo=self.config.conninfo,
            min_size=self.config.min_pool_size,
            max_size=self.config.max_pool_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        await self.pool.open(wait=True)

    async def close(self) -> None:
        await self.pool.close()

    async def ping(self) -> bool:
        async with self.pool.connection() as connection:
            result = await connection.execute("SELECT 1 AS ok")
            row = await result.fetchone()
            return bool(row and row["ok"] == 1)

    async def migrate(self, directory: Path | None = None) -> list[str]:
        """Apply pending migrations while preventing concurrent runners."""

        applied: list[str] = []
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("uams:schema-migrations",),
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version bigint PRIMARY KEY,
                        filename text NOT NULL UNIQUE,
                        checksum char(64) NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )

                for path in migration_paths(directory):
                    match = _MIGRATION_RE.match(path.name)
                    version = int(match.group("version"))
                    sql = path.read_text(encoding="utf-8")
                    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                    result = await connection.execute(
                        "SELECT checksum FROM schema_migrations WHERE version = %s",
                        (version,),
                    )
                    row = await result.fetchone()
                    if row:
                        if row["checksum"] != checksum:
                            raise RuntimeError(f"Migration {path.name} changed after application")
                        continue

                    await connection.execute(sql, prepare=False)
                    await connection.execute(
                        """
                        INSERT INTO schema_migrations (version, filename, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (version, path.name, checksum),
                    )
                    applied.append(path.name)

        return applied
