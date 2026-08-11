---
type: semantic
status: active
aliases:
  - UAMS
  - Unified Memory
tags:
  - "#uams"
  - "#architecture"
  - "#operations"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[PostgreSQL]]"
  - "[[Qdrant]]"
timestamps:
  created: 2026-06-10
  updated: 2026-08-11
---

# Unified Agent Memory System

**Unified Agent Memory System (UAMS)** is a local-first shared brain for AI agents. It gives tools like OpenClaw, Hermes, Claude Code, Codex, VoiceAI, and custom agents one durable memory layer for codebase knowledge, bug-fix history, procedures, decisions, and entity relationships.

The goal is simple: when an agent fixes bug A today, every agent can retrieve what changed, why it changed, and how to avoid repeating the investigation tomorrow.

## What It Does

- **Shared memory vault:** Human-readable Markdown notes with YAML frontmatter, Obsidian wikilinks, and strict agent-writing rules in `AGENTS.md`.
- **Reconciled knowledge:** A watcher stages Markdown revisions in [[PostgreSQL]] and delivers semantic vectors to [[Qdrant]] through a durable outbox.
- **Hybrid retrieval:** [[Qdrant]] supplies semantic candidates; [[PostgreSQL]] supplies exact/full-text matches, profiles, evidenced graph claims, and current-revision validation.
- **Bug-fix recall:** Procedural memories and task notes make searches smaller and more accurate because past fixes become durable project knowledge.
- **Agent SDK:** Python SDK and middleware for automatic pre-task memory injection and post-task memory distillation.
- **One-command setup:** Cross-platform scripts (`Makefile`, `install.bat`) create the Python environment and install dependencies.

## SOTA Intelligence Features

UAMS goes beyond basic RAG with production-grade intelligence layers:

### LLM-Powered Distillation
Memory summarization and lesson extraction use real LLM calls (Ollama/OpenAI) instead of keyword heuristics. Configure via environment variables:
- `UAMS_LLM_PROVIDER` — `ollama` (default), `openai` (for cloud), or `mock`
- `UAMS_LLM_MODEL` — main model name (default: `gemma4:12b-mlx`, or `gpt-4o`)
- `UAMS_LLM_BASE_URL` — LLM endpoint (default: `http://localhost:11434`)
- `UAMS_LLM_API_KEY` — API key for OpenAI-compatible providers
- `UAMS_EMBED_PROVIDER` — `ollama`, `openai`, or `fastembed`
- `UAMS_DISTILL_INTERVAL` — memory distillation frequency in file changes (default: `10`)

**Model Roles & Defaults:**
- **Embedding:** `mxbai-embed-large:335m` (1024-dim, high quality)
- **Reflection:** `gemma4:12b-mlx` (self-assessment and memory review via `/reflect`)
- **Fallback:** `glm-4.7-flash:latest` (fast, cheap, highly available)
- **Idle Timeout:** `300s` (optimizes memory lifecycle for large models)

### Cross-Encoder Neural Reranking
Retrieval results are reranked using `cross-encoder/ms-marco-MiniLM-L-6-v2` for more accurate relevance scoring. Falls back to heuristic word overlap if `sentence-transformers` is not installed.

### Identity Kernel
A 12-domain identity system that extracts traits from episodic memories, tracks stability over time, detects contradictions, and injects personalized context into agent reasoning. Agents become consistent personalities, not stateless tools.

### Memory Quality Scoring
Every memory note is scored on frontmatter completeness, link density, structural quality, and content length. Use `/memory/quality` to audit your vault.

### Self-Editing Memory
Agents can correct, update, or delete their own memories via `/memory/edit`, `/memory/delete`, and `/memory/add-link` — with full audit trail in `Logs/memory_edits.md`.

### Temporal Awareness
Recent memories are automatically boosted in retrieval to prevent stale context from dominating. Exponential decay ensures today's work surfaces first.

### Semantic Procedure Matching
Procedures are matched by embedding similarity, not just keyword overlap. The system tries neural reranking and falls back to keyword scoring.

## Architecture

