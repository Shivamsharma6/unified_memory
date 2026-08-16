"""Deep readiness and projection-drift assessment."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models.document import Chunk, ChunkMetadata, Document
from models.memory_record import parse_memory
from pipelines.reconciliation import Reconciler


async def _embedding_search_probe(embedder, vector_store):
    document = Document(
        path="readiness-probe",
        raw_content="unified memory readiness probe",
        chunks=[
            Chunk(
                content="unified memory readiness probe",
                metadata=ChunkMetadata(
                    chunk_id="readiness-probe",
                    source_file="readiness-probe",
                ),
            )
        ],
    )
    embedded = await embedder.embed(document)
    vector = embedded.chunks[0].embedding
    if vector is None:
        raise RuntimeError("Embedding provider returned no probe vector")
    return await vector_store.readiness_probe(vector)


def _markdown_state(vault_root: Path) -> tuple[set, list[str]]:
    memory_ids = set()
    malformed = []
    reconciler = Reconciler(vault_root, store=None)
    for path in reconciler.iter_memory_paths():
        try:
            record = parse_memory(path, path.read_text(encoding="utf-8"), vault_root=vault_root)
            memory_ids.add(record.memory_id)
        except Exception as error:
            malformed.append(f"{path.relative_to(vault_root).as_posix()}: {error}")
    return memory_ids, malformed


async def assess_lightweight_readiness(
    control_store,
    vector_store,
) -> dict:
    """Fast liveness/readiness assessment checking connection pools and queue backlogs (<10ms)."""
    components = {}
    pg_ok = False
    jobs = {
        "pending_jobs": 0,
        "failed_jobs": 0,
        "pending_outbox": 0,
        "failed_outbox": 0,
        "oldest_pending_seconds": 0.0,
    }

    try:
        if await control_store.ping():
            components["postgresql"] = {"status": "ok"}
            pg_ok = True
            jobs = await control_store.readiness_metrics()
        else:
            components["postgresql"] = {"status": "unavailable", "detail": "ping returned false"}
    except Exception as error:
        components["postgresql"] = {"status": "unavailable", "detail": str(error)}

    qdrant_ok = False
    try:
        collection_exists = await vector_store.client.collection_exists(vector_store.v2_collection)
        if collection_exists:
            components["qdrant"] = {"status": "ok", "collection": vector_store.v2_collection}
            qdrant_ok = True
        else:
            components["qdrant"] = {
                "status": "unavailable",
                "detail": f"collection {vector_store.v2_collection} does not exist",
            }
    except Exception as error:
        components["qdrant"] = {"status": "unavailable", "detail": str(error)}

    ready = pg_ok and qdrant_ok and jobs.get("failed_outbox", 0) == 0
    return {
        "ready": ready,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
        "jobs": jobs,
    }


async def assess_deep_projection_drift(
    vault_root: str | Path,
    control_store,
    vector_store,
    embedder,
    reranker,
) -> dict:
    root = Path(vault_root).resolve()
    components = {}

    try:
        if not await control_store.ping():
            raise RuntimeError("readiness query returned false")
        components["postgresql"] = {"status": "ok"}
        jobs = await control_store.readiness_metrics()
        database_state = await control_store.projection_state()
    except Exception as error:
        components["postgresql"] = {"status": "unavailable", "detail": str(error)}
        jobs = {
            "pending_jobs": 0,
            "failed_jobs": 1,
            "pending_outbox": 0,
            "failed_outbox": 0,
            "oldest_pending_seconds": None,
        }
        database_state = {"document_ids": set(), "current_pairs": set()}

    try:
        vector_state = await vector_store.projection_state()
        components["qdrant"] = {
            "status": "ok",
            "collection": "memory_chunks_v2",
            "points": vector_state.get("points", 0),
        }
    except Exception as error:
        components["qdrant"] = {"status": "unavailable", "detail": str(error)}
        vector_state = {"pairs": set(), "points": 0}

    try:
        probe = await _embedding_search_probe(embedder, vector_store)
        components["embedding_search_probe"] = {"status": "ok", **probe}
    except Exception as error:
        components["embedding_search_probe"] = {
            "status": "unavailable",
            "detail": str(error),
        }

    try:
        await reranker._ensure_model()
        components["reranker"] = {
            "status": "ok",
            "mode": "cross_encoder" if reranker._available else "heuristic",
            "model": getattr(reranker, "model_name", None),
        }
    except Exception as error:
        components["reranker"] = {
            "status": "unavailable",
            "mode": "unavailable",
            "detail": str(error),
        }

    markdown_ids, malformed = _markdown_state(root)
    database_ids = set(database_state.get("document_ids", set()))
    expected_pairs = set(database_state.get("current_pairs", set()))
    qdrant_pairs = set(vector_state.get("pairs", set()))
    expected_point_ids = set(database_state.get("point_ids", set()))
    qdrant_point_ids = set(vector_state.get("point_ids", set()))
    expected_points = database_state.get("expected_points")
    qdrant_points = vector_state.get("points", 0)
    point_delta = abs(expected_points - qdrant_points) if expected_points is not None else 0
    drift = {
        "markdown_missing_in_postgres": len(markdown_ids - database_ids),
        "postgres_missing_markdown": len(database_ids - markdown_ids),
        "qdrant_missing": len(expected_pairs - qdrant_pairs),
        "qdrant_stale": len(qdrant_pairs - expected_pairs),
        "qdrant_missing_points": len(expected_point_ids - qdrant_point_ids),
        "qdrant_stale_points": len(qdrant_point_ids - expected_point_ids),
        "point_count_delta": point_delta,
        "malformed_markdown": len(malformed),
        "malformed_details": malformed[:20],
    }
    drift["total"] = sum(
        drift[key]
        for key in (
            "markdown_missing_in_postgres",
            "postgres_missing_markdown",
            "qdrant_missing",
            "qdrant_stale",
            "qdrant_missing_points",
            "qdrant_stale_points",
            "point_count_delta",
            "malformed_markdown",
        )
    )
    required_components_ok = all(
        components[name]["status"] == "ok"
        for name in ("postgresql", "qdrant", "embedding_search_probe")
    )
    queues_clear = all(
        jobs.get(key, 0) == 0
        for key in ("pending_jobs", "failed_jobs", "pending_outbox", "failed_outbox")
    )
    return {
        "ready": required_components_ok and queues_clear and drift["total"] == 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
        "jobs": jobs,
        "drift": drift,
    }


# Backwards compatibility alias
assess_readiness = assess_deep_projection_drift

