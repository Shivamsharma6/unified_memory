# Architecture Design: Open-Source Polish, Zero-Friction Onboarding, Framework Adapters & Community Infrastructure

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Goal & Strategic Objective
Transform **UAMS (Unified Agent Memory System)** into a developer-first open source project with:
1. **Zero-Friction 1-Command Onboarding**: Top-level `docker-compose.yml`, `Dockerfile`, and interactive CLI demo (`uams demo`).
2. **First-Class Framework Adapters**: Native drop-in connectors for LangChain, LlamaIndex, and CrewAI.
3. **Contributor Infrastructure**: Detailed `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and rich GitHub Issue/PR templates.
4. **README Polish & Social Proof**: Clear architecture diagrams, competitive comparison matrix (vs. Mem0, Zep, Graphiti), and live badges.
5. **External Beta Testing Program**: Alpha tester guide, `uams doctor` diagnostic health inspector, and multi-agent reference examples.

---

## 2. Technical Architecture & Component Design

```
                                  AI Agent Ecosystem
           ┌───────────────────────────────┬───────────────────────────────┐
           │                               │                               │
     LangChain / Graph                LlamaIndex                        CrewAI
  (UAMSLangChainRetriever)      (UAMSLlamaIndexRetriever)       (UAMSCrewAIMemoryStorage)
           │                               │                               │
           └───────────────────────┬───────┴───────────────────────────────┘
                                   │
                                   ▼
                         UAMS Python SDK & MCP
                      (uams_sdk/client.py & mcp)
                                   │
                                   ▼
                        UAMS FastAPI Control Plane
                        (memory_watcher/api/main.py)
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
         Markdown Knowledge Vault      Postgres Control Plane &
         (Obsidian-Compatible)         Qdrant Vector DB (Dockerized)
```

---

## 3. Subsystem Breakdown

### 1. Docker & Quickstart Sandbox
- Root `docker-compose.yml`:
  - `postgres`: PostgreSQL 16 with `pgvector`.
  - `qdrant`: Qdrant vector database.
  - `uams-server`: Containerized UAMS FastAPI service + reconciler watcher daemon.
- `Dockerfile`: Multi-stage Python 3.11 build.
- `uams_sdk/demo.py`: Interactive 2-agent memory simulation for instant onboarding.

### 2. Framework Adapters (`uams_sdk/adapters/`)
- `langchain.py`:
  - `UAMSMemory`: Subclasses `BaseChatMessageHistory` / memory hooks for LangChain.
  - `UAMSRetriever`: Subclasses `BaseRetriever` to query UAMS hybrid search with metadata filters.
- `llamaindex.py`:
  - `UAMSRetriever`: Compatible with LlamaIndex query engines.
- `crewai.py`:
  - `UAMSCrewAIMemory`: Plugs into CrewAI agent memory management.

### 3. Contributor & Community Files
- `CONTRIBUTING.md`: Development environment setup, test instructions (`pytest`), architecture map.
- `CODE_OF_CONDUCT.md`: Standard Contributor Covenant v2.1.
- `.github/ISSUE_TEMPLATE/` (`bug_report.md`, `feature_request.md`, `connector_request.md`).
- `.github/pull_request_template.md`.

### 4. Developer Experience & Diagnostics Tooling
- `uams_sdk/diagnostics.py`: `uams doctor` command to check connectivity to API, PostgreSQL, Qdrant, Ollama/LLM, and vault directory.
- `examples/multi_agent_team_demo.py`: End-to-end multi-agent collaboration script showing real-time cross-agent memory sharing.
