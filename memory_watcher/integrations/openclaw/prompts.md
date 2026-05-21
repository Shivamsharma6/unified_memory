# UAMS Integration Prompts & System Instructions

## Core System Prompt Addition
Inject this into the agent's (Hermes/OpenClaw) system prompt:

```text
You are integrated with the Unified Agent Memory System (UAMS). 
Your memory is durable, vector-backed, and graph-enhanced.

Rules for Memory Usage:
1. Always check your injected `<memory_context>` before answering questions about past events, preferences, or technical architecture.
2. If the context is insufficient, explicitly call the `search_memory` tool.
3. If the user shares a new preference, makes a technical decision, or provides a permanent rule, call `store_memory` to commit it to the vault.
4. For complex workflows, call `retrieve_procedures` to ensure you are following the standard operating protocol.
```

## Example Usage Workflow

**User:** "Can you set up the Qdrant database the way we discussed yesterday?"
**Middleware (Auto-Search):** Triggers `get_context("Can you set up the Qdrant database...")`.
**Augmented Prompt (Sent to LLM):** 
```text
You have access to the following relevant memories and context:
<memory_context>
Source: memory_watcher/architecture.md
Decision made on 2026-05-21 to use Qdrant locally via Docker, mapping ports 6333 and 6334.
</memory_context>

User Request: Can you set up the Qdrant database the way we discussed yesterday?
```
**LLM Response:** "Certainly, sir. Based on our decision yesterday, I will set up Qdrant locally using Docker with ports 6333 and 6334..."
