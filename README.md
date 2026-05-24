# Unified Agent Memory System

**Unified Agent Memory System (UAMS)** is a local-first shared brain for AI agents. It gives tools like OpenClaw, Hermes, Claude Code, Codex, VoiceAI, and custom agents one durable memory layer for codebase knowledge, bug-fix history, procedures, decisions, and entity relationships.

The goal is simple: when an agent fixes bug A today, every agent can retrieve what changed, why it changed, and how to avoid repeating the investigation tomorrow.

## What It Does

- **Shared memory vault:** Human-readable Markdown notes with YAML frontmatter, Obsidian wikilinks, and strict agent-writing rules in `AGENTS.md`.
- **Auto-growing knowledge:** A watcher indexes new or changed memories into Qdrant and updates a NetworkX knowledge graph.
- **Hybrid retrieval:** Agents query one API that combines semantic search, entity extraction, graph expansion, reranking, and context compression.
- **Bug-fix recall:** Procedural memories and task notes make searches smaller and more accurate because past fixes become durable project knowledge.
- **Agent SDK:** Python SDK and middleware for automatic pre-task memory injection and post-task memory distillation.
- **One-command local setup:** `./install.sh` creates the Python environment, installs the watcher/API dependencies, and installs the SDK.

## Architecture

```text
Markdown Vault
  AGENTS.md, Concepts/, Projects/, Tasks/, Daily/
        |
        v
Memory Watcher + Reindex Command
        |
        +--> Semantic Chunker --> Embeddings --> Qdrant
        |
        +--> Graph Extractor --> NetworkX Knowledge Graph
        |
        v
Unified Retrieval API
        |
        v
Agent SDK / Middleware
  OpenClaw, Hermes, Claude Code, Codex, VoiceAI, custom agents
```

## Quick Start

Requirements:

- Python 3.11+
- Docker or OrbStack for Qdrant
- macOS or Linux

Install:

```bash
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory
./install.sh
```

Start everything:

```bash
./uams start
```

Open the API docs:

```text
http://localhost:8000/docs
```

Index the whole vault:

```bash
./uams index
```

Check status or stop services:

```bash
./uams status
./uams stop
```

Docker and Qdrant are automated by `./uams start`. UAMS uses Docker Compose to run Qdrant locally, with ports bound to `127.0.0.1` by default:

```text
Qdrant HTTP: http://127.0.0.1:6333
Qdrant gRPC: 127.0.0.1:6334
```

Optional overrides live in `.env`:

```bash
cp .env.example .env
```

The default image follows Qdrant’s documented Docker setup, which uses `qdrant/qdrant:latest`. For stricter production pinning, set `QDRANT_IMAGE=qdrant/qdrant:<version>` in `.env`.

Run the MCP adapter for MCP-aware agents:

```bash
./uams mcp
```

Print ready-to-paste MCP registration snippets:

```bash
./uams mcp-config all
```

Check the local install:

```bash
./uams doctor
```

## Agent Integration

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

- `get_context`: retrieve compressed task context before work.
- `get_procedures`: retrieve relevant rules and procedures.
- `search_memory`: targeted hybrid semantic + graph search.
- `remember`: store distilled durable memory.
- `store_fix_summary`: store structured bug-fix knowledge.
- `get_related_entities`: traverse the knowledge graph.
- `summarize_memory`: summarize a topic.
- `health`: check UAMS API connectivity.

The MCP server also exposes:

- `uams://memory-policy`: default memory operating policy.
- `use_uams_memory`: prompt template that makes the agent retrieve UAMS context before acting and store durable outcomes after work.

For best results, set the agent’s system/developer instructions to treat UAMS as mandatory memory:

```text
Before each task, use UAMS `get_procedures` and `get_context`.
After durable work, use UAMS `remember` or `store_fix_summary`.
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
- `GET /health`: API health check.

## Repository Layout

```text
.
├── AGENTS.md                  # Memory-writing protocol for agents
├── install.sh                 # One-command local installer
├── uams                       # Service control: start, stop, status, index, logs, mcp
├── memory_watcher/            # Watcher, ingestion pipeline, retrieval API
├── uams_sdk/                  # Python SDK, MCP server, and agent middleware
├── Concepts/ Projects/ Tasks/ # Canonical memory vault
└── AI/                        # Derived graph, embedding, and cache areas
```

## Open Source Roadmap

- Package the API and watcher as installable Python console commands.
- Add more templates for Claude Code, Codex, OpenClaw, Hermes, and LangChain-style agents.
- Replace heuristic post-task distillation with configurable local or hosted LLM distillers.
- Add first-class repository scanners for code symbols, commits, PRs, and issue history.
- Add memory quality checks for missing frontmatter, orphan notes, and oversized chunks.
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

Rebuild the knowledge graph only:

```bash
cd memory_watcher
.venv/bin/python scripts/force_graph_rebuild.py
```
