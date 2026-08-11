---
type: procedural
status: active
date: 2026-08-11
updated: 2026-08-11T14:05:00+05:30
aliases:
  - UAMS Reliability Implementation Plan
tags:
  - "#uams"
  - "#implementation-plan"
  - "#postgresql"
  - "#qdrant"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[PostgreSQL]]"
  - "[[Qdrant]]"
related_to:
  - "[[Unified Memory Reliability Design]]"
---

# Unified Memory Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PostgreSQL control plane and reconciled Qdrant v2 projection so every default retrieval result maps to a current Markdown revision.

**Architecture:** Markdown remains authoritative. A PostgreSQL-backed reconciler stages document revisions, chunks, lexical indexes, entities, graph claims, profiles, jobs, and vector outbox commands. Qdrant keeps semantic vectors in one collection; PostgreSQL activates a revision only after vector delivery succeeds, and hybrid retrieval fuses both engines.

**Tech Stack:** Python 3.11, FastAPI, Psycopg 3 async pool, PostgreSQL 16, Qdrant 1.x, Ollama embeddings, pytest, Docker Compose

---

## File Structure

- `memory_watcher/storage/migrations/001_control_plane.sql`: PostgreSQL schema and indexes.
- `memory_watcher/storage/postgres_store.py`: pool, migrations, revisions, FTS, graph/profile queries, and drift counts.
- `memory_watcher/models/memory_record.py`: validated frontmatter and stable memory identity.
- `memory_watcher/pipelines/reconciliation.py`: vault scan, content-hash comparison, staging, and lifecycle detection.
- `memory_watcher/pipelines/vector_worker.py`: durable outbox delivery and revision activation.
- `memory_watcher/storage/qdrant_store.py`: legacy compatibility plus `memory_chunks_v2` operations.
- `memory_watcher/api/retrieval/hybrid.py`: PostgreSQL/Qdrant fusion and active-revision validation.
- `memory_watcher/api/routers/profiles.py`: exact profile projection endpoint.
- `memory_watcher/scripts/migrate_control_plane.py`: migrations, reconciliation, vector drain, and drift report.
- `memory_watcher/scripts/evaluate_retrieval.py`: golden-query evaluation.

### Task 1: PostgreSQL Infrastructure and Migration Runner

**Files:**
- Modify: `memory_watcher/docker-compose.yml`
- Modify: `.env.example`
- Modify: `memory_watcher/requirements.txt`
- Create: `memory_watcher/storage/migrations/001_control_plane.sql`
- Create: `memory_watcher/storage/postgres_store.py`
- Create: `memory_watcher/tests/test_postgres_store.py`

- [ ] **Step 1: Write failing configuration and migration tests**

```python
def test_postgres_config_redacts_password(monkeypatch):
    monkeypatch.setenv("UAMS_POSTGRES_PASSWORD", "secret")
    config = PostgresConfig.from_env()
    assert config.host == "127.0.0.1"
    assert "secret" not in repr(config)

def test_migrations_are_ordered():
    assert [path.name for path in migration_paths()] == ["001_control_plane.sql"]
```

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_postgres_store.py -v`

Expected: import failure because `storage.postgres_store` does not exist.

- [ ] **Step 3: Add Docker and Python dependencies**

Add a localhost-only `postgres:16-bookworm` service, named volume, `POSTGRES_DB=uams`, application credentials, and `pg_isready` health check. Replace the Qdrant `latest` default with the locally tested digest `qdrant/qdrant@sha256:b3063c673f3973877c038eeecc392bad5011f072ee7892b56c9a8e204a3bdea9`. Add `psycopg[binary,pool]>=3.2,<4`. Configure `AsyncConnectionPool(open=False)` with explicit open/close.

- [ ] **Step 4: Create and apply the schema**

Create `schema_migrations`, `documents`, `document_revisions`, `chunks`, `entities`, `entity_aliases`, `mentions`, `claims`, `profiles`, `profile_facts`, `ingestion_jobs`, `vector_outbox`, and `memory_audit_events`. Use a stored English `tsvector` and GIN index on chunks.

- [ ] **Step 5: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_postgres_store.py -v`

Commit: `git add .env.example memory_watcher/docker-compose.yml memory_watcher/requirements.txt memory_watcher/storage/migrations/001_control_plane.sql memory_watcher/storage/postgres_store.py memory_watcher/tests/test_postgres_store.py && git commit -m "feat(storage): add postgres control plane"`

### Task 2: Managed Markdown Schema and Atomic Writes

