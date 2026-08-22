# Architecture Design: Memory Evolution, Bitemporal Claims, Retention & Deduplication

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
The UAMS memory store does not evolve:
1. `/remember` mints a fresh UUID per call without checking for semantic duplicates or updates.
2. `retention_policy` is unread; archived notes are indexed into active Qdrant collections without pruning; temporal recency has negligible retrieval impact.
3. Memory-level contradictions are unhandled; the graph's `verified` claim tier is unused.
4. Claims lack bitemporal validity intervals (`valid_from`, `valid_to`, `invalidated_by`), making "as of last month, what was true?" unanswerable.
5. AGENTS.md promotion rules ("promote after 2 references", "compress scattered logs") have zero enforcement mechanism.

---

## 2. Core Architectural Subsystems

```
                     ┌─────────────────────────────────────────────────────────┐
                     │                 POST /remember Ingestion                │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │          Write-Path Evolution & Dedup Engine            │
                     │  - Vector search for top-k similar memories (sim > 0.88)│
                     │  - LLM / Heuristic Decision: ADD vs UPDATE vs NOOP      │
                     │  - UPDATE: Appends new facts/revises existing note      │
                     │  - NOOP: Returns existing memory ID, prevents duplicate │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                   ┌──────────────────────────────┴──────────────────────────────┐
                   ▼                                                             ▼
     ┌────────────────────────────┐                                ┌───────────────────────────┐
     │  Bitemporal Claims Engine  │                                │  Retention & Forgetting   │
     │  - valid_from / valid_to   │                                │  - rolling TTL expiry     │
     │  - invalidated_by claim ID │                                │  - Qdrant archive filter  │
     │  - Contradiction detection │                                │  - Active vs Archived     │
     │  - Multi-agent verified tier│                               │    partitioning           │
     └────────────────────────────┘                                └───────────────────────────┘
                   │                                                             │
                   └──────────────────────────────┬──────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │           AGENTS.md Promotion Enforcement Engine        │
                     │  - Entity reference counting across Daily logs          │
                     │  - Auto-promotion to Concepts/ after >= 2 references   │
                     │  - Automated compression of scattered episodic logs     │
                     └─────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Technical Components

### Component 1: Write-Path Deduplication & Update Decision Engine
- **Files**: `memory_watcher/api/memory_writer.py`, `memory_watcher/api/main.py`, `memory_watcher/api/routers/ingest.py`.
- **Logic**:
  - Before creating a new file, run a hybrid similarity search against active memories.
  - If a memory matches with cosine similarity $\ge 0.88$ or matching title/entities:
    - Assess whether new text contains novel factual statements.
    - If novel facts exist: Update the existing note body with updated sections (`## Updates`, timestamped facts) and bump revision.
    - If no novel facts: Return existing memory with `decision: "NOOP"`, status: `"unchanged"`.
    - If distinct topic: Proceed with `ADD`.

### Component 2: Bitemporal Knowledge Graph Claims & Contradiction Detection
- **Files**: `memory_watcher/storage/migrations/003_bitemporal_claims.sql`, `memory_watcher/graph/extractor.py`, `memory_watcher/storage/postgres_store.py`.
- **Database Schema**:
  - Add to `claims` table:
    - `valid_from timestamptz NOT NULL DEFAULT now()`
    - `valid_to timestamptz`
    - `invalidated_by_claim_id uuid REFERENCES claims(claim_id) ON DELETE SET NULL`
    - `status text CHECK (status IN ('explicit', 'verified', 'candidate', 'superseded', 'retracted'))`
- **Contradiction Detection**:
  - When a new claim $(S, P, O_2)$ arrives where active claim $(S, P, O_1)$ exists with opposing truth value or exclusive object:
    - Mark $(S, P, O_1)$ as `valid_to = now()`, `status = 'superseded'`, `invalidated_by_claim_id = new_claim.claim_id`.
    - Mark new claim as `valid_from = now()`, `status = 'explicit'`.
  - When multiple distinct agents assert identical $(S, P, O)$:
    - Promote status to `'verified'` with confidence boost.

### Component 3: Retention Policy, Forgetting Engine & Qdrant Archive Filtering
- **Files**: `memory_watcher/memory_types/memory_types.py`, `memory_watcher/pipelines/reconciliation.py`, `memory_watcher/api/retrieval/hybrid.py`, `memory_watcher/services/watcher.py`.
- **Logic**:
  - `retention_policy`:
    - `indefinite`: Semantic concepts, procedures, identities (never pruned automatically).
    - `rolling`: Episodic notes older than 14 days with importance $< 0.35$ move to `Archive/` and status becomes `archived`.
  - **Qdrant Filtering**:
    - During vector search in `HybridRetrieval`, filter by `status: "active"` by default.
    - Exclude `archived` / `deleted` notes unless `include_historical=True`.
  - **Temporal Decay**:
    - Weight recency significantly for episodic queries ($e^{-\lambda \cdot \Delta t}$).

### Component 4: AGENTS.md Rule Enforcement Engine
- **Files**: `memory_watcher/intelligence/distiller.py`, `memory_watcher/memory_types/consolidation.py`, `memory_watcher/services/watcher.py`.
- **Logic**:
  - Reference Counter: Tracks entity references in `Daily/*.md`.
  - Trigger: When an entity (e.g. `[[Project X]]`, `[[Database Config]]`) is referenced in $\ge 2$ distinct daily files without an existing `Concepts/<Entity>.md`:
    - Automatically create `Concepts/<Entity>.md` with `type: semantic`.
    - Synthesize scattered daily log facts into the concept note.
    - Backlink source daily notes to the new concept note.

---

## 4. Verification Plan
- Unit & integration tests for:
  - Write-path deduplication & update resolution (`test_write_path_dedup.py`).
  - Bitemporal claim invalidation & contradiction handling (`test_bitemporal_claims.py`).
  - Retention policy enforcement and Qdrant archive exclusion (`test_retention_policy.py`).
  - AGENTS.md 2-reference promotion enforcement (`test_agents_rule_enforcement.py`).
- Full test suite run (`pytest memory_watcher/tests/ -v`).
