---
type: procedural
status: approved
aliases:
  - UAMS README Implementation Plan
tags:
  - "#documentation"
  - "#architecture"
  - "#uams"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[PostgreSQL]]"
  - "[[Qdrant]]"
related_to:
  - "[[UAMS README and Architecture Guide Design]]"
timestamps:
  created: 2026-08-11
  updated: 2026-08-11
---

# UAMS README and Architecture Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current README with a verified progressive operator-and-integrator guide and add an editable single-machine architecture diagram.

**Architecture:** The README leads with a working local installation, then agent integration, then the transactional Markdown/PostgreSQL/Qdrant architecture, memory authoring, operations, recovery, and reference material. A draw.io topology diagram shows runtime boundaries and data flow; an inline Mermaid state machine explains revision activation and failure behavior.

**Tech Stack:** GitHub-flavored Markdown, YAML frontmatter, Mermaid, draw.io XML/SVG, Bash, Docker Compose, FastAPI, MCP, Python 3.11

---

## File Map

- Modify: `README.md` — authoritative project entry point and complete progressive guide.
- Create: `docs/architecture/uams-single-machine.drawio` — editable source for the deployment topology.
- Create: `docs/architecture/uams-single-machine.svg` — crisp README-rendered architecture asset.
- Temporary, do not commit: `docs/architecture/uams-single-machine-preview.png` — visual QA export without embedded draw.io metadata.
- Preserve unchanged: `ArthaBot.md` — unrelated user deletion in the main workspace must never be staged by this plan.

### Task 1: Establish an Isolated Documentation Workspace

**Files:**

- Existing branch: `codex/readme-architecture-guide`
- Worktree: `.worktrees/readme-architecture-guide`

- [ ] **Step 1: Confirm the design and plan commits are on the documentation branch**

Run:

```bash
git log -2 --oneline
git status --short
```

Expected: the design and plan commits are present; the only unrelated main-workspace change is ` D ArthaBot.md`.

- [ ] **Step 2: Return the main workspace to `main` without staging user changes**

Run:

```bash
git switch main
```

Expected: `ArthaBot.md` remains deleted and unstaged in the main workspace.

- [ ] **Step 3: Create an isolated worktree for the documentation branch**

Follow the `using-git-worktrees` skill and create:

```text
/Users/shivamsharma/projects/unified_memory/.worktrees/readme-architecture-guide
```

Expected: the worktree is clean and checks out `codex/readme-architecture-guide`.

- [ ] **Step 4: Verify baseline documentation inputs**

Run from the worktree:

```bash
git status --short
bash -n uams
docker compose -f memory_watcher/docker-compose.yml config --quiet
memory_watcher/.venv/bin/python -c "import yaml; print('yaml=ok')"
```

Expected: clean Git status and zero command failures.

### Task 2: Create the Single-Machine Architecture Diagram

**Files:**

- Create: `docs/architecture/uams-single-machine.drawio`
- Create: `docs/architecture/uams-single-machine.svg`
- Temporary: `docs/architecture/uams-single-machine-preview.png`

- [ ] **Step 1: Resolve diagram tooling and style**

Run:

```bash
command -v drawio || test -x /Applications/draw.io.app/Contents/MacOS/draw.io
find "$HOME/.drawio-skill/styles" -maxdepth 1 -name '*.json' -print 2>/dev/null || true
```

Expected: use the native draw.io CLI when available. If no user default preset exists, use the built-in blue/orange/green/purple palette from the draw.io skill.

- [ ] **Step 2: Generate the editable draw.io topology**

Create valid uncompressed draw.io XML with:

- Required root cells `0` and `1`.
- Four left-to-right tiers: Agent Clients, Integration Boundary, Host Processes, and Docker Services.
- Client nodes for Codex, Claude, Hermes, OpenClaw, and custom agents.
- MCP, Python SDK, and REST integration nodes.
- FastAPI Hybrid Retrieval, Watcher/Reconciler, and Markdown Vault host nodes.
- PostgreSQL 16, Qdrant `memory_chunks_v2`, and Ollama embedding nodes.
- A green, visibly emphasized Markdown authority node.
- Blue read-path connectors and green/orange write-path connectors.
- Edge labels for MCP/HTTP, atomic write, reconcile/stage, full-text/exact, semantic search, outbox delivery, embedding, acknowledgement, and current-revision validation.
- Containers implemented with `swimlane`/`container=1`, not background rectangles over unrelated nodes.

