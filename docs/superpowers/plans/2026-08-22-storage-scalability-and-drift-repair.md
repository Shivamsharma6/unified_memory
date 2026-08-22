# Implementation Plan: Storage Scalability, Batch Staging, Index Optimization, and Drift Repair

**Goal**: Eliminate staging N+1 latency, unbounded storage growth, missing database indexes, poison 503 cascades, and broken maintenance scripts.

---

## Tasks

### Task 1: Performance Indexes & Storage Pruning Migration
- **Files**:
  - `memory_watcher/storage/migrations/006_performance_and_storage_indexes.sql`
  - `memory_watcher/tests/test_postgres_store.py`
- **Changes**:
  - Add migration 006 with indexes on `document_revisions`, `vector_outbox`, `ingestion_jobs`, `documents`, and `chunks`.

### Task 2: Batched Multi-Row Staging in `PostgresStore.stage_revision()`
- **Files**:
  - `memory_watcher/storage/postgres_store.py`
  - `memory_watcher/tests/test_batch_staging.py`
- **Changes**:
  - Replace iterative single-row inserts for chunks, mentions, and claims with multi-row batch statements.

### Task 3: Storage Pruning Engine & Maintenance Endpoint
- **Files**:
  - `memory_watcher/storage/postgres_store.py`
  - `memory_watcher/api/main.py`
  - `memory_watcher/tests/test_storage_pruning.py`
- **Changes**:
  - Implement `PostgresStore.prune_superseded_storage(max_age_days)`.
  - Expose `POST /admin/maintenance/prune` endpoint.

### Task 4: Resilient Readiness Probing & Drift Repair Endpoints
- **Files**:
  - `memory_watcher/api/readiness.py`
  - `memory_watcher/api/main.py`
  - `memory_watcher/tests/test_resilient_readiness.py`
- **Changes**:
  - Make readiness check resilient to isolated failed outbox rows.
  - Expose `/admin/repair/orphans` and `/admin/repair/reindex` endpoints.

### Task 5: Maintenance Script Modernization
- **Files**:
  - `memory_watcher/scripts/embed_upgrade.py`
  - `memory_watcher/scripts/reindex.py`
  - `memory_watcher/tests/test_maintenance_scripts.py`
- **Changes**:
  - Fix `NameError` in `embed_upgrade.py` with correct `qdrant_models.PointStruct`.
  - Update `reindex.py` to target `memory_chunks_v2` and use modern store pipelines.

### Task 6: Full Test Suite Verification & Quality Assurance
- Run `pytest memory_watcher/tests/ -v`.
- Verify 0 failures, 0 errors, and 0 regressions.
