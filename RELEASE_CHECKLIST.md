---
type: procedural
status: active
aliases:
  - UAMS Release Gate
tags:
  - "#uams"
  - "#release"
  - "#operations"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[PostgreSQL]]"
  - "[[Qdrant]]"
timestamps:
  created: 2026-06-10
  updated: 2026-08-11
---

# Public Release Checklist

## Must Have

- [x] Pick a repository name and update clone URLs in `README.md`.
- [x] Confirm `LICENSE` matches the intended open-source license.
- [ ] Run `./install.sh` on a clean machine or clean virtual environment.
- [x] Snapshot the Markdown vault, Qdrant named volume, and legacy graph JSON.
- [x] Run `./uams migrate` and require zero failed jobs, failed outbox rows, or projection drift.
- [x] Run `./uams start`, open `http://localhost:8000/docs`, and verify `/ready` returns HTTP 200.
- [x] Run `make evaluate` and require hit@1 ≥ 80%, hit@5 ≥ 90%, and zero lifecycle leaks.
- [x] Run `make test-integration` against live Docker PostgreSQL and Qdrant.
- [x] Run `./uams mcp-config all` and verify the generated snippets use absolute paths.
- [ ] Register the MCP server in at least one MCP client and verify tool discovery.
- [x] Run `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests tests uams_sdk/tests -q`.
- [x] Run `memory_watcher/.venv/bin/python -m compileall -q memory_watcher uams_sdk`.
- [x] Run `docker compose -f memory_watcher/docker-compose.yml config --quiet`.
- [x] Run `memory_watcher/.venv/bin/pip check`.
- [ ] Remove local logs, caches, generated HTML, and private memory notes from the commit.
- [ ] Review all Markdown memories for secrets and private project details.

## Should Have

- [ ] Add screenshots or terminal recordings for setup and MCP discovery.
- [ ] Publish a `v0.1.0` GitHub release with known limitations.
- [x] Add CI for linting, tests, and package installation.
- [x] Add issue templates for bugs, feature requests, and adapter requests.
- [ ] Add more agent-specific examples for Codex, Claude Code, Cursor, OpenClaw, and Hermes.

## Known Limitations To Document

- A direct write remains authoritative in Markdown but reports a pending projection until PostgreSQL and Qdrant reconciliation succeeds.
- Embedding/search readiness depends on the configured embedding provider; the default expects local Ollama with `mxbai-embed-large:335m`.
- Historical retrieval is explicit opt-in; normal search excludes archived, deleted, and superseded revisions.
- Legacy Qdrant collections and the NetworkX graph JSON are retained read-only for one rollback window.
- MCP registration is per-client; there is no universal OS-level MCP registry.
- Authentication is not enabled by default because UAMS is local-first.