- [ ] **Step 3: Validate XML before export**

Run:

```bash
xmllint --noout docs/architecture/uams-single-machine.drawio
```

Expected: exit code 0.

- [ ] **Step 4: Export a clean preview and inspect it**

Run the available draw.io executable without `--embed-diagram`:

```bash
drawio --export --format png --output docs/architecture/uams-single-machine-preview.png docs/architecture/uams-single-machine.drawio
```

Expected: a readable PNG with no clipped labels, overlapping nodes, stacked arrows, disconnected edges, or off-canvas content. Use visual inspection and make no more than two automatic correction rounds.

- [ ] **Step 5: Export the final SVG**

Run:

```bash
drawio --export --format svg --embed-diagram --output docs/architecture/uams-single-machine.svg docs/architecture/uams-single-machine.drawio
```

Expected: SVG exists, contains an `<svg` root, and remains editable through its embedded draw.io data.

- [ ] **Step 6: Remove the temporary preview and commit diagram assets**

Remove only the generated preview after visual QA, then run:

```bash
git add docs/architecture/uams-single-machine.drawio docs/architecture/uams-single-machine.svg
git commit -m "docs(architecture): add single-machine memory topology"
```

Expected: only the two architecture assets are committed.

### Task 3: Rewrite the README as a Progressive Guide

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Preserve valid metadata and replace the content hierarchy**

Keep YAML frontmatter with `type: semantic`, `status: active`, UAMS aliases, quoted tags, architecture entities, and the `2026-08-11` update timestamp.

Use exactly one H1 and this ordered H2 hierarchy:

```markdown
# Unified Agent Memory System

## What UAMS Guarantees
## Architecture at a Glance
## Five-Minute Installation
## Verify the Installation
## Daily Operation
## Connect Every Agent
## How the Architecture Works
## Authoritative Memory Format
## Retrieval Model
## Knowledge Graph and Profiles
## Operations, Backup, and Recovery
## Configuration Reference
## API Reference
## Repository Layout
## Development and Release Gates
## Security and Current Limitations
## Contributing
```

- [ ] **Step 2: Write the product contract and embed the topology**

State explicitly:

```text
Markdown is authoritative. PostgreSQL and Qdrant are rebuildable projections.
PostgreSQL owns exact/current/lifecycle truth. Qdrant owns semantic similarity.
Redis, Neo4j, and multi-machine coordination are not required for the supported deployment.
```

Embed the SVG with descriptive alt text and link its caption to the editable `.drawio` source.

- [ ] **Step 3: Write one verified installation path**

Document these exact commands:

```bash
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory
cp .env.example .env
ollama pull mxbai-embed-large:335m
./uams install
./uams migrate --vault "$PWD"
./uams start
./uams doctor
./uams status
curl -fsS http://127.0.0.1:8000/ready
```

Explain that Docker/OrbStack and Ollama must already be running. Tell operators to change `UAMS_POSTGRES_PASSWORD` in `.env` before first database creation.

- [ ] **Step 4: Document daily lifecycle commands in one table**

Include `install`, `start`, `stop`, `stop --infra`, `restart`, `status`, `migrate`, `logs`, `mcp`, `mcp-config`, `doctor`, and `integrate`. Explain that normal stop preserves and leaves database containers running, while `--infra` stops containers but preserves named volumes.

- [ ] **Step 5: Consolidate all agent integration guidance**

Document the default lifecycle:

```text
begin_task -> act/search_memory -> end_task
```