```text
Markdown Vault (authoritative)
  AGENTS.md, Concepts/, Projects/, Tasks/, Daily/
        |
        v
Reconciler + Semantic Chunker
        |
        +--> PostgreSQL control plane
        |      revisions, FTS, profiles, claims, jobs, outbox
        |
        +--> Qdrant memory_chunks_v2
               semantic vectors (derived projection)
        |
        v
Hybrid Retrieval API --> Agent SDK / MCP
```

Markdown is the only authoritative memory record. PostgreSQL and Qdrant are rebuildable projections. A revision becomes current only after its complete vector projection is acknowledged; normal retrieval rejects archived, deleted, and superseded revisions.

## Quick Start

Requirements:

- Python 3.11+
- Docker or OrbStack for PostgreSQL and Qdrant
- macOS, Linux, or Windows

Install:

```bash
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory
make install      # Mac/Linux
# or
install.bat       # Windows
```

Start everything:

```bash
make start        # Mac/Linux
# or
uams.bat start    # Windows
```

Open the API docs:

```text
http://localhost:8000/docs
```

Reconcile and migrate the whole vault:

```bash
./uams migrate
```

Check status or stop services:

```bash
./uams status
./uams stop
./uams stop --infra  # explicitly stop PostgreSQL and Qdrant too
```

`./uams start` starts both databases, applies schema migrations, starts the watcher and API, and waits for deep readiness. Docker ports are bound to `127.0.0.1` by default:

```text
PostgreSQL: 127.0.0.1:5432
Qdrant HTTP: http://127.0.0.1:6333
Qdrant gRPC: 127.0.0.1:6334
```

Optional overrides live in `.env`:

```bash
cp .env.example .env
```

The Qdrant default is pinned to an exact tested image digest, and PostgreSQL defaults to `postgres:16-bookworm`. Override them in `.env` only as a deliberate upgrade.

Run the MCP adapter for MCP-aware agents:

```bash
./uams mcp
```

Print ready-to-paste MCP registration snippets:

```bash
./uams mcp-config all
```

Audit UAMS MCP registration for installed local agents without modifying their configuration:

```bash
./uams integrate
```

Check the local install:

```bash
./uams doctor
```

## Agent Integration

### MCP Server

The UAMS MCP server exposes a **begin-then-end task lifecycle**: agents call `begin_task` before acting, then call `end_task` after durable work. This gives agents one obvious default memory habit instead of several optional tools.

**Protocol:**

1. **Begin** — Call `begin_task` with the user task.
2. **Act** — Use the returned procedures and context as grounding before coding or answering.
3. **Recall** — Use `search_memory` during work when more targeted recall is needed.
4. **End** — After durable work, call `end_task` with distilled, non-transcript outcomes.

**Available Tools:**

| Tool | Direction | Description |
|------|-----------|-------------|
| `begin_task` | Read | Default first call before work; retrieves procedures, compressed context, and memory policy. |
| `end_task` | Write | Default final call after durable work; stores a distilled task outcome. |
| `search_memory` | Read | Targeted hybrid semantic + graph search. |
| `get_context` | Read | Lower-level context retrieval. |
| `get_procedures` | Read | Lower-level procedure retrieval. |
| `remember` | Write | Store distilled durable memory. |
| `store_fix_summary` | Write | Store structured bug-fix knowledge. |
| `get_related_entities` | Read | Traverse the knowledge graph. |
| `summarize_memory` | Read | Summarize a topic. |
| `health` | Read | Check UAMS API connectivity. |

**Codex Configuration (already applied):**

The UAMS MCP server is configured in `~/.codex/config.toml`:

```toml
[mcp_servers.uams]
command = "/path/to/unified_memory/uams"
args = ["mcp"]
env = {UAMS_API_URL = "http://localhost:8000"}
```

Verify with:

```bash
./uams mcp-config codex
```

**Other Agents:**

Generate MCP config for other agents:

```bash
./uams mcp-config json        # Claude Code / Cursor / Windsurf
./uams mcp-config all          # All formats
./uams integrate               # Auto-integrate with local agents
```


### MCP Adapter

The recommended default integration is MCP. Configure the agent to launch UAMS over stdio:

