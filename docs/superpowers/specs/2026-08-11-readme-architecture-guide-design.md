---
type: architecture
status: approved
aliases:
  - UAMS README Redesign
  - UAMS Technical Guide Design
tags:
  - "#documentation"
  - "#architecture"
  - "#uams"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[PostgreSQL]]"
  - "[[Qdrant]]"
  - "[[Model Context Protocol]]"
related_to:
  - "[[Unified Agent Memory Reliability Design]]"
timestamps:
  created: 2026-08-11
  updated: 2026-08-11
---

# UAMS README and Architecture Guide Design

## TL;DR

Rewrite `README.md` as a progressive, technically authoritative guide that gets a single-machine operator running quickly and then explains how developers connect agents, reason about the transactional memory lifecycle, operate the services, and recover all derived state from Markdown.

Key decisions:

- Keep [[Markdown]] as the documented and implemented source of truth.
- Explain [[PostgreSQL]] as the exact, transactional control plane and [[Qdrant]] as the semantic vector projection.
- Serve operators first without hiding the architecture from integrators.
- Add one editable draw.io deployment-topology diagram and one inline Mermaid revision-lifecycle diagram.
- Remove duplicated MCP instructions and unsupported or overly broad product claims.
- Validate every documented command, endpoint, tool, environment variable, and local link against the repository or a live local service.

Next action: implement the approved hierarchy, diagrams, examples, and verification gates without modifying unrelated vault content.

## Problem

The current README contains the correct high-level Markdown/PostgreSQL/Qdrant split, but it is difficult to use as either an installation guide or an architecture reference.

Specific problems include:

- Installation, MCP registration, and MCP usage are repeated in multiple sections.
- Operational commands are mixed with optional intelligence features before the reader has a working system.
- Some descriptions imply that every write uses subsystems that are not part of the core reconciled serving path.
- The architecture diagram is too small to explain runtime boundaries, revision activation, outbox delivery, or retrieval fusion.
- Recovery, persistent volumes, readiness, projection drift, profiles, and evidence-backed graph claims are not explained deeply enough.
- The README does not provide a reliable end-to-end path from cloning the repository to connecting an agent and verifying memory retrieval.

## Audience

The guide serves two primary audiences with one progressive reading flow.

### Single-Machine Operators

Operators need to:

- Understand prerequisites and supported runtime assumptions.
- Install dependencies and the local embedding model.
- Configure localhost-only PostgreSQL and Qdrant services.
- Migrate the Markdown vault, start services, and verify deep readiness.
- Inspect logs, stop or restart services, preserve volumes, and rebuild projections.

### Agent Integrators and Developers

Integrators need to:

- Understand the MCP `begin_task` to `end_task` lifecycle.
- Generate and audit client-specific MCP configuration.
- Use the Python SDK or REST API when MCP is not appropriate.
- Understand exact, lexical, semantic, graph, and profile retrieval behavior.
- Trace every result to current Markdown revision evidence.
- Develop and test changes without confusing core and optional subsystems.

## Information Architecture

The README uses the following order.

### 1. Product Contract

Open with a concise statement of what UAMS guarantees:

- One shared local memory for multiple agents.
- Markdown is authoritative and human/Git readable.
- PostgreSQL and Qdrant are rebuildable derived stores.
- Default deployment is one machine and localhost-only.
- Normal retrieval excludes superseded, archived, and deleted revisions.

### 2. Five-Minute Installation

Provide one linear path:

1. Install Python 3.11+, Docker Desktop or OrbStack, and Ollama.
2. Pull `mxbai-embed-large:335m` for the default 1024-dimensional embeddings.
3. Clone the repository.
4. Copy `.env.example` to `.env` and change the local PostgreSQL password.
5. Run `./uams install` or `make install`.
6. Run `./uams migrate`.
7. Run `./uams start`.
8. Verify `./uams doctor`, `./uams status`, and `GET /ready`.

Windows commands may be listed as compatibility alternatives, but the verified macOS/Linux shell path remains primary. The README must not imply equal supervision behavior where it has not been verified.

### 3. Daily Use

Explain:

- The normal `start`, `status`, `logs`, `restart`, `stop`, and `stop --infra` commands.
- What remains running or persisted after each stop mode.
- How an atomic Markdown memory is structured.
- How watcher reconciliation turns a file revision into current searchable memory.
- A real semantic search request and a readiness request.

### 4. Connect Every Agent

Consolidate all integration material into one section:

- MCP is the recommended integration boundary.
- `./uams mcp-config all` generates configuration and `./uams integrate` audits it without mutation.
- Clients call `begin_task` before non-trivial work, `search_memory` during work, and `end_task` after durable outcomes.
- The tool table is generated from or checked against `uams_sdk/uams_sdk/mcp_server.py`.
- Python SDK and REST usage are alternatives, not competing default paths.
- Client applications may need restarting after their configuration changes.

### 5. Architecture Deep Dive

Explain the deployment topology, component responsibilities, write path, read path, and revision lifecycle. The section must make authority visually and textually unambiguous.

### 6. Memory Authoring Contract

Document the core rules from `AGENTS.md` without duplicating the entire protocol:

- Atomic, distilled notes instead of raw transcripts.
- YAML frontmatter and one stable `memory_id` for managed notes.
- Short `##` and `###` sections for semantic chunking.
- Wikilinks and explicit relationships for graph evidence.
- Structured `profile_facts` for exact profile retrieval.
- Status and archive behavior.

### 7. Operations and Recovery

