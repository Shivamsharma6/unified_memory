"""Filesystem-to-PostgreSQL reconciliation for authoritative Markdown memory."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chunkers.semantic import SemanticChunker
from graph.extractor import extract_projection
from models.document import Document
from models.memory_record import parse_memory, resolve_vault_path


EXCLUDED_DIRECTORIES = {
    ".git",
    ".superpowers",
    ".uams",
    ".venv",
    "__pycache__",
    "memory_watcher",
    "venv",
}
PROJECTION_VERSION = 2


def projection_hash(raw_markdown: str, *, version: int = PROJECTION_VERSION) -> str:
    """Fingerprint Markdown together with the derived-projection schema version."""

    payload = f"uams-projection-v{version}\0{raw_markdown}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ReconcileResult:
    status: str
    path: str
    memory_id: uuid.UUID | None = None
    revision_id: uuid.UUID | None = None
    error: str | None = None


@dataclass(frozen=True)
class ScanResult:
    discovered: int
    staged: int
    unchanged: int
    failed: int
    archived: int
    deleted: int


class Reconciler:
    """Rebuild derived state from Markdown without trusting watcher delivery."""

    def __init__(self, vault_root: str | Path, store: Any) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = store
        self.chunker = SemanticChunker()
        self._memory_locks: dict[uuid.UUID, asyncio.Lock] = {}
        self.is_scanning: bool = False
        self.last_scan_result: ScanResult | None = None

    def iter_memory_paths(self) -> list[Path]:
        paths: list[Path] = []
        for root, directories, filenames in os.walk(self.vault_root):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in EXCLUDED_DIRECTORIES and not directory.startswith(".")
            )
            for filename in sorted(filenames):
                if not filename.endswith(".md"):
                    continue
                if ".backup-" in filename or filename.startswith("."):
                    continue
                paths.append(Path(root) / filename)
        return paths

    def _vault_path(self, path: str | Path) -> str:
        resolved = resolve_vault_path(self.vault_root, path)
        return resolved.relative_to(self.vault_root).as_posix()

    @staticmethod
    def _document_status(vault_path: str, record_status: str) -> str:
        if vault_path.startswith("Archive/") or record_status in {"archived", "superseded"}:
            return "archived"
        if record_status == "deleted":
            return "deleted"
        return "active"

    async def _record_failure(self, vault_path: str, error: Exception) -> None:
        try:
            await self.store.record_ingestion_failure(vault_path, error)
        except Exception:
            pass

    async def reconcile_path(
        self,
        path: str | Path,
        *,
        mtime_ns: int | None = None,
        file_size: int | None = None,
    ) -> ReconcileResult:
        try:
            vault_path = self._vault_path(path)
        except ValueError as error:
            return ReconcileResult(status="failed", path=str(path), error=str(error))

        resolved = self.vault_root / vault_path
        if not resolved.exists():
            try:
                memory_id = await self.store.mark_deleted_by_path(vault_path)
                return ReconcileResult(status="deleted", path=vault_path, memory_id=memory_id)
            except Exception as error:
                await self._record_failure(vault_path, error)
                return ReconcileResult(status="failed", path=vault_path, error=str(error))

        try:
            stat = resolved.stat()
            if mtime_ns is None:
                mtime_ns = stat.st_mtime_ns
            if file_size is None:
                file_size = stat.st_size
        except OSError:
            pass

        record = None
        try:
            raw_markdown = resolved.read_text(encoding="utf-8")
            record = parse_memory(resolved, raw_markdown, vault_root=self.vault_root)
        except Exception as error:
            await self._record_failure(vault_path, error)
            return ReconcileResult(status="failed", path=vault_path, error=str(error))

        lock = self._memory_locks.setdefault(record.memory_id, asyncio.Lock())
        async with lock:
            try:
                if not resolved.exists():
                    memory_id = await self.store.mark_deleted_by_path(vault_path)
                    return ReconcileResult(status="deleted", path=vault_path, memory_id=memory_id)

                raw_markdown = resolved.read_text(encoding="utf-8")
                record = parse_memory(resolved, raw_markdown, vault_root=self.vault_root)
                content_hash = projection_hash(raw_markdown)
                document = self.chunker.chunk(
                    Document(path=record.vault_path, raw_content=raw_markdown)
                )
                projection = extract_projection(record)
                document_status = self._document_status(record.vault_path, record.status)
                staged = await self.store.stage_revision(
                    record=record,
                    raw_markdown=raw_markdown,
                    content_hash=content_hash,
                    chunks=document.chunks,
                    projection=projection,
                    document_status=document_status,
                    event_type="archive" if document_status == "archived" else "upsert",
                    mtime_ns=mtime_ns,
                    file_size=file_size,
                )
                return ReconcileResult(
                    status="staged" if staged.created else "unchanged",
                    path=record.vault_path,
                    memory_id=record.memory_id,
                    revision_id=staged.revision_id,
                )
            except Exception as error:
                await self._record_failure(vault_path, error)
                return ReconcileResult(
                    status="failed",
                    path=vault_path,
                    memory_id=record.memory_id,
                    error=str(error),
                )

    async def scan(self, *, force: bool = False) -> ScanResult:
        self.is_scanning = True
        try:
            paths = self.iter_memory_paths()
            cached_stats = {}
            if not force and self.store and hasattr(self.store, "get_document_file_stats"):
                try:
                    cached_stats = await self.store.get_document_file_stats()
                except Exception:
                    cached_stats = {}

            results: list[ReconcileResult] = []
            for path in paths:
                vault_path = self._vault_path(path)
                try:
                    stat = path.stat()
                except OSError:
                    results.append(await self.reconcile_path(path))
                    continue

                cached = cached_stats.get(vault_path)
                if (
                    cached
                    and cached["status"] != "deleted"
                    and cached["mtime_ns"] is not None
                    and cached["mtime_ns"] == stat.st_mtime_ns
                    and cached["file_size"] is not None
                    and cached["file_size"] == stat.st_size
                ):
                    results.append(
                        ReconcileResult(
                            status="unchanged",
                            path=vault_path,
                            memory_id=cached["memory_id"],
                            revision_id=cached["current_revision_id"],
                        )
                    )
                else:
                    results.append(
                        await self.reconcile_path(
                            path,
                            mtime_ns=stat.st_mtime_ns,
                            file_size=stat.st_size,
                        )
                    )

            seen = {result.memory_id for result in results if result.memory_id is not None}
            unidentified_failure = any(
                result.status == "failed" and result.memory_id is None for result in results
            )
            deleted_ids = [] if unidentified_failure or not self.store else await self.store.mark_missing_documents(seen)
            scan_res = ScanResult(
                discovered=len(paths),
                staged=sum(result.status == "staged" for result in results),
                unchanged=sum(result.status == "unchanged" for result in results),
                failed=sum(result.status == "failed" for result in results),
                archived=sum(
                    result.status in {"staged", "unchanged"} and result.path.startswith("Archive/")
                    for result in results
                ),
                deleted=len(deleted_ids),
            )
            self.last_scan_result = scan_res
            return scan_res
        finally:
            self.is_scanning = False

    async def startup_reconcile(self) -> ScanResult:
        return await self.scan()

