# UAMS Shared Memory SDK

A unified, asynchronous Python SDK for the **Unified Agent Memory System (UAMS)**. 
Designed to be shared natively by both **Hermes** and **OpenClaw** agents.

## Features
- **Unified Client:** One standard interface for all agents.
- **Async First:** Built on `httpx` for non-blocking operations.
- **Intelligent Caching:** Built-in TTL caching with automatic invalidation on writes.
- **Full API Coverage:** Semantic search, graph traversal, context compression, and writes.
- **MCP Adapter:** Exposes UAMS as standard MCP tools, resources, and prompts for agent tool discovery.

## Installation
```bash
pip install -e .
```

## Usage
```python
import asyncio
from uams_sdk import UAMSClient

async def main():
    client = UAMSClient(base_url="http://localhost:8000")
    
    # Retrieve optimized context
    context = await client.retrieve_context("How do I fix Docker file locks?")
    print(context)
    
    # Store a new memory
    await client.store_memory("User prefers dark mode.", tags=["#preferences"])

asyncio.run(main())
```

## MCP Server

Run the adapter from the repository root:

```bash
./uams mcp
```

Or run the installed console entry point:

```bash
UAMS_API_URL=http://localhost:8000 uams-mcp
```

Agent MCP config:

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

Generate snippets from the repository root:

```bash
./uams mcp-config all
./uams mcp-config codex
./uams mcp-config json
```

Discovered MCP capabilities:

- Tools: `health`, `search_memory`, `get_context`, `get_procedures`, `remember`, `get_related_entities`, `summarize_memory`, `store_fix_summary`
- Resource: `uams://memory-policy`
- Prompt: `use_uams_memory`