Cover:

- Named Docker volumes and localhost bindings.
- Deep readiness components and drift fields.
- PostgreSQL/Qdrant outage behavior and durable retries.
- Backup scope for Markdown, PostgreSQL, and Qdrant.
- Full projection rebuild from authoritative Markdown.
- Embedding-dimension and collection-version implications.
- Upgrade sequencing and rollback cautions.

### 8. Reference

End with compact tables for:

- CLI commands.
- Environment variables grouped by API, PostgreSQL, Qdrant, embeddings, and optional LLM features.
- REST endpoints grouped by retrieval, ingestion, graph/profile, intelligence, editing, and system health.
- Repository layout.
- Test and release-gate commands.
- Security boundaries and troubleshooting.

## Architecture Diagram

Create `docs/architecture/uams-single-machine.drawio` as the editable source and export `docs/architecture/uams-single-machine.svg` for README rendering.

The diagram uses a left-to-right layout with four visual tiers:

1. Agent clients: Codex, Claude, Hermes, OpenClaw, and custom agents.
2. Integration boundary: MCP, Python SDK, and REST.
3. Host processes: FastAPI hybrid retrieval, watcher/reconciler, and authoritative Markdown vault.
4. Docker services: PostgreSQL 16 and Qdrant, with Ollama shown as the embedding provider.

Color and labels distinguish:

- Authoritative Markdown.
- Transactional/exact PostgreSQL state.
- Semantic Qdrant state.
- Integration and API boundaries.
- Write-path and read-path arrows.

Every connector is labeled with the protocol or data transition it represents. Containers must be visually nested rather than merely overlaid. The diagram must remain legible when rendered at the README content width.

## Revision Lifecycle Diagram

Use inline Mermaid so the state machine remains directly reviewable in Markdown.

The primary flow is:

```text
discovered -> staged -> vector_pending -> vector_acknowledged -> active
active -> superseded | archived | deleted
```

Failure branches remain non-current:

- PostgreSQL unavailable: Markdown remains authoritative and reconciliation retries.
- Embedding or Qdrant unavailable: the revision remains staged and the durable outbox retries.
- Malformed Markdown: the previous active revision remains current and readiness reports the error.
- Delete or restore: idempotent cleanup or reprojection commands converge before readiness becomes green.

## Technical Truth Contract

The README must distinguish three levels of behavior.

### Core Serving Path

Core behavior is active in the default API/watcher path and may be described without qualification:

- Atomic Markdown writes.
- PostgreSQL revision lifecycle and full-text/exact retrieval.
- Qdrant semantic retrieval through `memory_chunks_v2`.
- Durable vector outbox and current-revision activation.
- Evidence-backed graph claims and structured profiles.
- Hybrid retrieval and deep readiness.
- MCP, SDK, and REST integration.

### Optional Features

Optional or separately invoked features must be labeled clearly:

- LLM distillation and reflection.
- Identity extraction and injection.
- Memory-quality auditing.
- Cross-encoder reranking when `sentence-transformers` is installed.
- Cloud embedding or LLM providers.

### Legacy or Non-Core Features

Do not present legacy NetworkX JSON, old Qdrant collections, generic memory-type classes, or experimental consolidation as if they are required for the reconciled serving path.

## Error Handling in the Guide

Each setup or operation includes the expected success signal and the most likely failure action.

Examples:

- Docker unavailable: start Docker Desktop or OrbStack before `./uams start`.
- Ollama model missing: run `ollama pull mxbai-embed-large:335m`.
- Readiness false: inspect `./uams status`, `./uams logs`, and the JSON body from `/ready`.
- Projection drift: stop host writers if needed, back up state, and run `./uams migrate` against the explicit vault path.
- MCP client not connected: generate config, audit it, and restart the client.
- Profile endpoint returns 404: add structured facts to authoritative profile Markdown rather than synthesizing unsupported facts.

## Validation Strategy

Before completion:

- Parse README YAML frontmatter.
- Confirm exactly one H1 and structurally valid H2/H3 hierarchy.
- Scan for placeholders and contradictory authority statements.
- Verify every documented `./uams` command exists in the launcher.
- Verify Make targets against `Makefile`.
- Verify environment variables against `.env.example`, Compose, and configuration classes.
- Verify API routes against FastAPI routers.
- Verify MCP tools against `uams_sdk/uams_sdk/mcp_server.py`.
- Verify local Markdown links and architecture asset paths.
- Validate draw.io XML and export the SVG with the native draw.io CLI.
- Render and visually inspect the architecture diagram for clipping, overlap, and edge routing.
- Run `bash -n uams`, Docker Compose config validation, `./uams doctor`, `./uams status`, and the existing test suite in proportion to documentation-only risk.
- Confirm Git stages only the README, architecture assets, spec, and plan; preserve the unrelated deletion of `ArthaBot.md`.

## Acceptance Criteria

- A new operator can reach a ready system by following one uninterrupted installation path.
- An integrator can connect an MCP client and discover the documented tools without reading source code.
- The architecture diagram makes Markdown authority and the PostgreSQL/Qdrant split obvious.
- The write path explains why a failed vector projection cannot silently become current.
- The read path explains semantic, lexical, exact, graph, profile, and current-revision filtering.
- Recovery instructions rebuild derived state without treating PostgreSQL or Qdrant as canonical.
- Core, optional, and legacy features are not conflated.
- Commands, routes, configuration, links, and diagrams pass the validation strategy.
- No unrelated workspace change is staged or committed.
