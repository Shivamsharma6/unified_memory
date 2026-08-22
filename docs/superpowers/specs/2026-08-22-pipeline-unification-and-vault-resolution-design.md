# Architecture Design: Pipeline Unification, Vault Root Consolidation, and Graph Synchronization

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
The UAMS codebase suffered from legacy architectural contamination:
1. **Dual Ingestion & Graph Divergence**: `/remember` could invoke legacy `IngestionPipeline`, which updated an additive-only `knowledge_graph.json` and legacy Qdrant collections (`semantic_memory`, `episodic_memory`, etc.), while the watcher populated the PostgreSQL control plane (`entities`, `mentions`, `claims`) and `memory_chunks_v2`.
2. **Divergent Pipeline Constants**: `RetrievalPipeline._temporal_boost` used an uncapped 1.0 curve with 30-day half-life, while `HybridRetrieval._temporal_boost` used bounded 0.15 scaling with 14-day half-life.
3. **Four Different Vault Root Calculations**: Vault-root was resolved differently across `memory_writer.py` (`parents[2]`), `memory_edit.py` (`parents[3]`), `validation.py`, `procedure_reader.py`, `identity/store.py`, and `main.py`. Setting `UAMS_VAULT_PATH` to an external vault caused `/remember` to write into the repository directory instead of the external vault.

---

## 2. Technical Architecture & Solutions

```
                                  ┌─────────────────────────────┐
                                  │   Authoritative Vault Root  │
                                  │   get_vault_root(explicit)  │
                                  └──────────────┬──────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
    ┌─────────────────────────────┐┌─────────────────────────────┐┌─────────────────────────────┐
    │     Unified Write Paths     ││   Synchronized v2 Ingestion ││     Unified Constants       │
    │  - /remember                ││  - Reconciler.reconcile_path││  - Scaled temporal boost    │
    │  - /memory/edit             ││  - PostgresStore (claims)   ││  - Canonical entity keys    │
    │  - File Watcher             ││  - memory_chunks_v2         ││  - Single ranking scheme    │
    └─────────────────────────────┘└─────────────────────────────┘└─────────────────────────────┘
```

---

## 3. Subsystem Detailed Changes

### Component 1: Centralized Vault Root Resolver (`get_vault_root()`)
- In `models/memory_record.py`:
  - Define `get_vault_root(explicit_root: Path | str | None = None) -> Path`:
    - Checks `explicit_root`.
    - Checks `os.getenv("UAMS_VAULT_PATH")`.
    - Fallback: repository root `Path(__file__).resolve().parents[2]`.
- Refactor all consumers:
  - `api/memory_writer.py`
  - `api/routers/memory_edit.py`
  - `api/routers/quality.py`
  - `api/routers/validation.py`
  - `api/procedure_reader.py`
  - `api/main.py`
  - `identity/store.py`
  - `intelligence/distiller.py`
  - `intelligence/reflection.py`
  - `pipelines/reconciliation.py`

### Component 2: Pipeline Unification & Dead Path Retirement
- In `api/main.py` & `api/memory_writer.py`:
  - Route all write paths through `Reconciler` / `PostgresStore` / `VectorStore` (v2).
  - Stop writing to legacy `knowledge_graph.json`.
- In `api/retrieval/pipeline.py`:
  - Align `_temporal_boost` with `HybridRetrieval._temporal_boost` (14-day half-life, 0.15 max bound).

### Component 3: Regression Testing
- Add `tests/test_vault_path_resolution.py` verifying external `UAMS_VAULT_PATH` is respected across every router and writer.
- Add `tests/test_unified_pipeline_constants.py` verifying temporal boost and entity extraction consistency.
