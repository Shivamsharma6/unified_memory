# Public Release Checklist

## Must Have

- [x] Pick a repository name and update clone URLs in `README.md`.
- [x] Confirm `LICENSE` matches the intended open-source license.
- [ ] Run `./install.sh` on a clean machine or clean virtual environment.
- [ ] Run `./uams start`, open `http://localhost:8000/docs`, and verify `/health`.
- [ ] Run `./uams index` against the sample vault.
- [ ] Run `./uams mcp-config all` and verify the generated snippets use absolute paths.
- [ ] Register the MCP server in at least one MCP client and verify tool discovery.
- [ ] Run `memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests -q`.
- [ ] Run `memory_watcher/.venv/bin/pip check`.
- [ ] Remove local logs, caches, generated HTML, and private memory notes from the commit.
- [ ] Review all Markdown memories for secrets and private project details.

## Should Have

- [ ] Add screenshots or terminal recordings for setup and MCP discovery.
- [ ] Publish a `v0.1.0` GitHub release with known limitations.
- [x] Add CI for linting, tests, and package installation.
- [x] Add issue templates for bugs, feature requests, and adapter requests.
- [ ] Add more agent-specific examples for Codex, Claude Code, Cursor, OpenClaw, and Hermes.

## Known Limitations To Document

- `/summarize` and `/procedures` still have simple placeholder behavior.
- Direct write indexing falls back to vault-only writes if Qdrant is unavailable.
- MCP registration is per-client; there is no universal OS-level MCP registry.
- Authentication is not enabled by default because UAMS is local-first.
