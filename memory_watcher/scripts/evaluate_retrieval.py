#!/usr/bin/env python3
"""Evaluate current-revision retrieval against the committed golden queries."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx


WATCHER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = WATCHER_ROOT.parent
DEFAULT_FIXTURE = WATCHER_ROOT / "tests" / "fixtures" / "retrieval_golden.json"
DEFAULT_REPORT = REPOSITORY_ROOT / ".uams" / "evaluations" / "latest.json"
sys.path.insert(0, str(WATCHER_ROOT))

from api.models import SearchRequest
from api.retrieval.pipeline import RetrievalPipeline
from storage.postgres_store import PostgresStore


def _result_value(result: Any, key: str, default=None):
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def score_case_results(
    case: dict[str, Any],
    results: list[Any],
    *,
    valid_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    """Score one ranked list and independently validate its lifecycle evidence."""

    expected = set(case["expected_sources"])
    sources = [str(_result_value(result, "source_file", "")) for result in results]
    leaks = []
    for result, source in zip(results, sources):
        memory_id = _result_value(result, "memory_id")
        revision_id = _result_value(result, "revision_id")
        if not memory_id or not revision_id:
            leaks.append(f"missing-evidence:{source}")
            continue
        pair = (str(memory_id), str(revision_id))
        if pair not in valid_pairs:
            leaks.append(f"{pair[0]}:{pair[1]}")

    reciprocal_rank = 0.0
    for idx, source in enumerate(sources, start=1):
        if source in expected:
            reciprocal_rank = 1.0 / idx
            break

    return {
        "id": case["id"],
        "query": case.get("query", ""),
        "expected_sources": sorted(expected),
        "sources": sources,
        "hit1": bool(sources and sources[0] in expected),
        "hit5": any(source in expected for source in sources[:5]),
        "reciprocal_rank": reciprocal_rank,
        "historical_leaks": leaks,
    }



async def _valid_pairs(store: PostgresStore, results: list[Any]) -> set[tuple[str, str]]:
    memory_ids = []
    for result in results:
        value = _result_value(result, "memory_id")
        try:
            memory_ids.append(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    pairs = await store.valid_revision_pairs(memory_ids)
    return {(str(memory_id), str(revision_id)) for memory_id, revision_id in pairs}


async def evaluate(
    cases: list[dict[str, Any]],
    search: Callable[[SearchRequest], Awaitable[list[Any]]],
    store: PostgresStore,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    details = []
    for case in cases:
        results = await search(
            SearchRequest(
                query=case["query"],
                limit=limit,
                min_score=0.0,
                compress=False,
                include_historical=False,
            )
        )
        details.append(
            score_case_results(
                case,
                results,
                valid_pairs=await _valid_pairs(store, results),
            )
        )
    total = len(details)
    return {
        "queries": total,
        "hit1": sum(detail["hit1"] for detail in details) / total if total else 0.0,
        "hit5": sum(detail["hit5"] for detail in details) / total if total else 0.0,
        "historical_leaks": sum(
            len(detail["historical_leaks"]) for detail in details
        ),
        "details": details,
    }


async def run(args) -> dict[str, Any]:
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    cases = fixture["queries"]
    store = PostgresStore()
    pipeline = None
    client = None
    if args.api:
        await store.open()
        await store.migrate()
        client = httpx.AsyncClient(base_url=args.api.rstrip("/"), timeout=60.0)

        async def search(request: SearchRequest):
            response = await client.post("/search", json=request.model_dump())
            response.raise_for_status()
            return response.json()["results"]

    else:
        pipeline = RetrievalPipeline(control_store=store)
        await pipeline.initialize()
        if pipeline.hybrid is None:
            raise RuntimeError("PostgreSQL/Qdrant control plane is not initialized")

        async def search(request: SearchRequest):
            return (await pipeline.search(request)).results

    try:
        return await evaluate(cases, search, store, limit=args.limit)
    finally:
        if client is not None:
            await client.aclose()
            await store.close()
        if pipeline is not None:
            await pipeline.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--api")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--require-hit1", type=float, default=0.0)
    parser.add_argument("--require-hit5", type=float, default=0.0)
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = asyncio.run(run(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"Golden retrieval: queries={report['queries']} "
            f"hit@1={report['hit1']:.1%} hit@5={report['hit5']:.1%} "
            f"historical_leaks={report['historical_leaks']}"
        )
        for detail in report["details"]:
            if not detail["hit1"] or not detail["hit5"] or detail["historical_leaks"]:
                print(
                    f"- {detail['id']}: expected={detail['expected_sources']} "
                    f"actual={detail['sources'][:5]} leaks={detail['historical_leaks']}"
                )
        print(f"Report: {output}")
    passed = (
        report["hit1"] >= args.require_hit1
        and report["hit5"] >= args.require_hit5
        and report["historical_leaks"] == 0
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
