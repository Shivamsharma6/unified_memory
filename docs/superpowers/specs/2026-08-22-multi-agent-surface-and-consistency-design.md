# Architecture Design: Multi-Agent Surface Attribution, Session Lifecycle, Read-After-Write Consistency, and Optimistic Concurrency

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
Although UAMS data schemas support multi-agent metadata, the public interface and runtime severed multi-agent capabilities in five critical areas:
1. **Attribution Disconnection**: The SDK and MCP server omitted `source_agent` and `project`, writing all notes as `"unknown"` and rendering search filters ineffective.
2. **Missing Session/Working-Memory Tier**: `begin_task` minted no session ID, stored no task state, and `end_task` swallowed store failures with silent `{"ok": false}` without diagnostic errors.
3. **Monolithic Global Identity**: Identity defaulted to a single shared `default.json` for all agents rather than per-agent profiles (`Hermes`, `OpenClaw`, `VoiceAI`, `Antigravity`).
4. **False Indexing Claims & Read-After-Write Race**: `/remember` returned `indexed: true` when revisions were merely staged in Postgres without vector activation, leaving memories unsearchable in the same turn.
5. **Concurrent Write Collisions**: `/memory/edit` operated on blind last-write-wins without version preconditions (`expected_revision_id` / `expected_hash`), causing silent clobbering.

---

## 2. Technical Architecture & Solutions

```
                                  ┌───────────────────────────┐
                                  │   Agent (Hermes/OpenClaw) │
                                  │ (source_agent, project)   │
                                  └─────────────┬─────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
      ┌─────────────────────────────┐                       ┌─────────────────────────────┐
      │     begin_task / end_task   │                       │      /remember (sync=True)  │
      │ - Mints persistent session  │                       │ - Synchronous vectorization │
      │ - Returns scoped context    │                       │ - Immediate active revision │
      │ - Diagnostic errors on fail │                       │ - Read-after-write parity   │
      └──────────────┬──────────────┘                       └──────────────┬──────────────┘
                     │                                                     │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │             Multi-Agent Control & Storage               │
                   │  - Scoped identity per agent (Hermes.json, etc.)        │
                   │  - Optimistic concurrency with expected_revision_id     │
                   │  - Attributed frontmatter, SQL, and vector payloads     │
                   └─────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Detailed Changes

### Component 1: SDK & MCP Multi-Agent Attribution
- In `uams_sdk/client.py`:
  - Allow `source_agent: str` and `project: Optional[str]` on client initialization (defaulting to env `UAMS_AGENT_NAME` / `UAMS_SOURCE_AGENT` and `UAMS_PROJECT`).
  - Pass `source_agent`, `project`, `entities`, and `sync` in `store_memory()`, `search()`, `begin_task()`, `end_task()`.
  - In `store_memory()`, return `{ "ok": True, "memory_id": ..., "decision": ..., "index_status": ... }` or raise `UAMSAPIError` with complete diagnostic details on failure.
- In `uams_sdk/mcp_server.py`:
  - Expose `source_agent` and `project` on all relevant tools (`search_memory`, `begin_task`, `end_task`, `remember`, `get_identity`, `inject_identity`).

### Component 2: Persistent Session Lifecycle & Working Memory
- In `api/models.py` / `api/routers/session.py` or `api/main.py`:
  - `begin_task` returns `session_id: str` (UUID), `task: str`, `source_agent: str`, `project: Optional[str]`, `procedures: List[str]`, `context: str`.
  - Store session in active sessions registry with working memory scratchpad.
  - `end_task` takes `session_id`, `outcome`, `decisions`, `fixes`, `files`, formats distilled Markdown note with proper attribution frontmatter, and persists to vault.

### Component 3: Per-Agent Scoped Identity Profiles
- In `identity/store.py` / `uams_sdk/client.py`:
  - Default `entity_id` to `source_agent` (e.g. `Hermes`, `OpenClaw`, `Antigravity`) when not explicitly provided.
  - Maintain isolated identity profile files in `Identity/{entity_id}.json`.

### Component 4: Guaranteed Read-After-Write Consistency
- In `api/main.py` / `api/models.py`:
  - Add `sync: bool = False` to `RememberRequest`.
  - When `sync=True` (or if vector pipeline is available), immediately embed chunks, upsert to vector store, and activate revision in Postgres store before returning.
  - Return honest `index_status: "active" | "staged" | "failed"` and `indexed: bool`.
  - Add `wait_for_indexing(memory_id, timeout)` helper in SDK.

### Component 5: Optimistic Concurrency Control for Memory Edits
- In `api/routers/memory_edit.py`:
  - Add `expected_revision_id: Optional[str] = None` and `expected_hash: Optional[str] = None` to `EditRequest`.
  - If provided and does not match the active revision / content hash, reject with HTTP 409 Conflict containing the current revision ID.