**Files:**
- Create: `memory_watcher/models/memory_record.py`
- Modify: `memory_watcher/api/memory_writer.py`
- Modify: `memory_watcher/api/routers/memory_edit.py`
- Create: `memory_watcher/tests/test_memory_record.py`
- Modify: `memory_watcher/tests/test_memory_edit.py`

- [ ] **Step 1: Write failing identity, concurrency, and path tests**

```python
def test_existing_note_gets_deterministic_memory_id(tmp_path):
    path = tmp_path / "Concepts" / "Qdrant.md"
    first = parse_memory(path, "---\ntype: semantic\n---\n# Qdrant")
    second = parse_memory(path, "---\ntype: semantic\n---\n# Qdrant")
    assert first.memory_id == second.memory_id

def test_resolve_vault_path_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        resolve_vault_path(tmp_path, "../outside.md")
```

Also run parallel writes with the same title and assert unique filenames and complete frontmatter.

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_memory_record.py memory_watcher/tests/test_memory_edit.py -v`

- [ ] **Step 3: Implement managed records and safe writes**

Normalize `memory_id`, type, status, aliases, entities, timestamps, source agent, project, and structured relationships. Existing notes use UUIDv5 over the normalized vault-relative path until migration writes IDs. New writes use a temporary sibling file, flush, `os.fsync()`, and `os.replace()`. Generated filenames contain a UUID suffix. Edit backups live under ignored `.uams/backups/`. The write endpoint returns `memory_id`, vault-relative path, and `index_status`, using `pending` when PostgreSQL is unavailable.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_memory_record.py memory_watcher/tests/test_memory_edit.py -v`

Commit: `git add memory_watcher/models/memory_record.py memory_watcher/api/memory_writer.py memory_watcher/api/routers/memory_edit.py memory_watcher/tests/test_memory_record.py memory_watcher/tests/test_memory_edit.py && git commit -m "feat(memory): validate and atomically write managed notes"`

### Task 3: Useful Chunks, Entities, Mentions, and Claims

**Files:**
- Modify: `memory_watcher/chunkers/semantic.py`
- Modify: `memory_watcher/graph/extractor.py`
- Create: `memory_watcher/tests/test_projection_extraction.py`

- [ ] **Step 1: Write failing extraction tests**

Cover heading-only suppression, title context on body chunks, alias normalization, wikilinks as mentions, `related_to` as explicit claims, structured relationship claims, and candidate claims excluded from verified expansion.

```python
def test_wikilink_is_a_mention_not_a_factual_claim():
    projection = extract_projection(record("This note references [[Qdrant]]."))
    assert [m.entity_name for m in projection.mentions] == ["Qdrant"]
    assert projection.claims == []
```

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_projection_extraction.py -v`

- [ ] **Step 3: Implement minimal extraction**

Do not emit standalone heading chunks. Prepend title and heading hierarchy to useful body chunks. Normalize entity keys with Unicode NFKC, trimmed whitespace, and `casefold()`. Body wikilinks are mentions. Only structured frontmatter and `related_to` become `explicit` claims.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_projection_extraction.py memory_watcher/tests/test_semantic.py -v`

Commit: `git add memory_watcher/chunkers/semantic.py memory_watcher/graph/extractor.py memory_watcher/tests/test_projection_extraction.py && git commit -m "feat(ingestion): extract useful chunks and evidenced claims"`

### Task 4: Transactional Revision Staging and Reconciliation

**Files:**
- Create: `memory_watcher/pipelines/reconciliation.py`
- Modify: `memory_watcher/storage/postgres_store.py`
- Modify: `memory_watcher/services/watcher.py`
- Modify: `memory_watcher/main.py`
- Create: `memory_watcher/tests/test_reconciliation.py`

- [ ] **Step 1: Write failing reconciliation tests**

Prove content-hash idempotency, per-memory serialization, move correlation by `memory_id`, archive and delete status, startup full scan, retry state, and preservation of the prior active revision after staging.

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_reconciliation.py -v`

- [ ] **Step 3: Implement staging and scans**

Inside one advisory lock and transaction, upsert the document, insert a revision, replace chunks/mentions/claims/profile facts, create a job and audit event, and enqueue `upsert_revision`. Do not change `current_revision_id`. Startup performs a complete scan before watching; periodic reconciliation defaults to 300 seconds. Exclude `.git`, virtualenvs, `memory_watcher`, `.uams`, `.superpowers`, and backups.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_reconciliation.py -v`