```json
{
  "mcpServers": {
    "uams": {
      "command": "/absolute/path/to/unified_memory/uams",
      "args": ["mcp"],
      "env": {
        "UAMS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Generate this snippet with:

```bash
./uams mcp-config json
```

For Codex, generate TOML for `~/.codex/config.toml`:

```bash
./uams mcp-config codex
```

Once connected, agents discover these tools automatically:

- `begin_task`: default first call before work; retrieves procedures, context, and memory policy.
- `end_task`: default final call after durable work; stores distilled task outcomes.
- `search_memory`: targeted hybrid semantic + graph search.
- `get_context`: lower-level compressed task context retrieval.
- `get_procedures`: lower-level procedure retrieval.
- `remember`: store distilled durable memory.
- `store_fix_summary`: store structured bug-fix knowledge.
- `get_related_entities`: traverse the knowledge graph.
- `summarize_memory`: summarize a topic.
- `health`: check UAMS API connectivity.

The MCP server also exposes:

- `uams://memory-policy`: default memory operating policy.
- `use_uams_memory`: prompt template that makes the agent call `begin_task` before acting and `end_task` after durable outcomes.

For best results, set the agent’s system/developer instructions to treat UAMS as mandatory memory:

```text
Before each non-trivial task, call UAMS `begin_task`.
During work, call UAMS `search_memory` when more recall is needed.
After durable work, call UAMS `end_task`.
Do not store raw transcripts; store distilled atomic knowledge only.
```

Start the API/watch service first:

```bash
./uams start
```

MCP registration is **per agent/client**. There is no universal machine-wide registry that every agent reads. Production setups should either:

- commit a project-level MCP config where the client supports it,
- add the generated snippet to the user-level agent config,
- or wrap the agent launcher so it starts with the UAMS MCP server enabled.

Python agents can use the SDK directly:

```python
import asyncio
from uams_sdk import UAMSClient

async def main():
    client = UAMSClient("http://localhost:8000")

    context = await client.retrieve_context("Fix the login timeout regression")
    print(context)

    await client.store_memory(
        "Resolved [[Login Timeout Regression]] by increasing the session refresh grace window.",
        category="procedural",
        tags=["#bugfix", "#auth"],
    )

asyncio.run(main())
```

Middleware can automatically:

- retrieve procedures before the agent starts work,
- inject compressed historical context into the prompt,
- extract durable insights after the task,
- store distilled memories back into the vault.

See [uams_sdk/README.md](uams_sdk/README.md) and [memory_watcher/integrations/openclaw](memory_watcher/integrations/openclaw) for examples.

## Memory Model

UAMS supports **7 application memory categories**. Current semantic chunks share one Qdrant collection, `memory_chunks_v2`; `memory_type` remains an indexed payload/filter and PostgreSQL column.

| Category | Purpose |
|----------|---------|
| `semantic` | Facts, concepts, domain knowledge |
| `episodic` | Experiences, events, interactions |
| `procedural` | How-to knowledge, workflows, procedures |
| `identity` | Stable personality traits and preferences |
| `goal` | Ongoing objectives and project states |
| `reflection` | Self-analysis, lessons learned, patterns |
| `relationship` | Person-specific dynamics and communication styles |

### Episodic Memory Schema

Episodic memories store **experiences**, not raw transcripts. Each record captures:

- **Emotional state**: frustration, excitement, confidence, stress, satisfaction (0.0–1.0)
- **Context**: platform, location, tools used, session ID
- **Outcome**: success flag, resolution, consequences, lessons learned
- **Importance**: weighted score (0.0–1.0) determining long-term survival
- **Relationships**: linked memory IDs, participants, source agent

```python
from memory_watcher.memory_types import (
    EpisodicMemory, EmotionalState, ContextData, OutcomeData,
)

mem = EpisodicMemory(
    event_type="decision",
    summary="Chose Qdrant over Pinecone for vector storage",
    participants=["Shivam", "Hermes"],
    emotional_state=EmotionalState(excitement=0.8, confidence=0.9),
    importance=0.85,
    context=ContextData(platform="cli", tools_used=["qdrant"]),
    outcome=OutcomeData(success=True, lessons_learned=["Qdrant has better local support"]),
    source="hermes",
)
```

