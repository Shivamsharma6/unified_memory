# Implementation Plan: Multi-Agent Surface Attribution, Session Lifecycle, Read-After-Write Consistency, and Optimistic Concurrency

**Goal**: Fix the multi-agent attribution disconnection, unpersisted session lifecycle, read-after-write vector lag, optimistic concurrency gaps, and global identity collision in UAMS.

---

## Tasks

### Task 1: SDK & MCP Multi-Agent Attribution Propagation
- **Files**:
  - `uams_sdk/uams_sdk/client.py`
  - `uams_sdk/uams_sdk/mcp_server.py`
  - `memory_watcher/tests/test_multiagent_attribution.py`
- **Changes**:
  - Support `source_agent: str` and `project: Optional[str]` on `UAMSClient` with environment variable defaults (`UAMS_AGENT_NAME` / `UAMS_PROJECT`).
  - Propagate `source_agent` and `project` in `store_memory`, `search`, `begin_task`, `end_task`.
  - Expose `source_agent` and `project` parameters across all FastMCP tools.

### Task 2: Persistent Session Lifecycle & Working Memory
- **Files**:
  - `memory_watcher/api/models.py`
  - `memory_watcher/api/main.py`
  - `uams_sdk/uams_sdk/client.py`
  - `memory_watcher/tests/test_session_lifecycle.py`
- **Changes**:
  - Add session management in API (`/session/begin`, `/session/end`) and SDK.
  - Return `session_id`, `status`, `procedures`, `context`, `working_memory`.
  - In `end_task`, return structured result with explicit error messages on failure (no silent loss).

### Task 3: Read-After-Write Consistency & Synchronous Vector Activation
- **Files**:
  - `memory_watcher/api/models.py`
  - `memory_watcher/api/main.py`
  - `uams_sdk/uams_sdk/client.py`
  - `memory_watcher/tests/test_read_after_write.py`
- **Changes**:
  - Add `sync: bool = False` to `RememberRequest`.
  - When `sync=True` (or when reconciler/vector pipeline is available), synchronously embed and upsert chunks to Qdrant and mark revision `active` in PostgreSQL before returning.
  - Return honest `index_status: "active" | "staged" | "failed"` and `indexed: bool`.
  - Add `wait_for_indexing(memory_id, timeout)` helper to `UAMSClient`.

### Task 4: Optimistic Concurrency Control in Memory Self-Editing
- **Files**:
  - `memory_watcher/api/routers/memory_edit.py`
  - `memory_watcher/tests/test_optimistic_concurrency.py`
- **Changes**:
  - Add `expected_revision_id: Optional[str] = None` and `expected_hash: Optional[str] = None` to `EditRequest`.
  - Check against current revision/hash, raising HTTP 409 Conflict on mismatch.

### Task 5: Per-Agent Identity Resolution & Isolation
- **Files**:
  - `memory_watcher/identity/store.py`
  - `uams_sdk/uams_sdk/client.py`
  - `uams_sdk/uams_sdk/mcp_server.py`
  - `memory_watcher/tests/test_agent_identity_isolation.py`
- **Changes**:
  - Default `entity_id` to client's `source_agent` across identity methods.
  - Store and inject per-agent profiles independently in `Identity/{entity_id}.json`.

### Task 6: Comprehensive Test Suite Verification & Quality Assurance
- Run `pytest memory_watcher/tests/ -v`.
- Ensure 0 failures and 0 regressions across all suites.
