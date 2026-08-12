# UAMS SDK

The official asynchronous Python client and Model Context Protocol (MCP) server for the [Unified Agent Memory System](https://github.com/Shivamsharma6/unified_memory).

UAMS gives Codex, Claude, Hermes, OpenClaw, VoiceAI, and custom agents one shared memory for facts, decisions, procedures, exact profiles, entity relationships, and bug-fix history. The SDK provides a common task lifecycle so agents retrieve relevant knowledge before work and store distilled outcomes afterward.

> This package is the client and MCP integration layer. It connects to a running UAMS server; it does not bundle PostgreSQL, Qdrant, Ollama, or the Markdown vault.

## Installation

```bash
pip install uams-sdk
```

Python 3.11 or newer is required. Install and start the self-hosted UAMS server by following the [server installation guide](https://github.com/Shivamsharma6/unified_memory#five-minute-installation). The default API address is `http://127.0.0.1:8000`.

## Why UAMS Uses Multiple Stores

The server keeps Markdown authoritative and treats its databases as rebuildable projections:

- **PostgreSQL** owns exact and current revision truth, full-text retrieval, durable jobs, graph evidence, and exact profiles.
- **Qdrant** owns semantic vector similarity, including recall when agents use different wording for the same concept.
- **Markdown** remains the canonical human-readable and Git-reviewable memory.

Every normal retrieval result is validated against the current revision in PostgreSQL, so stale, archived, deleted, or superseded vectors are not silently returned as current knowledge.

## Python SDK

The client is async-first and includes a small TTL cache for read requests. Writes invalidate the local cache.

```python
import asyncio

from uams_sdk import UAMSClient


async def main() -> None:
    client = UAMSClient(base_url="http://127.0.0.1:8000")
    task = "Fix intermittent session refresh failures"

    # Retrieve task-specific procedures and compressed historical context.
    preflight = await client.begin_task(task, max_tokens=2000)
    print(preflight["procedures"])
    print(preflight["context"])

    # Request targeted recall while working.
    recall = await client.search(
        "previous refresh-token fixes",
        limit=5,
        entities=["Authentication Service"],
        compress=True,
    )
    print(recall["results"])

    # Store only the durable outcome, never a raw conversation transcript.
    await client.end_task(
        task=task,
        outcome="Made refresh-token rotation atomic and added regression coverage.",
        files=["auth/session.py", "tests/test_session.py"],
        decisions=["Keep token invalidation in the same transaction."],
        fixes=["Prevent reuse of the superseded refresh token."],
        entities=["Authentication Service", "Session Refresh Fix"],
        tags=["#bugfix"],
        category="procedural",
    )


asyncio.run(main())
```

### Client Methods

| Method | Purpose |
| --- | --- |
| `begin_task` | Retrieve procedures, compressed context, and the shared memory policy. |
| `search` | Run hybrid semantic and lexical retrieval with optional entity hints. |
| `retrieve_context` | Assemble a token-bounded context block for an agent task. |
| `retrieve_procedures` | Retrieve relevant operating procedures. |
| `store_memory` | Store a distilled semantic, episodic, or procedural memory. |
| `end_task` | Store a structured task outcome with files, decisions, fixes, and entities. |
| `distill_memory` | Ask the server to summarize retrieved memory about a topic. |
| `related_entities` | Retrieve an evidence-backed graph neighborhood. |
| `get_identity` | Read an optional identity-kernel profile. |
| `inject_identity` | Retrieve optional identity context for reasoning. |
| `extract_identity` | Extract optional identity traits from supplied memories. |
| `memory_quality` | Score the structure and metadata of a Markdown memory. |

## MCP Server

The package installs the `uams-mcp` stdio server:

```bash
UAMS_API_URL=http://127.0.0.1:8000 uams-mcp
```

Register it in a JSON-based MCP client:

```json
{
  "mcpServers": {
    "uams": {
      "command": "uams-mcp",
      "env": {
        "UAMS_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

The recommended protocol is:

```text
begin_task -> act / search_memory -> end_task
```

### MCP Capabilities

UAMS SDK 1.1 exposes 14 MCP tools:

| Tool | Purpose |
| --- | --- |
| `health` | Check API reachability and shallow component health. |
| `begin_task` | Retrieve procedures, context, and the default memory policy. |
| `search_memory` | Run hybrid retrieval with optional entity hints and compression. |
| `get_context` | Build a token-bounded context block for a task. |
| `get_procedures` | Retrieve task-relevant operating rules. |
| `remember` | Store a distilled atomic memory. |
| `end_task` | Store a structured task-outcome memory. |
| `store_fix_summary` | Store an issue, cause, resolution, files, and linked entities. |
| `get_related_entities` | Retrieve an evidence-backed graph neighborhood. |
| `summarize_memory` | Retrieve context and generate an optional LLM summary. |
| `get_identity` | Read an optional identity-kernel profile. |
| `inject_identity` | Produce optional identity context for agent reasoning. |
| `extract_identity` | Extract optional identity traits from supplied memories. |
| `memory_quality` | Score a Markdown memory's structure and metadata. |

It also exposes:

- resource `uams://memory-policy` with the read-before-work and write-after-work rules;
- prompt `use_uams_memory` for applying the protocol to a task.

Identity-kernel tools are optional and distinct from the server's exact PostgreSQL-backed agent, user, and project profiles.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `UAMS_API_URL` | `http://localhost:8000` | Base URL used by the MCP server. |

For direct Python use, pass `base_url` to `UAMSClient`. The client uses a 15-second request timeout with a 5-second connection timeout and a 300-second cache TTL by default.

## Compatibility

- Python 3.11+
- UAMS server 1.1 recommended
- MCP Python SDK `>=1.12.4,<1.13`
- API transport through `httpx`

UAMS is local-first and the default server has no API authentication. Keep it bound to loopback or place an authenticated reverse proxy in front of it before remote access.

## Project Links

- [Server repository and complete documentation](https://github.com/Shivamsharma6/unified_memory)
- [Architecture guide](https://github.com/Shivamsharma6/unified_memory#how-the-architecture-works)
- [Issue tracker](https://github.com/Shivamsharma6/unified_memory/issues)
- [PyPI releases](https://pypi.org/project/uams-sdk/)

## License

MIT
