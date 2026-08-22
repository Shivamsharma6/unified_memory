# Implementation Plan: Open-Source Polish, Adapters, and Developer Experience

**Goal**: Deliver 5 developer-first enhancements to attract contributors and external beta testers: 1-command Docker onboarding, framework adapters (LangChain, LlamaIndex, CrewAI), contributor guides, README visual polish with comparison matrix, and an alpha tester diagnostic suite.

---

## Tasks

### Task 1: 1-Command Onboarding & CLI Interactive Demo
- **Files**:
  - `docker-compose.yml` (root level)
  - `Dockerfile` (root level)
  - `uams_sdk/uams_sdk/demo.py`
  - `uams_sdk/pyproject.toml` (expose `uams-demo` script)
- **Changes**:
  - Create production-ready Docker Compose stack running PostgreSQL (`pgvector`), Qdrant, and UAMS API.
  - Implement terminal interactive demo simulating multi-agent memory sharing.

### Task 2: Drop-in Framework Adapters
- **Files**:
  - `uams_sdk/uams_sdk/adapters/__init__.py`
  - `uams_sdk/uams_sdk/adapters/langchain.py`
  - `uams_sdk/uams_sdk/adapters/llamaindex.py`
  - `uams_sdk/uams_sdk/adapters/crewai.py`
  - `memory_watcher/tests/test_sdk_adapters.py`
- **Changes**:
  - Implement LangChain message history and retriever.
  - Implement LlamaIndex retriever.
  - Implement CrewAI memory storage backend.
  - Add test suite covering all 3 adapters.

### Task 3: Contributor Infrastructure & Community Templates
- **Files**:
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `.github/pull_request_template.md`
  - `.github/ISSUE_TEMPLATE/bug_report.md`
  - `.github/ISSUE_TEMPLATE/feature_request.md`
  - `.github/ISSUE_TEMPLATE/connector_request.md`
- **Changes**:
  - Comprehensive 3-step setup guide and TDD instructions.
  - Issue and PR templates for frictionless collaboration.

### Task 4: README Polish, Visual Flow & Comparison Matrix
- **Files**:
  - `README.md`
- **Changes**:
  - Add live badges (PyPI, CI, License, Python 3.11+).
  - Add 1-command quickstart section.
  - Add competitive comparison matrix (vs. Mem0, Zep, Graphiti).
  - Add copy-paste framework adapter code snippets.
  - Add alpha tester invitation banner.

### Task 5: External Tester Program & Diagnostic Health Check
- **Files**:
  - `uams_sdk/uams_sdk/diagnostics.py` (adds `uams-doctor` CLI)
  - `uams_sdk/pyproject.toml`
  - `docs/community/ALPHA_TESTERS.md`
  - `examples/multi_agent_team_demo.py`
  - `memory_watcher/tests/test_sdk_diagnostics.py`
- **Changes**:
  - Implement `uams doctor` command to check environment readiness.
  - Create end-to-end multi-agent team demo script.
  - Create design partner & alpha tester guide.
