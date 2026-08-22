# Implementation Plan: Memory Evolution, Bitemporal Claims, Retention & Deduplication

**Goal**: Implement memory evolution in UAMS to solve:
1. Write-path duplicate suppression and intelligent note updates (`ADD / UPDATE / NOOP`).
2. Bitemporal Knowledge Graph claims (`valid_from`, `valid_to`, `invalidated_by`) and memory contradiction detection.
3. Multi-agent claim verification (`verified` tier).
4. Retention policy enforcement and active vs archived Qdrant retrieval filtering.
5. AGENTS.md 2-reference entity promotion and scattered log compression.

---

## Tasks

### Task 1: Bitemporal Claims Schema & Migration
- **Files**:
  - `memory_watcher/storage/migrations/003_bitemporal_claims.sql`
  - `memory_watcher/graph/extractor.py`
  - `memory_watcher/storage/postgres_store.py`
  - `memory_watcher/tests/test_bitemporal_claims.py`
- **Details**:
  - Create migration adding `valid_from`, `valid_to`, `invalidated_by_claim_id`, and updating status check in `claims` table.
  - Update `ProjectedClaim` and `extract_projection` to support `valid_from`, `valid_to`, and timestamps.
  - Update `PostgresStore` methods to handle bitemporal claims and `as_of` temporal queries.

### Task 2: Claim Contradiction Detection & Multi-Agent Verified Tier
- **Files**:
  - `memory_watcher/graph/extractor.py`
  - `memory_watcher/storage/postgres_store.py`
  - `memory_watcher/tests/test_claim_contradictions.py`
- **Details**:
  - When saving claims in `PostgresStore`, check for conflicting claims on the same `(subject_entity_id, predicate)`:
    - If conflicting claim exists: mark old claim `valid_to = now()`, `status = 'superseded'`, `invalidated_by_claim_id = new_claim_id`.
    - If corroborating claim exists from another `source_agent`: promote status to `'verified'` and increase confidence.

### Task 3: Write-Path Deduplication, Updates & Semantic Decision Engine
- **Files**:
  - `memory_watcher/api/memory_writer.py`
  - `memory_watcher/api/main.py`
  - `memory_watcher/tests/test_write_path_dedup.py`
- **Details**:
  - In `write_memory`, before minting a fresh UUID and creating a new file:
    - Scan active vault files in target category directory.
    - If title or core entity matches and content similarity is high:
      - If text is redundant: return existing record (`decision: "NOOP"`, `status: "unchanged"`).
      - If text provides new updates: append `## Updates ({ISO_DATE})\n{update_text}` to existing file, update frontmatter `timestamps.updated`, and trigger reconciliation (`decision: "UPDATE"`).
      - Otherwise: create new file (`decision: "ADD"`).

### Task 4: Retention Policy & Archive Filtering in Vector Retrieval
- **Files**:
  - `memory_watcher/api/retrieval/hybrid.py`
  - `memory_watcher/pipelines/vector_worker.py`
  - `memory_watcher/tests/test_retention_policy.py`
- **Details**:
  - In `HybridRetrieval.search()`:
    - Default filter: only include memories with `status: "active"` or exclude `status: "archived"`.
    - Allow `include_historical=True` to include archived memories.
  - Enhance recency decay scaling in `HybridRetrieval` to give actionable separation based on memory age.

### Task 5: AGENTS.md 2-Reference Auto-Promotion & Log Compression
- **Files**:
  - `memory_watcher/intelligence/distiller.py`
  - `memory_watcher/memory_types/consolidation.py`
  - `memory_watcher/tests/test_agents_rule_enforcement.py`
- **Details**:
  - Implement `promote_referenced_entities(vault_path: Path)` in `MemoryDistiller`:
    - Count occurrences of `[[Entity]]` across `Daily/*.md`.
    - If an entity appears in $\ge 2$ daily files and no `Concepts/<Entity>.md` exists:
      - Create `Concepts/<Entity>.md` with `type: semantic`, summary of daily mentions, and backlink to daily logs.
      - Update daily notes with proper categorization.

### Task 6: Full Test Suite Verification & Quality Assurance
- Run all tests: `source memory_watcher/.venv/bin/activate && pytest memory_watcher/tests/ -v`.
- Ensure 0 failures and 0 regressions.