### Memory Ingestion Pipeline

Every meaningful interaction flows through a 6-stage pipeline:

```
Conversation → Summarization → Emotion extraction →
Importance scoring → Memory classification → Storage
```

The pipeline auto-classifies content into the appropriate memory type and creates structured records with emotional metadata and importance scores.

### Importance Scoring

Memories are scored on a 0.0–1.0 scale using:

```
importance = emotional_weight * 0.3 + novelty * 0.2 + goal_relevance * 0.3 + repetition * 0.2
```

- **Emotional weight**: average intensity of all emotion dimensions
- **Novelty**: ratio of unique/rare words to common words
- **Goal relevance**: proximity to stated objectives and priorities
- **Repetition**: how often the topic has been mentioned

Category-specific thresholds determine which memories survive consolidation (e.g., episodic: 0.3, reflection: 0.4).

### Memory Consolidation

Periodic consolidation jobs compress raw memories into stable knowledge:

```
Raw memories → Cluster similar → Summarize patterns →
Create abstractions → Reduce redundancy
```

Example: 50 conversations about optimization → *"User consistently prioritizes system efficiency over simplicity."*

The `MemoryConsolidator` provides:

- `consolidate()`: full consolidation pipeline with statistics
- `get_low_value_memories()`: retrieve memories below importance threshold
- `promote_to_concept()`: convert episodic clusters into semantic concepts

UAMS stores knowledge as atomic Markdown notes:

- `Concepts/`: stable facts, architecture, domain concepts.
- `Projects/`: active or archived project-level memory.
- `Tasks/`: reusable procedures, debugging playbooks, and coding directives.
- `Daily/`: short-term episodic notes that can later be promoted.
- `People/`, `Research/`, `Logs/`, `AI/`: supporting vault areas.

Every durable memory should include:

- YAML frontmatter with `type`, tags, aliases/entities, and timestamps where relevant.
- Wikilinks for important entities, such as `[[OpenClaw]]` or `[[Qdrant]]`.
- Short sections with `##` and `###` headers so retrieval chunks stay focused.

The full write protocol lives in [AGENTS.md](AGENTS.md).

## API Surface

- `POST /search`: semantic and graph-aware retrieval.
- `POST /context`: compressed context block for agent prompts.
- `POST /remember`: direct agent write path.
- `POST /procedures`: procedure retrieval for coding and operational tasks.
- `GET /graph/neighborhood/{entity}`: graph neighborhood lookup.
- `GET /profiles/{profile_id}`: exact current profile facts with evidence.
- `GET /memory/status/{memory_id}`: revision and projection lifecycle.
- `GET /health`: API health check.
- `GET /ready`: deep database, embedding/search, queue, and drift readiness.

## Repository Layout

```text
.
├── AGENTS.md                  # Memory-writing protocol for agents
├── install.sh                 # One-command local installer
├── uams                       # Service control: start, migrate, status, logs, mcp
├── memory_watcher/            # Reconciler, PostgreSQL control plane, Qdrant projection, API
├── uams_sdk/                  # Python SDK, MCP server, and agent middleware
├── Concepts/ Projects/ Tasks/ # Canonical memory vault
└── AI/                        # Legacy/derived embedding and cache areas
```

## Open Source Roadmap

- Package the API and watcher as installable Python console commands.
- Add more templates for Claude Code, Codex, OpenClaw, Hermes, and LangChain-style agents.
- Replace heuristic post-task distillation with configurable local or hosted LLM distillers.
- Add first-class repository scanners for code symbols, commits, PRs, and issue history.
- Publish Docker Compose profiles for local-only, team, and production setups.

## Public Release

Before publishing, run through [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) and review [SECURITY.md](SECURITY.md). The default deployment is local-first and does not include public API authentication.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). UAMS is released under the [MIT License](LICENSE).

## Development

Run unit tests from the repo root:

```bash
memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests
```

Run container lifecycle and failure recovery tests:

```bash
make test-integration
```

Run the committed retrieval-quality release gate after migration:

```bash
make evaluate
```
