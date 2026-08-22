# UAMS Alpha Tester & Design Partner Program 🧪

Welcome to the **Unified Agent Memory System (UAMS)** Alpha Tester & Design Partner Program!

If you are building multi-agent systems, autonomous workflows, or memory-enabled AI applications, you know the pain:
- Agents forgetting context across sessions.
- Duplicate notes and raw conversation dumps cluttering databases.
- Vector-only search missing exact entity relationships and recent changes.
- Opaque cloud backends that you cannot inspect or audit in Markdown.

UAMS solves this with an **Obsidian-compatible Markdown authority layer**, **PostgreSQL + Qdrant hybrid retrieval**, and **bitemporal claim evolution**.

---

## 🎯 What We Are Looking For

We are seeking builders to test UAMS in real-world scenarios:
1. **Multi-Agent Teams**: Frameworks like LangChain, CrewAI, AutoGen, or custom agent networks.
2. **Coding Assistants & IDE Agents**: Integrating UAMS via MCP in Claude Desktop, Cursor, or Windsurf.
3. **Domain-Specific Agents**: Research, customer support, legal/finance analysis, and personal AI assistants.

---

## 🚀 How to Get Started in 3 Steps

### 1. Spin up UAMS Locally
```bash
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory
docker compose up -d
```

### 2. Verify Your Environment
```bash
pip install uams-sdk
uams-doctor
```

### 3. Connect Your Agents
Use our drop-in adapters for [LangChain, CrewAI, or LlamaIndex](../../README.md#-framework-adapters) or the native Python SDK:
```python
from uams_sdk import UAMSClient

client = UAMSClient(source_agent="MyAgent", project="AlphaProject")
```

---

## 💬 How to Share Feedback & Get Direct Support

We provide direct architectural support to all alpha testers:
- **GitHub Discussions**: Post in [Show and Tell](https://github.com/Shivamsharma6/unified_memory/discussions) or [Q&A](https://github.com/Shivamsharma6/unified_memory/discussions/categories/q-a).
- **Issue Tracker**: File [Bug Reports](https://github.com/Shivamsharma6/unified_memory/issues/new?template=bug_report.md) or [Connector Requests](https://github.com/Shivamsharma6/unified_memory/issues/new?template=connector_request.md).
- **Direct Email**: Reach the team directly at `shivam@unifiedmemory.ai`.

---

## 🏆 Alpha Tester Perks
- Direct 1-on-1 architectural consultations and priority connector development.
- Co-authorship and spotlight in the UAMS README, case studies, and official documentation.
- Early access to upcoming v2 features (distributed federation, graph visualizer, and local MLX models).
