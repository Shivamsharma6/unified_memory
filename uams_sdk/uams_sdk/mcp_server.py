import os
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import UAMSClient


DEFAULT_BASE_URL = os.getenv("UAMS_API_URL", "http://localhost:8000")

mcp = FastMCP(
    "Unified Agent Memory",
    instructions=(
        "Use UAMS as the default shared memory backend. Before coding or answering, "
        "call get_context and get_procedures for relevant background. After durable "
        "work, call remember or store_fix_summary with distilled, non-transcript memory."
    ),
)


def _client() -> UAMSClient:
    return UAMSClient(base_url=os.getenv("UAMS_API_URL", DEFAULT_BASE_URL))


@mcp.resource("uams://memory-policy")
def memory_policy() -> str:
    """Default operating policy agents should follow when UAMS is available."""
    return """# UAMS Default Memory Policy

Before each task:
- Call `get_procedures` for task-specific rules.
- Call `get_context` for compressed historical and graph context.
- Use `search_memory` when targeted lookup is needed.

After each task:
- Store only durable facts, decisions, fixes, and procedures.
- Never store raw chat transcripts.
- Prefer wikilinks like `[[Entity Name]]` and tags like `#bugfix`.
- Use `store_fix_summary` for bug fixes so future retrieval can explain cause and resolution.
"""


@mcp.prompt(title="Use UAMS Memory")
def use_uams_memory(task: str) -> str:
    """Prompt template that makes an agent default to UAMS for a task."""
    return f"""You have access to Unified Agent Memory System tools.

Task: {task}

Protocol:
1. Call `get_procedures` with the task.
2. Call `get_context` with the task.
3. Use the retrieved memory as grounding before acting.
4. After completing durable work, call `remember` or `store_fix_summary`.
5. Store distilled atomic memory only, never raw conversation."""


@mcp.tool()
async def health() -> dict[str, Any]:
    """Check whether the UAMS Retrieval API is reachable."""
    return await _client()._request("GET", "/health", use_cache=False)


@mcp.tool()
async def search_memory(
    query: str,
    limit: int = 5,
    entities: list[str] | None = None,
    compress: bool = True,
) -> dict[str, Any]:
    """Search UAMS using hybrid semantic and graph-aware retrieval."""
    return await _client().search(
        query=query,
        limit=limit,
        entities=entities or [],
        compress=compress,
    )


@mcp.tool()
async def get_context(task: str, max_tokens: int = 2000) -> dict[str, Any]:
    """Return compressed memory context for an agent task."""
    context = await _client().retrieve_context(task=task, max_tokens=max_tokens)
    return {"task": task, "context": context, "max_tokens": max_tokens}


@mcp.tool()
async def get_procedures(task: str) -> dict[str, Any]:
    """Return procedural memories and operating rules relevant to a task."""
    procedures = await _client().retrieve_procedures(task=task)
    return {"task": task, "procedures": procedures}


@mcp.tool()
async def remember(
    text: str,
    category: str = "episodic",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Store a distilled memory in UAMS. Do not use for raw transcripts."""
    ok = await _client().store_memory(
        text=text,
        category=category,
        tags=tags or [],
    )
    return {"ok": ok, "category": category, "tags": tags or []}


@mcp.tool()
async def get_related_entities(entity: str, radius: int = 1) -> dict[str, Any]:
    """Fetch a graph neighborhood around an entity."""
    return await _client().related_entities(entity=entity, radius=radius)


@mcp.tool()
async def summarize_memory(topic: str) -> dict[str, Any]:
    """Ask UAMS to generate or retrieve a semantic summary for a topic."""
    summary = await _client().distill_memory(topic=topic)
    return {"topic": topic, "summary": summary}


@mcp.tool()
async def store_fix_summary(
    issue: str,
    cause: str,
    resolution: str,
    files: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Store a durable bug-fix memory with cause, resolution, files, and entities."""
    all_tags = list(dict.fromkeys((tags or []) + ["#bugfix", "#auto-distilled"]))
    linked_entities = " ".join(f"[[{entity}]]" for entity in entities or [])
    file_list = "\n".join(f"- `{path}`" for path in files or [])
    today = date.today().isoformat()

    text = f"""---
type: procedural
date: {today}
tags: {all_tags}
---
# Fix Summary: {issue}

## TL;DR
[[{issue}]] was caused by {cause} and resolved by {resolution}.

## Entities
{linked_entities or f"[[{issue}]]"}

## Files
{file_list or "- Not specified"}

## Cause
{cause}

## Resolution
{resolution}

## Retrieval Notes
Future agents should search for [[{issue}]], related files, and the listed entities before re-debugging this class of issue.
"""

    ok = await _client().store_memory(text=text, category="procedural", tags=all_tags)
    return {
        "ok": ok,
        "issue": issue,
        "category": "procedural",
        "tags": all_tags,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