Commit: `git add memory_watcher/pipelines/reconciliation.py memory_watcher/storage/postgres_store.py memory_watcher/services/watcher.py memory_watcher/main.py memory_watcher/tests/test_reconciliation.py && git commit -m "feat(ingestion): reconcile markdown revisions transactionally"`

### Task 5: Qdrant v2 Projection and Durable Outbox

**Files:**
- Modify: `memory_watcher/storage/qdrant_store.py`
- Create: `memory_watcher/pipelines/vector_worker.py`
- Create: `memory_watcher/tests/test_vector_worker.py`

- [ ] **Step 1: Write failing lifecycle tests**

Test collection initialization, payload indexes, full-revision upsert, filter deletion by `memory_id` and `revision_id`, outbox retry, acknowledgement, activation, and old-revision cleanup.

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_vector_worker.py -v`

- [ ] **Step 3: Implement `memory_chunks_v2` and delivery**

Create one 1024-dimensional cosine collection and keyword indexes for `memory_id`, `revision_id`, `memory_type`, `project`, `source_agent`, and entity keys. Claim outbox rows with `FOR UPDATE SKIP LOCKED`, embed staged chunks, upsert with `wait=True`, acknowledge, activate in PostgreSQL, supersede the old revision, and delete old points by filter. Failures retry without changing the old active revision.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_vector_worker.py -v`

Commit: `git add memory_watcher/storage/qdrant_store.py memory_watcher/pipelines/vector_worker.py memory_watcher/tests/test_vector_worker.py && git commit -m "feat(vectors): project active revisions through durable outbox"`

### Task 6: Hybrid Retrieval with Revision Validation

**Files:**
- Create: `memory_watcher/api/retrieval/hybrid.py`
- Modify: `memory_watcher/api/retrieval/pipeline.py`
- Modify: `memory_watcher/api/models.py`
- Modify: `memory_watcher/api/main.py`
- Create: `memory_watcher/tests/test_hybrid_retrieval.py`

- [ ] **Step 1: Write failing retrieval tests**

Cover cross-type vector search, FTS, reciprocal-rank fusion, verified graph expansion, active-revision validation, archived/historical behavior, `min_score`, filters, evidence IDs, bounded temporal boosts, and deduplication.

```python
async def test_default_search_rejects_stale_qdrant_candidate():
    response = await pipeline.search(request("reconnect bug"))
    assert all(item.revision_id == active[item.memory_id] for item in response.results)
```

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_hybrid_retrieval.py -v`

- [ ] **Step 3: Implement fusion**

Query Qdrant and PostgreSQL concurrently, validate current revisions, fuse ranks with RRF constant 60, cap graph/profile/recency boosts, rerank, enforce `min_score`, and deduplicate. Use legacy retrieval only when the v2 control plane is unavailable or not migrated.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_hybrid_retrieval.py memory_watcher/api/tests/test_retrieval_pipeline.py -v`

Commit: `git add memory_watcher/api/retrieval/hybrid.py memory_watcher/api/retrieval/pipeline.py memory_watcher/api/models.py memory_watcher/api/main.py memory_watcher/tests/test_hybrid_retrieval.py && git commit -m "feat(retrieval): fuse qdrant semantics with postgres truth"`

### Task 7: Evidence Graph and Profile APIs

**Files:**
- Modify: `memory_watcher/api/routers/graph.py`
- Create: `memory_watcher/api/routers/profiles.py`
- Modify: `memory_watcher/api/main.py`
- Create: `memory_watcher/tests/test_graph_profiles.py`

- [ ] **Step 1: Write failing API tests**

Graph results must include claim ID, predicate, evidence, confidence, status, and source revision. Candidate claims are hidden by default. Profile facts return current values and evidence; archived profile revisions are excluded.

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_graph_profiles.py -v`

- [ ] **Step 3: Implement PostgreSQL endpoints**

Replace global NetworkX router state with store queries. Add `GET /profiles/{profile_id}` with candidate and historical flags. Preserve the old node-link shape for SDK compatibility while attaching evidence metadata.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_graph_profiles.py -v`

Commit: `git add memory_watcher/api/routers/graph.py memory_watcher/api/routers/profiles.py memory_watcher/api/main.py memory_watcher/tests/test_graph_profiles.py && git commit -m "feat(graph): serve evidenced claims and durable profiles"`

### Task 8: Readiness, Drift, CLI, and Migration

**Files:**
- Modify: `memory_watcher/api/main.py`
- Modify: `memory_watcher/scripts/doctor.py`
- Create: `memory_watcher/scripts/migrate_control_plane.py`
- Modify: `memory_watcher/scripts/auto_integrate.py`
- Modify: `uams`
- Modify: `Makefile`
- Create: `memory_watcher/tests/test_control_plane_health.py`

