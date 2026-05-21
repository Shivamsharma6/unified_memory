# Unified Agent Memory System (UAMS)

The **Unified Agent Memory System (UAMS)** is a production-grade, local-first, multi-agent memory architecture designed to provide AI agents (such as Hermes, OpenClaw, and VoiceAI) with durable, graph-enhanced, and semantically searchable long-term memory.

## 🏗 System Architecture

```text
 ┌────────────────┐
 │    Obsidian    │
 └────────┬───────┘
          │
  Markdown Watcher
          │
 ┌───────────────┼───────────────┐
 │                               │
 ┌───────▼────────┐      ┌────────▼────────┐
 │     Qdrant     │      │ Knowledge Graph │
 │ Semantic Store │      │      Neo4j      │
 └───────┬────────┘      └────────┬────────┘
 │                               │
 └───────────────┬───────────────┘
                 │
       Unified Retrieval API
                 │
 ┌────────────────┼────────────────┐
 │                │                │
 ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
 │   Hermes    │  │  OpenClaw   │  │ VoiceAgent  │
 └─────────────┘  └─────────────┘  └─────────────┘
```

## 🚀 Key Features by Phase

### Phase 1: Canonical Memory Vault
- **Obsidian-Native:** Memory is stored in human-readable Markdown, structured across `Concepts/`, `Daily/`, `Tasks/`, etc.
- **Protocol Enforced:** Governed by `AGENTS.md` to ensure atomic, highly-linked, metadata-rich memory files.

### Phase 2: Automatic Embedding Pipeline
- **Memory Watcher:** An asynchronous file watcher (`watchdog`) detects changes, debounces rapid saves, and processes modified memory files.
- **Semantic Chunking:** An advanced chunker that splits text while preserving Markdown hierarchy (`H1 > H2 > H3`), code blocks, and Entity Wikilinks (`[[Entity]]`), generating deterministic hashes for chunks.

### Phase 3: Vector Database (Qdrant)
- **Local-First & Apple Silicon Optimized:** Uses local Qdrant via Docker.
- **Dynamic Embeddings:** Uses `fastembed` (for native MPS/Metal acceleration) or `ollama` (for API-driven local models).
- **Batch Processing:** Implements an async SQLite cache to prevent redundant embedding generation and executes batch upserts to Qdrant.

### Phase 4: Unified Retrieval API (FastAPI)
- **8-Step Search Pipeline:** Query Understanding → Intent Classification → Entity Extraction → Graph Expansion → Vector Retrieval → Reranking → Context Compression → Final Assembly.
- **Endpoints:** Exposes `/search`, `/context`, `/remember`, `/procedures`, and `/entities` to the agents.

### Phase 5: Hermes & OpenClaw Integration
- **Agent Tools:** Provides callable functions for standard agent loops (`search_memory`, `store_memory`).
- **Auto-Context Middleware:** Automatically intercepts prompts, retrieves highly compressed relevant memories, and injects them as `<memory_context>` seamlessly.
- **Context Compression:** Deduplicates results, clusters by entity, and uses extractive summarization to aggressively reduce LLM token usage while preserving facts.

### Phase 6: Knowledge Graph (Neo4j / NetworkX)
- **Graph Extraction:** Parses unstructured Markdown to extract Entities and Relational Edges (`uses`, `fixes`, `caused_by`, `depends_on`).
- **Hybrid Reranking:** Enhances semantic search by mathematically boosting retrieved chunks that have a structural graph relationship (e.g., `fixes`) to the user's query entities.
- **Dual Store:** Uses NetworkX for rapid local n-hop traversals and Neo4j for persistent production storage.

### Phase 7: Autonomous Memory Intelligence
- **Distillation Engine:** A background process that ages and decays daily logs (30-day half-life).
- **Lifecycle Management:** Automatically transitions memories (`raw` → `summarized` → `distilled`).
- **Procedural Promotion:** Highly dense, important memories (e.g., bug fixes) are automatically extracted and rewritten as permanent Standard Operating Procedures (SOPs) in the `Tasks/` directory.

## 🛠 Getting Started

### Prerequisites
- macOS (Apple Silicon recommended)
- Python 3.11+
- Docker & Docker Compose (for Qdrant)
- `uv` (Fast Python package installer)

### Installation & Execution

1. **Start the Vector Database (Qdrant)**
   ```bash
   cd memory_watcher
   bash scripts/start_qdrant.sh
   ```

2. **Run the Memory Watcher (Background Sync)**
   ```bash
   cd memory_watcher
   bash start.sh
   ```

3. **Start the Unified Retrieval API**
   ```bash
   cd memory_watcher
   source .venv/bin/activate
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
   *View the Swagger OpenAPI documentation at: `http://localhost:8000/docs`*

4. **Run Autonomous Distillation Cycle (Cron/Scheduled)**
   ```bash
   cd memory_watcher
   source .venv/bin/activate
   python intelligence/distiller.py
   ```

## 🧠 Using with OpenClaw

To integrate this with your local OpenClaw or Hermes instance, install the middleware located in `memory_watcher/integrations/openclaw/`. Ensure your system prompt is appended with the rules defined in `prompts.md`.