Include one JSON MCP configuration, one Codex TOML configuration, `./uams mcp-config all`, `./uams integrate`, a table of all tools currently decorated with `@mcp.tool()`, the `uams://memory-policy` resource, and the `use_uams_memory` prompt. Explain that client restart/reload may be necessary.

Include one Python SDK example that calls `begin_task`, `search`, and `end_task`, using method names verified in `uams_sdk/uams_sdk/client.py`.

- [ ] **Step 6: Explain the complete write path**

Describe:

```text
atomic Markdown write
  -> watcher/reconciler parse and chunk
  -> PostgreSQL staged revision + claims/profiles/jobs/outbox transaction
  -> Ollama embedding
  -> Qdrant idempotent upsert
  -> outbox acknowledgement
  -> PostgreSQL activates the revision
  -> previous vector projection is cleaned up
```

Add the approved Mermaid revision state machine, including retry/failure branches that never become current.

- [ ] **Step 7: Explain the complete read path**

Describe parallel PostgreSQL lexical/exact retrieval and Qdrant semantic retrieval, rank fusion, current-revision validation, graph/profile evidence enrichment, reranking, and optional compression. Explain the difference between exact profile facts and narrative semantic matches.

- [ ] **Step 8: Document the authoritative memory format**

Include a complete Markdown example with:

```yaml
memory_id: 11111111-1111-4111-8111-111111111111
type: procedural
status: active
aliases:
  - Session Refresh Fix
tags:
  - "#bugfix"
entities:
  - "[[Authentication Service]]"
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
relationships:
  - predicate: fixes
    target: "[[Login Timeout Regression]]"
    status: explicit
```

Use short H2 sections in the example body. Explain stable IDs, wikilinks, explicit graph relationships, and structured `profile_facts` for exact profile retrieval.

- [ ] **Step 9: Write operations and recovery procedures**

Document:

- PostgreSQL and Qdrant named volumes.
- Deep readiness fields and zero-drift meaning.
- Docker, PostgreSQL, Qdrant, Ollama, and malformed-Markdown failure behavior.
- A backup sequence that captures Markdown/Git plus PostgreSQL and Qdrant volume or snapshot data.
- A rebuild sequence that starts infrastructure and runs `./uams migrate --vault "$PWD"`.
- Embedding model/dimension changes requiring a deliberate new projection version or collection rebuild.

- [ ] **Step 10: Add exact reference tables and current limitations**

Cross-check and list:

- Environment variables from `.env.example` and their defaults/sensitivity.
- Current FastAPI routes from `memory_watcher/api/main.py` and `memory_watcher/api/routers/`.
- Test commands: full pytest suite, `make test-integration`, `make evaluate`, Compose validation, and `pip check`.
- Localhost-only/no-auth security boundary.
- Heuristic reranker fallback when `sentence-transformers` is absent.
- Exact profiles require structured `profile_facts` in Markdown.
- MCP registration is per client.

- [ ] **Step 11: Remove duplicated and unsupported descriptions**

Delete the repeated MCP sections and do not claim that these are mandatory core-path behavior:

- Emotion extraction for every interaction.
- Automatic six-stage conversation ingestion for every client.
- Neural reranking when the optional package is absent.
- NetworkX JSON as the current serving graph.
- Seven Qdrant collections for seven memory types.

- [ ] **Step 12: Commit the README rewrite**

Run `git diff --check`, inspect the complete diff, then:

```bash
git add README.md
git commit -m "docs(readme): add complete operator and architecture guide"
```

Expected: only `README.md` is committed in this task.

### Task 4: Verify Documentation Against the Implementation

**Files:**

- Modify if verification finds an error: `README.md`
- Verify: `docs/architecture/uams-single-machine.drawio`
- Verify: `docs/architecture/uams-single-machine.svg`

- [ ] **Step 1: Validate frontmatter and heading structure**

Run a Python assertion that:

- Parses the first YAML frontmatter block.
- Requires `type: semantic` and `status: active`.
- Finds exactly one H1.
- Finds every approved H2 exactly once and in the approved order.

Expected: `readme_structure=ok`.

- [ ] **Step 2: Validate local Markdown and architecture links**

