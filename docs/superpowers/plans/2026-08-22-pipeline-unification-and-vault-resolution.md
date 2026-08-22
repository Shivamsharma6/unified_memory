# Implementation Plan: Pipeline Unification, Vault Root Consolidation, and Graph Synchronization

**Goal**: Eliminate dual-pipeline coexistence, legacy graph contamination, constant divergences, and inconsistent vault-path calculations.

---

## Tasks

### Task 1: Centralized `get_vault_root()` Helper & Router Refactoring
- **Files**:
  - `memory_watcher/models/memory_record.py`
  - `memory_watcher/api/memory_writer.py`
  - `memory_watcher/api/routers/memory_edit.py`
  - `memory_watcher/api/routers/quality.py`
  - `memory_watcher/api/routers/validation.py`
  - `memory_watcher/api/procedure_reader.py`
  - `memory_watcher/api/main.py`
- **Changes**:
  - Implement `get_vault_root()` in `models/memory_record.py`.
  - Refactor all routers and writer modules to use `get_vault_root()`.

### Task 2: Subsystem Vault Root Alignment
- **Files**:
  - `memory_watcher/identity/store.py`
  - `memory_watcher/intelligence/distiller.py`
  - `memory_watcher/intelligence/reflection.py`
  - `memory_watcher/pipelines/reconciliation.py`
  - `memory_watcher/api/retrieval/pipeline.py`
- **Changes**:
  - Ensure all subsystems pass through `get_vault_root()`.

### Task 3: Ingestion Pipeline & Graph Write Unification
- **Files**:
  - `memory_watcher/api/main.py`
  - `memory_watcher/api/memory_writer.py`
- **Changes**:
  - Route all write paths exclusively through `Reconciler` / `PostgresStore` / `VectorStore` (v2).
  - Stop legacy graph contamination.

### Task 4: Pipeline Constants & Temporal Boost Calibration
- **Files**:
  - `memory_watcher/api/retrieval/pipeline.py`
  - `memory_watcher/api/retrieval/hybrid.py`
- **Changes**:
  - Standardize `_temporal_boost` calculation and decay constants across pipelines.

### Task 5: Vault Path & Pipeline Integration Tests
- **Files**:
  - `memory_watcher/tests/test_vault_path_resolution.py`
  - `memory_watcher/tests/test_unified_pipeline_constants.py`
- **Changes**:
  - Add test suites verifying external `UAMS_VAULT_PATH` support and constant consistency.

### Task 6: Full Test Suite Verification & Quality Assurance
- Run `pytest memory_watcher/tests/ -v`.
- Verify all tests pass with 0 regressions.
