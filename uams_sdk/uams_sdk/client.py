import os
import httpx
import logging
import json
from datetime import date
from typing import Dict, Any, List, Optional
from .cache import SDKCache
from .exceptions import UAMSError, UAMSConnectionError, UAMSAPIError

logger = logging.getLogger(__name__)

class UAMSClient:
    """
    Unified Agent Memory System (UAMS) SDK Client.
    Shared across Hermes, OpenClaw, VoiceAI, Antigravity.
    """
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        cache_ttl: int = 300,
        source_agent: Optional[str] = None,
        project: Optional[str] = None,
    ):
        self.base_url = base_url
        self.source_agent = (
            source_agent
            or os.getenv("UAMS_AGENT_NAME")
            or os.getenv("UAMS_SOURCE_AGENT")
            or "unknown"
        )
        self.project = project or os.getenv("UAMS_PROJECT")
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self.cache = SDKCache(ttl=cache_ttl)

    async def _request(self, method: str, endpoint: str, json_data: Dict[str, Any] = None, use_cache: bool = False) -> Dict[str, Any]:
        if use_cache and method == "POST":
            cached = self.cache.get(endpoint, json_data or {})
            if cached:
                logger.debug(f"Cache hit for {endpoint}")
                return cached

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                if method == "POST":
                    response = await client.post(f"{self.base_url}{endpoint}", json=json_data or {})
                elif method == "GET":
                    response = await client.get(f"{self.base_url}{endpoint}", params=json_data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                response.raise_for_status()
                data = response.json()
                
                if use_cache and method == "POST":
                    self.cache.set(endpoint, json_data or {}, data)
                    
                return data
                
            except httpx.HTTPStatusError as e:
                raise UAMSAPIError(f"API Error: {e.response.status_code}", status_code=e.response.status_code, details=e.response.text)
            except httpx.RequestError as e:
                raise UAMSConnectionError(f"Connection error to UAMS {endpoint}: {str(e)}")

    async def search(
        self,
        query: str,
        limit: int = 5,
        entities: List[str] = None,
        compress: bool = True,
        memory_types: List[str] = None,
        tags: List[str] = None,
        projects: List[str] = None,
        source_agents: List[str] = None,
        min_score: float = 0.0,
        include_historical: bool = False,
    ) -> Dict[str, Any]:
        """Semantic + Graph hybrid retrieval."""
        payload = {
            "query": query,
            "limit": limit,
            "entities": entities or [],
            "compress": compress,
            "memory_types": memory_types or [],
            "tags": tags or [],
            "projects": projects or ([self.project] if self.project else []),
            "source_agents": source_agents or [],
            "min_score": min_score,
            "include_historical": include_historical,
        }
        return await self._request("POST", "/search", payload, use_cache=True)

    async def retrieve_context(self, task: str, max_tokens: int = 2000) -> str:
        """Highly compressed context assembly for LLM prompting."""
        res = await self._request("POST", "/context", {"task": task, "max_tokens": max_tokens}, use_cache=True)
        return res.get("context", "")

    async def retrieve_procedures(self, task: str) -> List[str]:
        """Fetch procedural memories (AGENTS.md / SOPs)."""
        res = await self._request("POST", f"/procedures", {"task": task}, use_cache=True)
        return res.get("procedures", [])

    async def begin_task(
        self,
        task: str,
        max_tokens: int = 2000,
        source_agent: Optional[str] = None,
        project: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Default memory preflight agents should call before doing work."""
        agent = source_agent or self.source_agent
        proj = project or self.project
        import uuid as _uuid
        active_session_id = session_id or str(_uuid.uuid4())

        procedures = await self.retrieve_procedures(task)
        context = await self.retrieve_context(task, max_tokens=max_tokens)
        return {
            "session_id": active_session_id,
            "task": task,
            "source_agent": agent,
            "project": proj,
            "status": "ready",
            "procedures": procedures,
            "context": context,
            "max_tokens": max_tokens,
            "memory_policy": (
                "Always call begin_task before non-trivial work. Use the procedures and "
                "context as grounding. Call search_memory when recall is needed during "
                "the task. Call end_task after durable work to store distilled outcomes."
            ),
        }

    async def store_memory(
        self,
        text: str,
        category: str = "episodic",
        tags: List[str] = None,
        source_agent: Optional[str] = None,
        project: Optional[str] = None,
        entities: List[str] = None,
        sync: bool = False,
        distill: bool = False,
    ) -> Dict[str, Any]:
        """Agent memory write support. Clears cache to ensure fresh reads."""
        agent = source_agent or self.source_agent
        proj = project or self.project
        payload = {
            "text": text,
            "category": category,
            "tags": tags or [],
            "source_agent": agent,
            "project": proj,
            "entities": entities or [],
            "sync": sync,
            "distill": distill,
        }
        try:
            res = await self._request("POST", "/remember", payload, use_cache=False)
            self.cache.clear()
            return {
                "ok": True,
                "memory_id": res.get("memory_id"),
                "decision": res.get("decision", "ADD"),
                "index_status": res.get("index_status", "active"),
                "path": res.get("path"),
            }
        except UAMSError as e:
            logger.error(f"Failed to store memory: {e}")
            return {"ok": False, "error": str(e)}

    async def end_task(
        self,
        task: str,
        outcome: str,
        files: Optional[List[str]] = None,
        decisions: Optional[List[str]] = None,
        fixes: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: str = "episodic",
        source_agent: Optional[str] = None,
        project: Optional[str] = None,
        session_id: Optional[str] = None,
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Store a distilled task outcome after durable work completes."""
        agent = source_agent or self.source_agent
        proj = project or self.project
        all_tags = list(dict.fromkeys((tags or []) + ["#auto-distilled", "#task-outcome"]))
        entity_links = " ".join(f"[[{entity}]]" for entity in entities or [])
        file_lines = "\n".join(f"- `{path}`" for path in files or []) or "- Not specified"
        decision_lines = "\n".join(f"- {item}" for item in decisions or []) or "- None recorded"
        fix_lines = "\n".join(f"- {item}" for item in fixes or []) or "- None recorded"
        today = date.today().isoformat()

        tags_json = json.dumps(all_tags)
        frontmatter = f"""---
type: {category}
date: {today}
source_agent: {agent}"""
        if proj:
            frontmatter += f"\nproject: {proj}"
        if session_id:
            frontmatter += f"\nsession_id: {session_id}"
        frontmatter += f"\ntags: {tags_json}\n---"

        text = f"""{frontmatter}
# Task Outcome: {task}

## TL;DR
{outcome.strip()}

## Entities
{entity_links or f"[[{task}]]"}

## Files
{file_lines}

## Decisions
{decision_lines}

## Fixes
{fix_lines}

## Retrieval Notes
Future agents should search for [[{task}]], the listed entities, and the listed files before repeating related work.
"""
        store_res = await self.store_memory(
            text=text,
            category=category,
            tags=all_tags,
            source_agent=agent,
            project=proj,
            entities=entities or [],
            sync=sync,
        )
        return {
            "ok": store_res.get("ok", False),
            "category": category,
            "tags": all_tags,
            "memory_id": store_res.get("memory_id"),
            "decision": store_res.get("decision"),
            "error": store_res.get("error"),
            "session_id": session_id,
        }


    async def distill_memory(self, topic: str) -> str:
        """Trigger summarization/distillation of a topic."""
        res = await self._request("POST", "/summarize", {"topic": topic}, use_cache=False)
        return res.get("summary", "")

    async def related_entities(self, entity: str, radius: int = 1) -> Dict[str, Any]:
        """Graph retrieval: neighborhood expansion."""
        try:
            return await self._request("GET", f"/graph/neighborhood/{entity}", {"radius": radius}, use_cache=True)
        except UAMSAPIError as e:
            if getattr(e, 'status_code', None) == 404:
                return {"error": f"Entity '{entity}' not found in knowledge graph.", "nodes": [], "links": []}
            raise

    async def get_identity(self, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """Get identity profile for entity or caller agent."""
        resolved = entity_id or (self.source_agent if self.source_agent != "unknown" else "default")
        return await self._request("POST", "/identity/profile", {"entity_id": resolved}, use_cache=True)

    async def inject_identity(
        self, entity_id: Optional[str] = None, query: str = "", task_type: str = "general"
    ) -> Dict[str, Any]:
        """Inject identity into reasoning."""
        resolved = entity_id or (self.source_agent if self.source_agent != "unknown" else "default")
        return await self._request("POST", "/identity/inject", {
            "entity_id": resolved, "query": query, "task_type": task_type
        }, use_cache=False)

    async def extract_identity(
        self,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Extract identity from memories."""
        resolved = entity_id or (self.source_agent if self.source_agent != "unknown" else "default")
        name = entity_name or (self.source_agent if self.source_agent != "unknown" else "Agent")
        return await self._request("POST", "/identity/extract", {
            "entity_id": resolved, "entity_name": name, "memories": memories or []
        }, use_cache=False)


    async def memory_quality(self, path: str) -> Dict[str, Any]:
        """Score memory quality."""
        return await self._request("POST", "/memory/quality", {"path": path}, use_cache=True)

    async def wait_for_indexing(
        self,
        memory_id: str,
        timeout: float = 5.0,
        poll_interval: float = 0.1,
    ) -> bool:
        """Poll the memory status endpoint until the revision is active or timeout occurs."""
        import asyncio
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                res = await self._request("GET", f"/memory/status/{memory_id}", use_cache=False)
                if res.get("revision_status") == "active":
                    return True
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
        return False