Parse inline Markdown links that do not contain a URL scheme or fragment, resolve them from the repository root, and fail if any target is missing.

Expected: `local_links=ok`.

- [ ] **Step 3: Validate documented CLI commands and targets**

Run:

```bash
bash -n uams
./uams 2>&1 | grep -F 'install|start|stop'
make -qp | grep -E '^(install|start|stop|restart|status|migrate|doctor|integrate|logs|test|test-integration|evaluate):'
```

Expected: every README command exists.

- [ ] **Step 4: Validate infrastructure and Python dependencies**

Run:

```bash
docker compose -f memory_watcher/docker-compose.yml config --quiet
memory_watcher/.venv/bin/python -m pip check
memory_watcher/.venv/bin/python -m compileall -q memory_watcher uams_sdk
```

Expected: zero failures.

- [ ] **Step 5: Verify live operator commands without changing memory**

Run:

```bash
./uams doctor
./uams status
curl -fsS http://127.0.0.1:8000/ready
./uams mcp-config all
./uams integrate
```

Expected: doctor passes, services are ready, generated paths are absolute, and each installed client is reported configured or missing rather than unreachable.

- [ ] **Step 6: Verify the complete MCP capability list**

Start an independent stdio MCP session with `/absolute/path/to/uams mcp`, initialize it, call `list_tools`, and compare the returned names to the README table.

Expected: no documented tool is missing and no discovered tool is omitted.

- [ ] **Step 7: Run the proportionate test and retrieval gates**

Run:

```bash
memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests tests uams_sdk/tests -q
UAMS_VAULT_PATH="$PWD" make evaluate
```

Expected: all tests pass; retrieval meets hit@1 >= 80%, hit@5 >= 90%, and zero historical leaks.

- [ ] **Step 8: Review the rendered README and diagram**

Check:

- SVG renders in the README preview.
- Mermaid syntax is valid and labels are readable.
- Code fences are balanced.
- No section duplicates installation, MCP, or architecture material.
- No paragraph exceeds 300 words without an H2/H3 structural break.

- [ ] **Step 9: Confirm workspace isolation**

Run:

```bash
git status --short
git diff --check
git diff --name-only main...HEAD
```

Expected branch-owned paths:

```text
README.md
docs/architecture/uams-single-machine.drawio
docs/architecture/uams-single-machine.svg
docs/superpowers/plans/2026-08-11-readme-architecture-guide.md
docs/superpowers/specs/2026-08-11-readme-architecture-guide-design.md
```

The main workspace's unrelated `ArthaBot.md` deletion must not appear in the branch diff.

- [ ] **Step 10: Commit verification corrections only if needed**

If verification required corrections, commit only the corrected documentation:

```bash
git add README.md docs/architecture/uams-single-machine.drawio docs/architecture/uams-single-machine.svg
git commit -m "docs(readme): correct verified commands and references"
```

If no tracked file changed, do not create an empty commit.

### Task 5: Final Review and Handoff

**Files:**

- Review: `README.md`
- Review: `docs/architecture/uams-single-machine.drawio`
- Review: `docs/architecture/uams-single-machine.svg`

- [ ] **Step 1: Apply the verification-before-completion skill**

Re-run fresh Git status, README structure/link checks, XML validation, SVG existence/render checks, test summary, retrieval summary, live readiness, and MCP audit. Base every completion statement on this fresh output.

- [ ] **Step 2: Apply the requesting-code-review skill locally**

Because multi-agent delegation is disabled, review the branch diff directly for:

- Technical contradictions.
- Commands that mutate or delete more than described.
- Missing prerequisites.
- Misstated authority or lifecycle behavior.
- Broken paths, code fences, tables, or diagrams.
- Accidental inclusion of unrelated memory files.

Fix Critical and Important findings before proceeding.

- [ ] **Step 3: Finish the development branch**

Use the `finishing-a-development-branch` skill. The user already selected implementation and local integration in the active workflow, but do not discard or overwrite the unrelated main-workspace deletion. Merge only after all verification gates pass.