- [ ] **Step 1: Write failing health and lifecycle tests**

Readiness reports PostgreSQL, Qdrant, a real embedding/search probe, reranker state, pending/failed jobs, oldest lag, and drift. CLI status reports both databases and reconciler state.

- [ ] **Step 2: Run RED**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_control_plane_health.py -v`

- [ ] **Step 3: Implement commands**

`./uams start` starts both databases, waits for health, migrates, starts host services, and verifies `/ready`. `./uams migrate` performs full reconciliation, vector drain, drift reporting, and a controlled `--write-memory-ids` pass that atomically adds stable IDs to legacy notes. `./uams integrate` reports each client as configured, missing, invalid, or unreachable. `./uams stop` leaves durable databases running unless `--infra` is explicit.

- [ ] **Step 4: Run GREEN and commit**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests/test_control_plane_health.py -v`

Commit: `git add memory_watcher/api/main.py memory_watcher/scripts/doctor.py memory_watcher/scripts/migrate_control_plane.py memory_watcher/scripts/auto_integrate.py uams Makefile memory_watcher/tests/test_control_plane_health.py && git commit -m "feat(ops): add control-plane readiness and migration lifecycle"`

### Task 9: Golden Retrieval and Failure Integration Tests

**Files:**
- Create: `memory_watcher/tests/fixtures/retrieval_golden.json`
- Create: `memory_watcher/scripts/evaluate_retrieval.py`
- Create: `memory_watcher/tests/integration/test_projection_lifecycle.py`
- Create: `memory_watcher/tests/integration/test_failure_recovery.py`
- Modify: `Makefile`

- [ ] **Step 1: Add the golden dataset and failing tests**

Commit the ten audited queries and add profile, alias, graph evidence, archived, superseded, contradiction, and historical cases. Real Docker tests stop Qdrant after staging, stop PostgreSQL around a Markdown write, miss events, inject malformed notes, run parallel writes, and move/archive/restore/delete notes.

- [ ] **Step 2: Run RED**

Run: `make test-integration`

Expected: failure until lifecycle recovery is fully wired.

- [ ] **Step 3: Complete only missing recovery behavior**

Do not weaken assertions. Fix the responsible boundary until tests converge with zero drift and lost writes.

- [ ] **Step 4: Run acceptance and commit**

Run: `memory_watcher/.venv/bin/python memory_watcher/scripts/evaluate_retrieval.py --require-hit1 0.80 --require-hit5 0.90`

Expected: hit@1 at least 80%, hit@5 at least 90%, and zero historical leaks.

Commit: `git add memory_watcher/tests/fixtures/retrieval_golden.json memory_watcher/scripts/evaluate_retrieval.py memory_watcher/tests/integration Makefile && git commit -m "test(memory): enforce retrieval and recovery acceptance gates"`

### Task 10: Full Verification, Migration, and Deployment

**Files:**
- Modify: `README.md`
- Modify: `RELEASE_CHECKLIST.md`

- [ ] **Step 1: Run full verification**

Run: `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests tests uams_sdk/tests -q`

Run: `memory_watcher/.venv/bin/python -m compileall -q memory_watcher uams_sdk`

Run: `git diff --check`

Run: `docker compose -f memory_watcher/docker-compose.yml config --quiet`

Expected: every command exits 0.

- [ ] **Step 2: Snapshot and deploy**

Back up the Qdrant named volume and legacy graph, start PostgreSQL, run `./uams migrate`, and retain old Qdrant collections unchanged for rollback.

- [ ] **Step 3: Verify live readiness**

Run: `./uams start`

Run: `curl -fsS http://127.0.0.1:8000/ready`

Run: `./uams status`

Expected: PostgreSQL, Qdrant, embeddings, API, and reconciler ready; failed jobs and drift equal zero.

- [ ] **Step 4: Re-run live retrieval acceptance**

Run: `memory_watcher/.venv/bin/python memory_watcher/scripts/evaluate_retrieval.py --api http://127.0.0.1:8000 --require-hit1 0.80 --require-hit5 0.90`

- [ ] **Step 5: Document operations and commit**

Document PostgreSQL/Qdrant responsibilities, migration, backup, readiness, reconciliation, rollback, and the absence of Redis.

Commit: `git add README.md RELEASE_CHECKLIST.md && git commit -m "docs(memory): document reliable local control plane"`
