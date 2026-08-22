# Implementation Plan: Trust Boundary Hardening, Path Containment, and Security Layer

**Goal**: Close path traversal exploits in quality scoring, enforce durable backups on deletes, establish per-agent authentication and identity verification, sanitize error responses, and bound full-vault scans.

---

## Tasks

### Task 1: Path Traversal Containment in Quality Router
- **Files**:
  - `memory_watcher/api/routers/quality.py`
  - `memory_watcher/tests/test_quality_security.py`
- **Changes**:
  - Enforce `resolve_vault_path()` across `memory_quality` and `batch_quality`.
  - Return `HTTP 400 Bad Request` on escape attempts.

### Task 2: Durable Backups on Memory Deletions
- **Files**:
  - `memory_watcher/api/routers/memory_edit.py`
  - `memory_watcher/tests/test_delete_backup.py`
- **Changes**:
  - Add `_backup(file_path)` prior to moving/archiving in `delete_memory`.

### Task 3: Per-Agent Identity & Authentication Security Layer
- **Files**:
  - `memory_watcher/api/security.py`
  - `memory_watcher/api/main.py`
  - `memory_watcher/tests/test_api_security.py`
- **Changes**:
  - Create `api/security.py` supporting `UAMS_API_KEY`, `UAMS_AUTH_REQUIRED`, and `UAMS_ALLOWED_AGENTS`.
  - Protect API endpoints with agent verification dependencies.

### Task 4: Bounded & Non-Blocking Vault Validation
- **Files**:
  - `memory_watcher/api/routers/validation.py`
  - `memory_watcher/tests/test_validation_bounded.py`
- **Changes**:
  - Add `limit: int = 500` and thread execution in `validate_entire_vault`.

### Task 5: Error Sanitization Across API Routers
- **Files**:
  - `memory_watcher/api/routers/quality.py`
  - `memory_watcher/api/main.py`
- **Changes**:
  - Sanitize 500 internal error responses and log full traces internally.

### Task 6: Full Test Suite Verification & Quality Assurance
- Run `pytest memory_watcher/tests/ -v`.
- Verify all tests pass with 0 regressions.
