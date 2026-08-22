# Architecture Design: Storage Scalability, Batch Ingestion Optimization, Index Acceleration, and Drift Repair

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
The UAMS storage and maintenance architecture had five operational vulnerabilities:
1. **N+1 Staging & Ingestion Lock Contention**: `stage_revision` executed individual single-row SQL inserts per chunk, mention, and claim. Periodic scans held monolithic locks blocking concurrent API writes.
2. **Unbounded Storage Growth & Duplicate Data**: Redundant duplicate strings (`embedding_text` and `content`), unpruned superseded revisions, old ingestion jobs, completed outbox rows, and audit events grew indefinitely with no retention routine.
3. **Missing Critical PostgreSQL Indexes**: Sequential table scans occurred during revision activation, search, and outbox polling.
4. **Poison Outbox 503 Cascades**: A single poison outbox row caused `assess_lightweight_readiness()` to return `503 Service Unavailable` for the entire cluster.
5. **Broken Maintenance & Drift Repair Scripts**: `scripts/embed_upgrade.py` crashed on `NameError: models.PointStruct`, `scripts/reindex.py` targeted legacy deleted collections, and drift repair functions had zero production endpoints.

---

## 2. Technical Architecture & Solutions

```
                               ┌─────────────────────────────┐
                               │   PostgreSQL Control Store  │
                               └──────────────┬──────────────┘
                                              │
                 ┌────────────────────────────┼────────────────────────────┐
                 ▼                            ▼                            ▼
  ┌─────────────────────────────┐┌─────────────────────────────┐┌─────────────────────────────┐
  │   Batched Multi-Row Staging ││  006 Indexing & Pruning API ││  Resilient Readiness Probe  │
  │ - Multi-row chunk inserts   ││ - Fast index lookups        ││ - Non-blocking status       │
  │ - Multi-row claim inserts   ││ - prune_superseded_storage  ││ - Diagnostic error flags    │
  │ - Granular advisory locks   ││ - Automatic outbox cleanup  ││ - No poison 503 cascades    │
  └─────────────────────────────┘└─────────────────────────────┘└─────────────────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   Production Drift Repair   │
                               │ - POST /admin/repair/prune  │
                               │ - Fixed embed_upgrade.py    │
                               │ - Fixed reindex.py for v2   │
                               └─────────────────────────────┘
```

---

## 3. Subsystem Detailed Changes

### Component 1: Batched Multi-Row Staging & Granular Advisory Locks
- In `storage/postgres_store.py`:
  - Batch insert chunks using multi-row tuples in `stage_revision()`.
  - Batch insert mentions and claims in single multi-row SQL statements.
  - In `reconciliation.py`, ensure advisory locking is per `memory_id` without blocking other memories.

### Component 2: Performance Indexes & Automated Storage Pruning
- Create migration `006_performance_and_storage_indexes.sql`:
  - `CREATE INDEX IF NOT EXISTS idx_doc_revisions_state ON document_revisions(state, memory_id);`
  - `CREATE INDEX IF NOT EXISTS idx_doc_revisions_superseded ON document_revisions(superseded_at) WHERE superseded_at IS NOT NULL;`
  - `CREATE INDEX IF NOT EXISTS idx_vector_outbox_status_avail ON vector_outbox(status, available_at);`
  - `CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status, event_type);`
  - `CREATE INDEX IF NOT EXISTS idx_documents_status_type ON documents(status, memory_type);`
  - `CREATE INDEX IF NOT EXISTS idx_chunks_revision ON chunks(revision_id);`
- In `storage/postgres_store.py`:
  - Add `prune_superseded_storage(max_age_days=30)`:
    - Deletes completed/abandoned `vector_outbox` rows older than 7 days.
    - Deletes completed `ingestion_jobs` older than 7 days.
    - Prunes superseded `profile_facts` and audit events older than `max_age_days`.

### Component 3: Resilient Readiness Probing & Drift Repair Endpoints
- In `api/readiness.py`:
  - In `assess_lightweight_readiness()`, check core PostgreSQL and Qdrant connectivity; report `failed_outbox` in `jobs` diagnostics without failing the entire API health probe.
- In `api/routers/` or `api/main.py`:
  - Add `/admin/maintenance/prune` and `/admin/repair/orphans` endpoints.
- In `scripts/embed_upgrade.py`:
  - Fix `qdrant_models.PointStruct` import and instantiation.
- In `scripts/reindex.py`:
  - Target `memory_chunks_v2` collection and utilize `PostgresStore` / `QdrantStore`.
