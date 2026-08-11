#!/usr/bin/env python3
"""Migrate, reconcile, drain, and audit the UAMS control plane."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml


WATCHER_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = WATCHER_ROOT.parent
sys.path.insert(0, str(WATCHER_ROOT))

from api.readiness import assess_readiness
from api.retrieval.reranker import CrossEncoderReranker
from embeddings.generator import EmbeddingGenerator
from models.memory_record import atomic_write, parse_memory, split_frontmatter
from pipelines.reconciliation import Reconciler
from pipelines.vector_worker import VectorWorker
from storage.postgres_store import PostgresStore
from storage.qdrant_store import QdrantStore


def write_memory_ids(vault_root: str | Path) -> list[str]:
    """Atomically add deterministic IDs to legacy notes; never run implicitly."""

    root = Path(vault_root).resolve()
    changed = []
    for path in Reconciler(root, store=None).iter_memory_paths():
        content = path.read_text(encoding="utf-8")
        metadata, body = split_frontmatter(content)
        if metadata.get("memory_id"):
            continue
        record = parse_memory(path, content, vault_root=root)
        now = datetime.now(timezone.utc).isoformat()
        managed = {
            "memory_id": str(record.memory_id),
            "type": metadata.get("type", record.memory_type),
            "status": metadata.get("status", "active"),
            "aliases": metadata.get("aliases", []),
            "tags": metadata.get("tags", []),
            "entities": metadata.get("entities", []),
            "timestamps": metadata.get(
                "timestamps",
                {"created": metadata.get("date", now), "updated": metadata.get("updated", now)},
            ),
        }
        for key, value in metadata.items():
            if key not in managed:
                managed[key] = value
        rendered = yaml.safe_dump(managed, sort_keys=False, allow_unicode=True).strip()
        atomic_write(path, f"---\n{rendered}\n---\n{body.strip()}\n")
        changed.append(path.relative_to(root).as_posix())
    return changed


async def run_migration(args) -> dict:
    root = Path(args.vault).resolve()
    store = PostgresStore()
    await store.open()
    try:
        migrations = await store.migrate()
        report = {"migrations": migrations, "vault": str(root)}
        if args.schema_only:
            return report
        report["memory_ids_written"] = write_memory_ids(root) if args.write_memory_ids else []
        report["reconciliation"] = (await Reconciler(root, store).scan()).__dict__

        vectors = QdrantStore()
        await vectors.initialize_v2_collection()
        report["vector_commands_requeued"] = await store.requeue_failed_vector_commands()
        embedder = EmbeddingGenerator()
        worker = VectorWorker(store, vectors, embedder, batch_size=10)
        deadline = time.monotonic() + args.drain_timeout
        processed = 0
        while time.monotonic() < deadline:
            processed += await worker.run_once()
            metrics = await store.readiness_metrics()
            if metrics["pending_outbox"] == 0:
                break
            await asyncio.sleep(0.5)
        report["vector_commands_processed"] = processed
        report["readiness"] = await assess_readiness(
            root,
            store,
            vectors,
            embedder,
            CrossEncoderReranker(),
        )
        return report
    finally:
        await store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", default=str(VAULT_ROOT))
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--write-memory-ids", action="store_true")
    parser.add_argument("--drain-timeout", type=float, default=120.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = asyncio.run(run_migration(args))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Applied migrations: {report['migrations'] or 'none'}")
        if not args.schema_only:
            reconciliation = report["reconciliation"]
            print(
                "Reconciliation: "
                f"discovered={reconciliation['discovered']} "
                f"staged={reconciliation['staged']} "
                f"failed={reconciliation['failed']} "
                f"deleted={reconciliation['deleted']}"
            )
            print(f"Vector commands processed: {report['vector_commands_processed']}")
            print(f"Vector commands requeued: {report['vector_commands_requeued']}")
            print(f"Ready: {report['readiness']['ready']}")
            print(f"Drift: {report['readiness']['drift']['total']}")
    readiness = report.get("readiness")
    return 0 if readiness is None or readiness["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
