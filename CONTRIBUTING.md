# Contributing to Unified Agent Memory System (UAMS)

Welcome, and thank you for considering contributing to UAMS! 🎉

UAMS is an open-source, multi-agent shared memory system that bridges human-readable **Markdown knowledge vaults** (Obsidian-compatible) with real-time **hybrid retrieval** (PostgreSQL FTS + Qdrant vectors + cross-encoder reranking + bitemporal claim graph).

---

## 🛠️ Quickstart: Development Setup

### 1. Prerequisites
- **Python 3.11+**
- **Docker & Docker Compose** (for PostgreSQL + Qdrant)
- **Git**

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies for both server and SDK
pip install -r memory_watcher/requirements.txt
pip install -e "uams_sdk[dev]"
```

### 3. Spin up Infrastructure (Optional for local testing)
```bash
docker compose up -d postgres qdrant
```

### 4. Run the Full Test Suite
```bash
pytest memory_watcher/tests/ -v
```

---

## 🧠 System Architecture: How UAMS Works

```
                               AI Agents (Hermes, OpenClaw, VoiceAI, LangChain, etc.)
                                                        │
                                                        ▼
                                           UAMS Python SDK / MCP Server
                                                        │
                                                        ▼
                                           FastAPI Ingestion & Retrieval API
                                                        │
                                ┌───────────────────────┴───────────────────────┐
                                ▼                                               ▼
                    Authoritative Markdown Vault                    Derived Storage Projections
                    (Obsidian Wikilinks, Frontmatter)               (PostgreSQL Control + Qdrant)
```

1. **Source of Truth**: Markdown files in the vault (`Concepts/`, `Daily/`, `Tasks/`, `Identity/`, `Archive/`). All notes contain YAML frontmatter and Obsidian `[[wikilinks]]`.
2. **Reconciler & Outbox**: Scans and hashes Markdown files into immutable revisions. Staged outbox rows are vectorized asynchronously or synchronously (`sync=True`).
3. **Hybrid Retrieval**: Combines BM25/FTS in PostgreSQL, Dense Cosine Search in Qdrant, RRF fusion, Temporal Recency Boosts, Graph-profile expansion, and MS-MARCO Cross-Encoder reranking.
4. **Bitemporal Claims**: Automatic evolution and contradiction detection (`valid_from`, `valid_to`, `invalidated_by_claim_id`).

---

## 📐 Coding & Contribution Guidelines

### 1. Strict Test-Driven Development (TDD)
- All new features and bug fixes **must** include automated pytest tests under `memory_watcher/tests/`.
- Ensure tests run fast and isolate filesystem operations using `tmp_path`.

### 2. Follow AGENTS.md Conventions
- Memories written to the vault must follow [AGENTS.md](file:///Users/shivamsharma/projects/unified_memory/AGENTS.md):
  - Always include YAML frontmatter (`type`, `tags`, `entities`, `timestamps`).
  - Use Obsidian wikilinks `[[Entity Name]]` for relationships.
  - Keep sections modular with `##` headers.

### 3. Git Commit Messages
We follow Conventional Commits:
- `feat(scope): add new feature`
- `fix(scope): fix bug or edge-case`
- `test(scope): add automated test suite`
- `docs(scope): update documentation or examples`
- `refactor(scope): refactor code without changing behavior`

---

## 🤝 Areas Where We Need Help

We welcome contributions across all areas, especially:
- **Framework Connectors**: Adapters for AutoGen, Semantic Kernel, DSPy, Haystack, or custom agent runtimes.
- **Web UI & Graph Visualizers**: Next.js / Streamlit web interface to inspect active memories, entity graphs, and audit trails.
- **Local Embedding & Cross-Encoder Optimizations**: Apple Silicon (MLX), ONNX Runtime, and TensorRT acceleration.
- **Benchmarking**: Evaluation datasets and comparative benchmarks against Mem0, Zep, and Graphiti.

---

## 📬 Submitting a Pull Request
1. Fork the repo and create your feature branch: `git checkout -b feat/your-feature-name`.
2. Ensure all tests pass: `pytest memory_watcher/tests/ -v`.
3. Push your branch: `git push origin feat/your-feature-name`.
4. Open a Pull Request on GitHub and fill in the PR template.
