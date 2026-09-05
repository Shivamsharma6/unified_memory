import os
from datetime import date
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import UAMSClient


DEFAULT_BASE_URL = os.getenv("UAMS_API_URL", "http://localhost:8000")

mcp = FastMCP(
    "Unified Agent Memory",
    instructions=(
        "Use UAMS as the default shared memory backend. Before coding or answering, "
        "call begin_task for relevant procedures and context. After durable work, "
        "call end_task with distilled, non-transcript outcomes. Use search_memory "
        "during work when additional recall is needed."
    ),
)


_shared_client: Optional[UAMSClient] = None


def _client() -> UAMSClient:
    global _shared_client
    base_url = os.getenv("UAMS_API_URL", DEFAULT_BASE_URL)
    if _shared_client is None or _shared_client.base_url != base_url.rstrip("/"):
        _shared_client = UAMSClient(base_url=base_url)
    return _shared_client


@mcp.resource("uams://memory-policy")
def memory_policy() -> str:
    """Default operating policy agents should follow when UAMS is available."""
    return """# UAMS Default Memory Policy

Before each task:
- Call `begin_task` for task-specific rules, compressed historical context, and graph context.
- Use `search_memory` when targeted lookup is needed.

After each task:
- Call `end_task` with distilled outcomes.
- Store only durable facts, decisions, fixes, and procedures.
- Never store raw chat transcripts.
- Prefer wikilinks like `[[Entity Name]]` and tags like `#bugfix`.
- Use `store_fix_summary` for bug fixes so future retrieval can explain cause and resolution.
"""


@mcp.prompt(title="Use UAMS Memory")
def use_uams_memory(task: str = "") -> str:
    """Prompt template that makes an agent default to UAMS for a task."""
    task_line = f"Task: {task}\n\n" if task else ""
    return f"""You have access to Unified Agent Memory System tools.

{task_line}Protocol:
1. Call `begin_task` with the task.
2. Use the returned procedures and context as grounding before acting.
3. Use `search_memory` during work when additional recall is needed.
4. After completing durable work, call `end_task`.
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
    memory_types: list[str] | None = None,
    tags: list[str] | None = None,
    projects: list[str] | None = None,
    source_agents: list[str] | None = None,
    min_score: float = 0.0,
    include_historical: bool = False,
) -> dict[str, Any]:
    """Search UAMS using hybrid semantic and graph-aware retrieval."""
    return await _client().search(
        query=query,
        limit=limit,
        entities=entities or [],
        compress=compress,
        memory_types=memory_types or [],
        tags=tags or [],
        projects=projects or [],
        source_agents=source_agents or [],
        min_score=min_score,
        include_historical=include_historical,
    )


@mcp.tool()
async def begin_task(
    task: str,
    max_tokens: int = 2000,
    source_agent: str | None = None,
    project: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Default first call before work: retrieve procedures, context, and memory policy."""
    return await _client().begin_task(
        task=task,
        max_tokens=max_tokens,
        source_agent=source_agent,
        project=project,
        session_id=session_id,
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
    source_agent: str | None = None,
    project: str | None = None,
    entities: list[str] | None = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Store a distilled memory in UAMS. Do not use for raw transcripts."""
    res = await _client().store_memory(
        text=text,
        category=category,
        tags=tags or [],
        source_agent=source_agent,
        project=project,
        entities=entities or [],
        sync=sync,
    )
    return {
        "ok": res.get("ok", False),
        "memory_id": res.get("memory_id"),
        "decision": res.get("decision", "ADD"),
        "index_status": res.get("index_status", "active"),
        "path": res.get("path"),
        "error": res.get("error"),
        "category": category,
        "tags": tags or [],
    }


@mcp.tool()
async def end_task(
    task: str,
    outcome: str,
    files: list[str] | None = None,
    decisions: list[str] | None = None,
    fixes: list[str] | None = None,
    entities: list[str] | None = None,
    tags: list[str] | None = None,
    category: str = "episodic",
    source_agent: str | None = None,
    project: str | None = None,
    session_id: str | None = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Default final call after durable work: store distilled task outcome memory."""
    return await _client().end_task(
        task=task,
        outcome=outcome,
        files=files or [],
        decisions=decisions or [],
        fixes=fixes or [],
        entities=entities or [],
        tags=tags or [],
        category=category,
        source_agent=source_agent,
        project=project,
        session_id=session_id,
        sync=sync,
    )


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
    source_agent: str | None = None,
    project: str | None = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Store a durable bug-fix memory with cause, resolution, files, and entities."""
    agent = source_agent or os.getenv("UAMS_AGENT_NAME") or "unknown"
    proj = project or os.getenv("UAMS_PROJECT")
    all_tags = list(dict.fromkeys((tags or []) + ["#bugfix", "#auto-distilled"]))
    linked_entities = " ".join(f"[[{entity}]]" for entity in entities or [])
    file_list = "\n".join(f"- `{path}`" for path in files or [])
    today = date.today().isoformat()

    import json
    tags_json = json.dumps(all_tags)
    frontmatter = f"""---
type: procedural
date: {today}
source_agent: {agent}"""
    if proj:
        frontmatter += f"\nproject: {proj}"
    frontmatter += f"\ntags: {tags_json}\n---"

    text = f"""{frontmatter}
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

    res = await _client().store_memory(
        text=text,
        category="procedural",
        tags=all_tags,
        source_agent=agent,
        project=proj,
        entities=entities or [],
        sync=sync,
    )
    return {
        "ok": res.get("ok", False),
        "issue": issue,
        "category": "procedural",
        "tags": all_tags,
        "memory_id": res.get("memory_id"),
        "error": res.get("error"),
    }


@mcp.tool()
async def get_identity(entity_id: str | None = None) -> dict[str, Any]:
    """Get the identity profile for an entity or the caller agent (traits, confidence, version)."""
    resolved_id = entity_id or os.getenv("UAMS_AGENT_NAME") or "default"
    return await _client().get_identity(entity_id=resolved_id)


@mcp.tool()
async def inject_identity(
    entity_id: str | None = None,
    query: str = "",
    task_type: str = "general",
) -> dict[str, Any]:
    """Inject identity context into agent reasoning for personalized responses."""
    resolved_id = entity_id or os.getenv("UAMS_AGENT_NAME") or "default"
    return await _client().inject_identity(
        entity_id=resolved_id, query=query, task_type=task_type
    )


@mcp.tool()
async def extract_identity(
    entity_id: str | None = None,
    entity_name: str = "Agent",
    memories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract identity traits from episodic memories."""
    resolved_id = entity_id or os.getenv("UAMS_AGENT_NAME") or "default"
    return await _client().extract_identity(
        entity_id=resolved_id,
        entity_name=entity_name,
        memories=memories or [],
    )



@mcp.tool()
async def memory_quality(path: str) -> dict[str, Any]:
    """Score a memory note's quality and completeness."""
    return await _client().memory_quality(path=path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
